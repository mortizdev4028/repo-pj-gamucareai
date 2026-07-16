"""Ingest trusted documents and fictitious clinical records into Qdrant.

Files may begin with a small YAML-like front matter block delimited by `---`.
Clinical points are built from PostgreSQL and contain no owner contact details.
The collection is rebuilt atomically enough for the local MVP: points are first
prepared, then the old collection is replaced and populated in batches.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
import uuid

from bs4 import BeautifulSoup
from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, FieldCondition, Filter, FilterSelector, MatchValue, PointStruct, VectorParams, PayloadSchemaType
)
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import SessionLocal
from app.models import Pet, RagDocument
from app.services.ollama import OllamaClient
from app.services.risk_engine import age_years

settings = get_settings()


def _sidecar_metadata(path: Path) -> dict[str, str]:
    """Read metadata written next to downloaded external documents."""
    sidecar = path.with_name(f'{path.name}.meta.json')
    if not sidecar.exists():
        return {}
    raw = json.loads(sidecar.read_text(encoding='utf-8'))
    metadata = raw.get('metadata') if isinstance(raw, dict) else None
    if not isinstance(metadata, dict):
        metadata = raw if isinstance(raw, dict) else {}
    return {
        str(key): ', '.join(str(item) for item in value) if isinstance(value, list) else str(value)
        for key, value in metadata.items()
        if value is not None
    }


def _text_from_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = [(page.extract_text() or '').strip() for page in reader.pages]
    return "\n\n".join(page for page in pages if page)


def _text_from_html(path: Path) -> str:
    soup = BeautifulSoup(path.read_text(encoding='utf-8', errors='ignore'), 'html.parser')
    for element in soup(['script', 'style', 'noscript', 'svg']):
        element.decompose()
    return "\n".join(
        line.strip() for line in soup.get_text("\n").splitlines() if line.strip()
    )


def parse_document(path: Path) -> tuple[dict[str, str], str]:
    """Extract metadata and text from Markdown, text, PDF or HTML files."""
    suffix = path.suffix.casefold()
    metadata = _sidecar_metadata(path)
    if suffix == '.pdf':
        body = _text_from_pdf(path)
    elif suffix in {'.html', '.htm'}:
        body = _text_from_html(path)
    else:
        raw = path.read_text(encoding='utf-8', errors='ignore')
        body = raw
        if suffix == '.md' and raw.startswith('---'):
            try:
                _, front, body = raw.split('---', 2)
            except ValueError:
                front = ''
            for line in front.splitlines():
                if ':' in line:
                    key, value = line.split(':', 1)
                    metadata.setdefault(key.strip(), value.strip().strip('"'))
    return metadata, body.strip()


def chunks(text: str, max_chars: int = 1250, overlap_chars: int = 180) -> list[str]:
    """Split Markdown by headings and paragraphs with a small contextual overlap.

    The previous implementation could separate a paragraph from its heading. This
    version repeats the active heading and the end of the previous chunk, which
    improves retrieval while keeping chunks readable in the source panel.
    """
    blocks: list[str] = []
    active_heading = ''
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('#'):
            active_heading = line.lstrip('#').strip()
            continue
        block = f'{active_heading}\n{line}'.strip() if active_heading else line
        blocks.append(block)

    result: list[str] = []
    current = ''
    for block in blocks:
        if current and len(current) + len(block) + 2 > max_chars:
            result.append(current)
            overlap = current[-overlap_chars:].lstrip() if overlap_chars else ''
            current = f'{overlap}\n\n{block}'.strip()
        else:
            current = f'{current}\n\n{block}'.strip()
    if current:
        result.append(current)
    return result


def _metadata_list(value: str | None) -> list[str]:
    """Parse comma-separated front matter values into clean metadata lists."""
    if not value:
        return []
    return [item.strip() for item in value.split(',') if item.strip()]


def _clinical_profile_text(pet: Pet) -> str:
    """Create a searchable patient summary without owner personal data."""
    return '\n'.join(
        [
            f'Paciente: {pet.name}.',
            f'Especie: {pet.species}. Raza: {pet.breed}.',
            f'Edad: {age_years(pet.birth_date)} anos. Sexo: {pet.sex}.',
            f'Peso actual: {float(pet.weight_kg):.1f} kg. Esterilizado: {"si" if pet.neutered else "no"}.',
            f'Alergias registradas: {pet.allergies or "ninguna"}.',
            f'Antecedentes o problemas cronicos: {pet.chronic_conditions or "ninguno"}.',
        ]
    )


def _clinical_event_text(pet: Pet, event: Any) -> str:
    """Create a complete, compact representation of one clinical event."""
    parts = [
        f'Paciente: {pet.name}. Especie: {pet.species}. Raza: {pet.breed}.',
        f'Fecha del evento: {event.event_date.date().isoformat()}. Tipo: {event.event_type}.',
        f'Titulo: {event.title}.',
        f'Descripcion: {event.description}.',
    ]
    if event.diagnosis:
        parts.append(f'Diagnostico registrado: {event.diagnosis}.')
    if event.treatment:
        parts.append(f'Tratamiento registrado: {event.treatment}.')
    if event.weight_kg is not None:
        parts.append(f'Peso en la visita: {float(event.weight_kg):.1f} kg.')
    if pet.allergies:
        parts.append(f'Alergias conocidas: {pet.allergies}.')
    if pet.chronic_conditions:
        parts.append(f'Antecedentes: {pet.chronic_conditions}.')
    return '\n'.join(parts)


def _point_payload(text: str, **metadata: Any) -> dict[str, Any]:
    """Build a payload with a common text field and serialisable metadata."""
    return {'text': text, **metadata}


async def _embed_entries(ollama: OllamaClient, entries: list[dict[str, Any]]) -> tuple[list[PointStruct], int | None]:
    """Embed entries in batches and convert them into Qdrant points."""
    points: list[PointStruct] = []
    vector_size: int | None = None
    batch_size = 24
    for start in range(0, len(entries), batch_size):
        batch = entries[start:start + batch_size]
        vectors = await ollama.embed_many([entry['text'] for entry in batch])
        for entry, vector in zip(batch, vectors, strict=True):
            vector_size = vector_size or len(vector)
            points.append(
                PointStruct(
                    id=entry['point_id'],
                    vector=vector,
                    payload=entry['payload'],
                )
            )
        print(f'Embeddings generados: {min(start + batch_size, len(entries))}/{len(entries)}')
    return points, vector_size


async def upsert_pet(pet_id: uuid.UUID | str) -> dict[str, int]:
    """Replace the vectors for one patient without rebuilding the collection."""
    db = SessionLocal()
    try:
        pet = db.scalar(
            select(Pet)
            .options(selectinload(Pet.clinical_events))
            .where(Pet.id == uuid.UUID(str(pet_id)))
        )
        if pet is None:
            return {'profiles': 0, 'events': 0}

        ollama = OllamaClient()
        qdrant = QdrantClient(url=settings.qdrant_url, timeout=60)
        if not qdrant.collection_exists(settings.qdrant_collection):
            return {'profiles': 0, 'events': 0}

        entries: list[dict[str, Any]] = []
        profile_text = _clinical_profile_text(pet)
        entries.append(
            {
                'point_id': str(uuid.uuid5(uuid.NAMESPACE_URL, f'clinical-profile:{pet.id}')),
                'text': profile_text,
                'payload': _point_payload(
                    profile_text,
                    content_type='clinical_profile',
                    title=f'Ficha clinica de {pet.name}',
                    source='Historial clinico ficticio',
                    url=None,
                    category='clinical_profile',
                    pet_id=str(pet.id),
                    pet_external_id=pet.external_id,
                    pet_name=pet.name,
                    species=pet.species,
                    breed=pet.breed,
                    age_years=age_years(pet.birth_date),
                    is_active=pet.is_active,
                    visible_to_owner=True,
                    language='es',
                    trust_level='internal',
                    tags=['ficha', pet.species, pet.breed],
                ),
            }
        )
        for event in pet.clinical_events:
            event_text = _clinical_event_text(pet, event)
            entries.append(
                {
                    'point_id': str(uuid.uuid5(uuid.NAMESPACE_URL, f'clinical-event:{event.id}')),
                    'text': event_text,
                    'payload': _point_payload(
                        event_text,
                        content_type='clinical_event',
                        title=f'{pet.name} - {event.title}',
                        source='Historial clinico ficticio',
                        url=None,
                        category='clinical_history',
                        pet_id=str(pet.id),
                        pet_external_id=pet.external_id,
                        pet_name=pet.name,
                        species=pet.species,
                        breed=pet.breed,
                        event_id=str(event.id),
                        event_date=event.event_date.date().isoformat(),
                        event_type=event.event_type,
                        visible_to_owner=event.visible_to_owner,
                        language='es',
                        trust_level='internal',
                        tags=['historial', event.event_type, pet.species, pet.breed],
                    ),
                }
            )

        points, _ = await _embed_entries(ollama, entries)
        qdrant.delete(
            collection_name=settings.qdrant_collection,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[FieldCondition(key='pet_id', match=MatchValue(value=str(pet.id)))]
                )
            ),
            wait=True,
        )
        qdrant.upsert(settings.qdrant_collection, points=points, wait=True)
        return {'profiles': 1, 'events': len(pet.clinical_events)}
    finally:
        db.close()


async def ingest() -> None:
    """Rebuild the Qdrant collection with documents and clinical histories."""
    source_dirs = [Path(settings.rag_documents_path), Path(settings.rag_external_documents_path)]
    supported = {'.md', '.txt', '.pdf', '.html', '.htm'}
    files = sorted(
        path
        for source_dir in source_dirs
        if source_dir.exists()
        for path in source_dir.rglob('*')
        if path.is_file()
        and path.suffix.casefold() in supported
        and path.name.casefold() != 'readme.md'
    )

    ollama = OllamaClient()
    qdrant = QdrantClient(url=settings.qdrant_url, timeout=60)
    db = SessionLocal()
    entries: list[dict[str, Any]] = []
    document_chunks = 0
    clinical_profiles = 0
    clinical_events = 0

    try:
        for path in files:
            metadata, body = parse_document(path)
            if len(body) < 80:
                print(f'Documento omitido por falta de texto extraible: {path}')
                continue
            file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            document = db.scalar(select(RagDocument).where(RagDocument.file_hash == file_hash))
            if document is None:
                document = RagDocument(
                    title=metadata.get('title', path.stem),
                    source_name=metadata.get('source', 'Fuente de demostracion'),
                    source_url=metadata.get('url') or None,
                    document_date=date.fromisoformat(metadata['date']) if metadata.get('date') else None,
                    country=metadata.get('country') or None,
                    category=metadata.get('category', 'general'),
                    language=metadata.get('language', 'es'),
                    audience=metadata.get('audience', 'owner'),
                    source_type=metadata.get('source_type', 'guideline'),
                    trust_level=metadata.get('trust_level', 'official'),
                    tags=_metadata_list(metadata.get('tags')),
                    last_reviewed_at=date.fromisoformat(metadata['last_reviewed']) if metadata.get('last_reviewed') else None,
                    file_hash=file_hash,
                    ingestion_status='processing',
                )
                db.add(document)
                db.flush()
            else:
                document.title = metadata.get('title', path.stem)
                document.source_name = metadata.get('source', 'Fuente de demostracion')
                document.source_url = metadata.get('url') or None
                document.document_date = date.fromisoformat(metadata['date']) if metadata.get('date') else None
                document.country = metadata.get('country') or None
                document.category = metadata.get('category', 'general')
                document.language = metadata.get('language', 'es')
                document.audience = metadata.get('audience', 'owner')
                document.source_type = metadata.get('source_type', 'guideline')
                document.trust_level = metadata.get('trust_level', 'official')
                document.tags = _metadata_list(metadata.get('tags'))
                document.last_reviewed_at = date.fromisoformat(metadata['last_reviewed']) if metadata.get('last_reviewed') else None
                document.ingestion_status = 'processing'

            for index, chunk in enumerate(chunks(body)):
                point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f'document:{file_hash}:{index}'))
                payload = _point_payload(
                    chunk,
                    content_type='reference_document',
                    document_id=str(document.id),
                    chunk_index=index,
                    title=document.title,
                    source=document.source_name,
                    url=document.source_url,
                    category=document.category,
                    country=document.country,
                    language=document.language,
                    audience=document.audience,
                    source_type=document.source_type,
                    trust_level=document.trust_level,
                    tags=document.tags or [],
                    document_date=document.document_date.isoformat() if document.document_date else None,
                    last_reviewed=document.last_reviewed_at.isoformat() if document.last_reviewed_at else None,
                )
                entries.append({'point_id': point_id, 'text': chunk, 'payload': payload})
                document_chunks += 1
            document.ingestion_status = 'completed'
            document.ingested_at = datetime.now(timezone.utc)
            db.commit()

        pets = db.scalars(
            select(Pet).options(selectinload(Pet.clinical_events)).order_by(Pet.name)
        ).all()
        for pet in pets:
            profile_text = _clinical_profile_text(pet)
            profile_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f'clinical-profile:{pet.id}'))
            profile_payload = _point_payload(
                profile_text,
                content_type='clinical_profile',
                title=f'Ficha clinica de {pet.name}',
                source='Historial clinico ficticio',
                url=None,
                category='clinical_profile',
                pet_id=str(pet.id),
                pet_external_id=pet.external_id,
                pet_name=pet.name,
                species=pet.species,
                breed=pet.breed,
                age_years=age_years(pet.birth_date),
                is_active=pet.is_active,
                visible_to_owner=True,
                language='es',
                trust_level='internal',
                tags=['ficha', pet.species, pet.breed],
            )
            entries.append({'point_id': profile_id, 'text': profile_text, 'payload': profile_payload})
            clinical_profiles += 1

            for event in pet.clinical_events:
                event_text = _clinical_event_text(pet, event)
                event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f'clinical-event:{event.id}'))
                event_payload = _point_payload(
                    event_text,
                    content_type='clinical_event',
                    title=f'{pet.name} - {event.title}',
                    source='Historial clinico ficticio',
                    url=None,
                    category='clinical_history',
                    pet_id=str(pet.id),
                    pet_external_id=pet.external_id,
                    pet_name=pet.name,
                    species=pet.species,
                    breed=pet.breed,
                    event_id=str(event.id),
                    event_date=event.event_date.date().isoformat(),
                    event_type=event.event_type,
                    visible_to_owner=event.visible_to_owner,
                    language='es',
                    trust_level='internal',
                    tags=['historial', event.event_type, pet.species, pet.breed],
                )
                entries.append({'point_id': event_id, 'text': event_text, 'payload': event_payload})
                clinical_events += 1

        if not entries:
            print('No hay documentos ni historiales que indexar')
            return

        points, vector_size = await _embed_entries(ollama, entries)
        if vector_size is None:
            return
        if qdrant.collection_exists(settings.qdrant_collection):
            qdrant.delete_collection(settings.qdrant_collection)
        qdrant.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        for start in range(0, len(points), 64):
            qdrant.upsert(settings.qdrant_collection, points=points[start:start + 64], wait=True)
        for field_name in ('content_type', 'category', 'country', 'species', 'pet_id', 'visible_to_owner', 'trust_level'):
            try:
                qdrant.create_payload_index(
                    collection_name=settings.qdrant_collection,
                    field_name=field_name,
                    field_schema=PayloadSchemaType.KEYWORD,
                    wait=True,
                )
            except Exception:
                # An index is optional for the local MVP; retrieval still works without it.
                pass

        print(
            'Ingesta completada: '
            f'{len(files)} documentos ({document_chunks} fragmentos), '
            f'{clinical_profiles} fichas y {clinical_events} eventos clinicos.'
        )
    finally:
        db.close()


if __name__ == '__main__':
    asyncio.run(ingest())
