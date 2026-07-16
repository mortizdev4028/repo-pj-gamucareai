"""Retrieval-augmented generation for public and fictitious clinical content.

Version 0.7 adds deterministic query analysis, candidate reranking, conversational
context, explicit source identifiers and retrieval diagnostics. Access filters
remain enforced before retrieval so the LLM never decides what a user may see.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import time
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

from app.config import get_settings
from app.services.ollama import OllamaClient
from app.observability.metrics import QDRANT_DURATION, QDRANT_SEARCHES, RAG_RESULTS
from app.services.rag_intelligence import QueryProfile, analyse_query, rerank_score

settings = get_settings()


@dataclass(slots=True)
class RetrievedChunk:
    """Normalised and reranked Qdrant result used by prompts and responses."""

    text: str
    title: str
    source: str
    url: str | None
    category: str | None
    score: float
    dense_score: float = 0.0
    citation_id: str | None = None
    content_type: str | None = None
    document_id: str | None = None
    country: str | None = None
    language: str | None = None
    trust_level: str | None = None
    tags: list[str] = field(default_factory=list)
    pet_id: str | None = None
    pet_name: str | None = None
    breed: str | None = None
    species: str | None = None
    event_date: str | None = None
    event_type: str | None = None


@dataclass(slots=True)
class RagDiagnostics:
    """Explain how retrieval behaved for one answer."""

    confidence: str = 'low'
    confidence_reason: str = 'No se ha ejecutado una busqueda.'
    retrieved_count: int = 0
    candidate_count: int = 0
    top_score: float = 0.0
    applied_filters: dict = field(default_factory=dict)
    urgent: bool = False
    urgency_matches: list[str] = field(default_factory=list)
    retrieval_decision: str = 'not_started'
    domain_in_scope: bool = True
    domain_reason: str = 'No se ha evaluado el dominio.'
    candidate_top_score: float = 0.0

    def as_dict(self) -> dict:
        return {
            'confidence': self.confidence,
            'confidence_reason': self.confidence_reason,
            'retrieved_count': self.retrieved_count,
            'candidate_count': self.candidate_count,
            'top_score': round(self.top_score, 4),
            'applied_filters': self.applied_filters,
            'urgent': self.urgent,
            'urgency_matches': self.urgency_matches,
            'retrieval_decision': self.retrieval_decision,
            'domain_in_scope': self.domain_in_scope,
            'domain_reason': self.domain_reason,
            'candidate_top_score': round(self.candidate_top_score, 4),
        }


class RagService:
    """Retrieve filtered context and ask the local model to explain it."""

    def __init__(self) -> None:
        self.ollama = OllamaClient()
        self.qdrant = QdrantClient(url=settings.qdrant_url, timeout=30)
        self.last_diagnostics = RagDiagnostics()

    @staticmethod
    def _build_filter(
        content_types: list[str] | None = None,
        pet_id: uuid.UUID | str | None = None,
        owner_visible_only: bool = False,
    ) -> Filter | None:
        """Build mandatory security and content filters.

        Category and jurisdiction are deliberately handled during reranking. A
        strict category filter could hide useful multi-topic documents.
        """
        must: list[FieldCondition] = []
        if content_types:
            must.append(FieldCondition(key='content_type', match=MatchAny(any=content_types)))
        if pet_id:
            must.append(FieldCondition(key='pet_id', match=MatchValue(value=str(pet_id))))
        if owner_visible_only:
            must.append(FieldCondition(key='visible_to_owner', match=MatchValue(value=True)))
        return Filter(must=must) if must else None

    @staticmethod
    def _history_text(history: list[dict[str, str]] | None) -> str:
        if not history:
            return 'Sin mensajes anteriores relevantes.'
        lines = []
        for item in history[-6:]:
            role = 'Usuario' if item.get('role') == 'user' else 'Asistente'
            content = item.get('content', '').strip()
            if content:
                lines.append(f'{role}: {content[:800]}')
        return '\n'.join(lines) or 'Sin mensajes anteriores relevantes.'

    @staticmethod
    def _confidence(chunks: list[RetrievedChunk]) -> tuple[str, str]:
        if not chunks:
            return 'low', 'No se recuperaron fragmentos por encima del umbral configurado.'
        top = chunks[0].score
        if top >= 0.72 and len(chunks) >= 2:
            return 'high', 'Hay varios fragmentos relevantes y el mejor resultado tiene una puntuacion alta.'
        if top >= 0.55:
            return 'medium', 'Existe contexto util, aunque la coincidencia no es concluyente.'
        return 'low', 'La coincidencia documental es limitada; la respuesta debe interpretarse con cautela.'

    async def search(
        self,
        question: str,
        *,
        content_types: list[str] | None = None,
        pet_id: uuid.UUID | str | None = None,
        owner_visible_only: bool = False,
        limit: int | None = None,
        profile: QueryProfile | None = None,
    ) -> list[RetrievedChunk]:
        """Retrieve a broad semantic candidate set and rerank it transparently."""
        if pet_id:
            inferred_scope = 'pet'
        elif content_types and set(content_types).issubset({'clinical_profile', 'clinical_event'}):
            inferred_scope = 'clinical'
        elif content_types == ['reference_document']:
            inferred_scope = 'general'
        else:
            inferred_scope = 'mixed'
        query_profile = profile or analyse_query(question, scope=inferred_scope)
        mode = content_types[0] if content_types and len(content_types) == 1 else 'mixed'
        if not query_profile.in_domain:
            RAG_RESULTS.labels(mode).observe(0)
            self.last_diagnostics = RagDiagnostics(
                confidence='low',
                confidence_reason=query_profile.domain_reason,
                retrieved_count=0,
                candidate_count=0,
                top_score=0.0,
                candidate_top_score=0.0,
                applied_filters={
                    **query_profile.filters(),
                    'content_types': content_types or [],
                    'pet_id': str(pet_id) if pet_id else None,
                    'owner_visible_only': owner_visible_only,
                },
                urgent=query_profile.urgent,
                urgency_matches=query_profile.urgency_matches,
                retrieval_decision='out_of_scope',
                domain_in_scope=False,
                domain_reason=query_profile.domain_reason,
            )
            return []
        vector = await self.ollama.embed(question)
        query_filter = self._build_filter(content_types, pet_id, owner_visible_only)
        result_limit = limit or settings.rag_top_k
        candidate_limit = max(result_limit, settings.rag_candidate_k)
        qdrant_started = time.perf_counter()
        qdrant_outcome = 'error'
        try:
            try:
                result = self.qdrant.query_points(
                    collection_name=settings.qdrant_collection,
                    query=vector,
                    query_filter=query_filter,
                    limit=candidate_limit,
                    with_payload=True,
                ).points
            except Exception:
                result = self.qdrant.search(
                    collection_name=settings.qdrant_collection,
                    query_vector=vector,
                    query_filter=query_filter,
                    limit=candidate_limit,
                    with_payload=True,
                )
            qdrant_outcome = 'success'
        finally:
            QDRANT_SEARCHES.labels(mode, qdrant_outcome).inc()
            QDRANT_DURATION.labels(mode).observe(time.perf_counter() - qdrant_started)

        candidates: list[RetrievedChunk] = []
        seen: set[str] = set()
        for item in result:
            payload = item.payload or {}
            text = str(payload.get('text', '')).strip()
            if not text:
                continue
            fingerprint = hashlib.sha1(text.encode('utf-8')).hexdigest()
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            dense_score = float(item.score)
            final_score = rerank_score(
                dense_score=dense_score,
                profile=query_profile,
                text=' '.join([text, str(payload.get('title', '')), ' '.join(payload.get('tags') or [])]),
                category=payload.get('category'),
                species=payload.get('species'),
                country=payload.get('country'),
                trust_level=payload.get('trust_level'),
            )
            candidates.append(
                RetrievedChunk(
                    text=text,
                    title=str(payload.get('title', 'Documento sin titulo')),
                    source=str(payload.get('source', 'Fuente no indicada')),
                    url=payload.get('url'),
                    category=payload.get('category'),
                    score=final_score,
                    dense_score=dense_score,
                    content_type=payload.get('content_type'),
                    document_id=payload.get('document_id'),
                    country=payload.get('country'),
                    language=payload.get('language'),
                    trust_level=payload.get('trust_level'),
                    tags=list(payload.get('tags') or []),
                    pet_id=payload.get('pet_id'),
                    pet_name=payload.get('pet_name'),
                    breed=payload.get('breed'),
                    species=payload.get('species'),
                    event_date=payload.get('event_date'),
                    event_type=payload.get('event_type'),
                )
            )

        candidates.sort(key=lambda chunk: (chunk.score, chunk.dense_score), reverse=True)
        selected = [chunk for chunk in candidates if chunk.score >= settings.rag_min_score][:result_limit]
        for index, chunk in enumerate(selected, start=1):
            chunk.citation_id = f'F{index}'

        RAG_RESULTS.labels(mode).observe(len(selected))
        candidate_top_score = candidates[0].score if candidates else 0.0
        if selected:
            retrieval_decision = 'accepted'
            confidence, reason = self._confidence(selected)
        elif candidates:
            retrieval_decision = 'low_score'
            confidence, reason = (
                'low',
                'Se encontraron candidatos, pero ninguno supero el umbral minimo de evidencia.',
            )
        else:
            retrieval_decision = 'no_evidence'
            confidence, reason = ('low', 'No se encontro evidencia documental relacionada.')
        self.last_diagnostics = RagDiagnostics(
            confidence=confidence,
            confidence_reason=reason,
            retrieved_count=len(selected),
            candidate_count=len(candidates),
            top_score=selected[0].score if selected else 0.0,
            applied_filters={
                **query_profile.filters(),
                'content_types': content_types or [],
                'pet_id': str(pet_id) if pet_id else None,
                'owner_visible_only': owner_visible_only,
            },
            urgent=query_profile.urgent,
            urgency_matches=query_profile.urgency_matches,
            retrieval_decision=retrieval_decision,
            domain_in_scope=query_profile.in_domain,
            domain_reason=query_profile.domain_reason,
            candidate_top_score=candidate_top_score,
        )
        return selected

    @staticmethod
    def _context(chunks: list[RetrievedChunk]) -> str:
        sections: list[str] = []
        for index, chunk in enumerate(chunks, start=1):
            citation = chunk.citation_id or f'F{index}'
            metadata = [citation, chunk.title, chunk.source]
            if chunk.country:
                metadata.append(f'ambito={chunk.country}')
            if chunk.pet_name:
                metadata.append(f'paciente={chunk.pet_name}')
            if chunk.breed:
                metadata.append(f'raza={chunk.breed}')
            if chunk.event_date:
                metadata.append(f'fecha={chunk.event_date}')
            sections.append(f"{' | '.join(metadata)}\n{chunk.text}")
        return '\n\n'.join(sections)

    @staticmethod
    def _urgent_instruction(profile: QueryProfile) -> str:
        if not profile.urgent:
            return ''
        return (
            'La consulta contiene posibles signos de urgencia. Empieza la respuesta indicando '
            'que debe contactarse de inmediato con una clinica veterinaria o servicio de urgencias. '
            'No retrases esa recomendacion con explicaciones largas. '
        )

    async def answer_general(
        self,
        question: str,
        *,
        history: list[dict[str, str]] | None = None,
    ) -> tuple[str, list[RetrievedChunk], bool]:
        """Answer a general question using only curated reference documents."""
        profile = analyse_query(question, scope='general')
        retrieval_query = f'{question}\nContexto conversacional: {self._history_text(history)}'
        chunks = await self.search(
            retrieval_query,
            content_types=['reference_document'],
            limit=settings.rag_top_k,
            profile=profile,
        )
        if not chunks:
            prefix = (
                'La descripcion puede corresponder a una urgencia. Contacta de inmediato con una clinica veterinaria.\n\n'
                if profile.urgent else ''
            )
            if self.last_diagnostics.retrieval_decision == 'out_of_scope':
                message = (
                    'Esta consulta no parece pertenecer al ambito veterinario de VetIA. '
                    'Puedo ayudar con salud preventiva, viajes con mascotas, vacunacion, '
                    'parasitos, nutricion e informacion clinica autorizada.'
                )
            else:
                message = (
                    'No dispongo de informacion suficientemente fiable en la base documental '
                    'para responder a esta consulta. Consulta con tu clinica veterinaria o con el '
                    'organismo oficial correspondiente.'
                )
            return prefix + message, [], False

        system_prompt = (
            'Eres un asistente documental veterinario. Responde exclusivamente con el contexto '
            'aportado. Cada afirmacion relevante debe terminar con uno o varios identificadores '
            'de fuente como [F1] o [F1, F2]. No cites una fuente si no respalda esa afirmacion. '
            'No diagnostiques ni prescribas. Si la pregunta trata de tramites o normativa, indica '
            'el ambito geografico y recuerda que debe verificarse la version vigente en la fuente oficial. '
            + self._urgent_instruction(profile)
        )
        user_prompt = (
            f'PREGUNTA ACTUAL:\n{question}\n\nCONVERSACION RECIENTE:\n{self._history_text(history)}\n\n'
            f'CONTEXTO RECUPERADO:\n{self._context(chunks)}'
        )
        answer = await self.ollama.chat(system_prompt, user_prompt)
        return answer, chunks, True

    async def answer_clinical(
        self,
        question: str,
        *,
        history: list[dict[str, str]] | None = None,
    ) -> tuple[str, list[RetrievedChunk], bool]:
        """Analyse fictitious patient records for clinic and staff users."""
        profile = analyse_query(question, scope='clinical')
        chunks = await self.search(
            f'{question}\n{self._history_text(history)}',
            content_types=['clinical_profile', 'clinical_event'],
            limit=settings.rag_clinical_top_k,
            profile=profile,
        )
        if not chunks:
            if self.last_diagnostics.retrieval_decision == 'out_of_scope':
                message = (
                    'La consulta no parece describir una busqueda clinica veterinaria. '
                    'Indica un paciente, especie, raza, sintoma, diagnostico o tipo de evento.'
                )
            else:
                message = (
                    'No se han encontrado historiales suficientemente relacionados con la consulta. '
                    'Prueba con una raza, un sintoma o un tipo de evento mas concreto.'
                )
            return message, [], False

        system_prompt = (
            'Actuas como apoyo para revisar historiales clinicos ficticios. Identifica coincidencias, '
            'recurrencias y diferencias solo a partir del contexto. Cita cada observacion con [F1], '
            '[F2] u otros identificadores disponibles. Indica cuantos pacientes y eventos aparecen '
            'en la muestra recuperada. No presentes la muestra como prevalencia real, no diagnostiques '
            'y no inventes relaciones causales. Separa hechos observados de lineas de revision.'
        )
        user_prompt = (
            f'CONSULTA CLINICA:\n{question}\n\nCONVERSACION RECIENTE:\n{self._history_text(history)}\n\n'
            f'HISTORIALES RECUPERADOS:\n{self._context(chunks)}'
        )
        answer = await self.ollama.chat(system_prompt, user_prompt)
        return answer, chunks, True

    async def answer_pet(
        self,
        question: str,
        *,
        pet_id: uuid.UUID | str,
        pet_name: str,
        structured_context: str,
        owner_visible_only: bool,
        history: list[dict[str, str]] | None = None,
    ) -> tuple[str, list[RetrievedChunk], bool]:
        """Answer about one authorised pet using SQL data and filtered vectors."""
        profile = analyse_query(question, scope='pet')
        if not profile.in_domain:
            self.last_diagnostics = RagDiagnostics(
                confidence='low',
                confidence_reason=profile.domain_reason,
                retrieved_count=0,
                candidate_count=0,
                applied_filters={**profile.filters(), 'pet_id': str(pet_id)},
                urgent=profile.urgent,
                urgency_matches=profile.urgency_matches,
                retrieval_decision='out_of_scope',
                domain_in_scope=False,
                domain_reason=profile.domain_reason,
            )
            return (
                'Esta consulta no parece estar relacionada con la mascota, su plan, sus pagos '
                'o su historial autorizado.',
                [],
                False,
            )
        try:
            chunks = await self.search(
                f'{question}\n{self._history_text(history)}',
                content_types=['clinical_profile', 'clinical_event'],
                pet_id=pet_id,
                owner_visible_only=owner_visible_only,
                limit=settings.rag_clinical_top_k,
                profile=profile,
            )
        except Exception:
            chunks = []
            self.last_diagnostics = RagDiagnostics(
                confidence='medium',
                confidence_reason='La respuesta usa datos estructurados de PostgreSQL; Qdrant no estaba disponible.',
                retrieved_count=0,
                applied_filters={'pet_id': str(pet_id), 'owner_visible_only': owner_visible_only},
                urgent=profile.urgent,
                urgency_matches=profile.urgency_matches,
            )
        record_source = RetrievedChunk(
            text=structured_context,
            title=f'Ficha, plan e historial autorizado de {pet_name}',
            source='Datos ficticios de GamuCare AI',
            url=None,
            category='pet_record',
            score=1.0,
            dense_score=1.0,
            citation_id='F0',
            content_type='pet_record',
            pet_id=str(pet_id),
            pet_name=pet_name,
            trust_level='internal',
        )
        sources = [record_source, *chunks]
        if not chunks:
            self.last_diagnostics.confidence = 'medium'
            self.last_diagnostics.confidence_reason = (
                'La respuesta se apoya en datos estructurados autorizados de PostgreSQL; '
                'no se recuperaron fragmentos adicionales del indice vectorial.'
            )
        system_prompt = (
            'Eres el asistente de una aplicacion veterinaria. Responde solo sobre la mascota indicada '
            'y exclusivamente con los datos aportados. Cita la ficha estructurada como [F0] y los '
            'fragmentos del historial como [F1], [F2], etc. Puedes resumir historial, plan, pagos, '
            'prestaciones y avisos. No conviertas antecedentes en un diagnostico nuevo, no prescribas '
            'y no inventes datos. Cuando sea necesaria una valoracion clinica, recomienda contactar '
            'con la clinica. ' + self._urgent_instruction(profile)
        )
        user_prompt = (
            f'PREGUNTA SOBRE {pet_name}:\n{question}\n\nCONVERSACION RECIENTE:\n{self._history_text(history)}\n\n'
            f'F0 | DATOS ESTRUCTURADOS AUTORIZADOS:\n{structured_context}\n\n'
            f'FRAGMENTOS DEL HISTORIAL:\n{self._context(chunks) if chunks else "Sin fragmentos adicionales."}'
        )
        answer = await self.ollama.chat(system_prompt, user_prompt)
        return answer, sources, True

    async def explain_alert(
        self,
        *,
        pet_name: str,
        species: str,
        breed: str,
        rule_title: str,
        evidence: dict,
        rule_description: str | None = None,
        rule_source: str | None = None,
        rule_source_url: str | None = None,
    ) -> tuple[str | None, list[RetrievedChunk]]:
        """Ground a deterministic alert with similar records and reference material."""
        query = (
            f'{rule_title}. {rule_description or ""} Paciente {species}, raza {breed}. '
            f'Fuente de la regla: {rule_source or "no indicada"}. Datos observados: {evidence}. '
            'Buscar antecedentes similares y recomendaciones preventivas.'
        )
        profile = analyse_query(query, scope='mixed')
        chunks = await self.search(
            query,
            content_types=['clinical_profile', 'clinical_event', 'reference_document'],
            limit=settings.rag_alert_top_k,
            profile=profile,
        )
        if not chunks:
            return None, []

        system_prompt = (
            'Redacta una explicacion breve para un aviso preventivo generado por una regla determinista. '
            'Usa exclusivamente el contexto y cita las fuentes con [F1], [F2], etc. Explica por que '
            'conviene revisar el caso, menciona antecedentes similares o documentacion relacionada y '
            'deja claro que no es un diagnostico. No prescribas.'
        )
        user_prompt = (
            f'PACIENTE: {pet_name}\nESPECIE: {species}\nRAZA: {breed}\nAVISO: {rule_title}\n'
            f'DESCRIPCION: {rule_description or "No indicada"}\nFUENTE DE LA REGLA: {rule_source or "No indicada"}\n'
            f'URL: {rule_source_url or "No indicada"}\nEVIDENCIA: {evidence}\n\nCONTEXTO RAG:\n{self._context(chunks)}'
        )
        explanation = await self.ollama.chat(system_prompt, user_prompt)
        return explanation, chunks

    async def answer(
        self,
        question: str,
        *,
        scope: str = 'general',
        history: list[dict[str, str]] | None = None,
    ) -> tuple[str, list[RetrievedChunk], bool]:
        """Dispatcher used by the chat endpoint."""
        if scope == 'clinical':
            return await self.answer_clinical(question, history=history)
        return await self.answer_general(question, history=history)
