"""Tests for deterministic RAG routing, chunking and evaluation helpers."""
from app.rag.ingest import chunks
from app.services.rag_intelligence import analyse_query, lexical_overlap, rerank_score


def test_query_analysis_detects_travel_dog_and_spain() -> None:
    profile = analyse_query('Que necesita mi perro para viajar desde España a Francia?')
    assert 'travel' in profile.categories
    assert 'dog' in profile.species
    assert 'ES' in profile.countries
    assert 'EU' in profile.countries


def test_query_analysis_detects_possible_emergency() -> None:
    profile = analyse_query('Mi gato no puede orinar y esta muy inquieto')
    assert profile.urgent is True
    assert 'no puede orinar' in profile.urgency_matches


def test_query_analysis_does_not_mark_normal_question_as_urgent() -> None:
    profile = analyse_query('Que vacunas necesita un cachorro?')
    assert profile.urgent is False


def test_lexical_overlap_ignores_unmatched_terms() -> None:
    score = lexical_overlap(['vacuna', 'rabia', 'pasaporte'], 'Vacuna de rabia vigente')
    assert score == 2 / 3


def test_reranking_rewards_exact_category_and_official_source() -> None:
    profile = analyse_query('vacuna de rabia para viajar')
    baseline = rerank_score(
        dense_score=0.6,
        profile=profile,
        text='contenido general',
        category='general',
        species=None,
        country=None,
        trust_level='internal',
    )
    boosted = rerank_score(
        dense_score=0.6,
        profile=profile,
        text='vacuna de rabia para viajar por Europa',
        category='vaccination',
        species=None,
        country='EU',
        trust_level='official',
    )
    assert boosted > baseline


def test_markdown_chunks_keep_heading_context() -> None:
    text = '# Vacunacion\nParrafo uno.\n\nParrafo dos.\n# Viajes\nMicrochip y pasaporte.'
    result = chunks(text, max_chars=55, overlap_chars=10)
    assert len(result) >= 2
    assert any('Vacunacion' in item for item in result)
    assert any('Viajes' in item for item in result)


def test_domain_gate_rejects_general_knowledge_question() -> None:
    profile = analyse_query('Cual es la capital de Australia?', scope='general')
    assert profile.in_domain is False
    assert 'general_knowledge' in profile.domain_negative_matches


def test_domain_gate_rejects_computing_history_query() -> None:
    profile = analyse_query(
        'Busca historiales sobre reparacion de placas base de ordenadores',
        scope='clinical',
    )
    assert profile.in_domain is False
    assert 'computing' in profile.domain_negative_matches


def test_domain_gate_allows_pet_plan_and_payment_question() -> None:
    profile = analyse_query('Cuanto me queda por pagar del plan?', scope='pet')
    assert profile.in_domain is True


def test_veterinary_evidence_overrides_incidental_computing_term() -> None:
    profile = analyse_query('Mi gato ha mordido el cable del ordenador, que hago?', scope='general')
    assert profile.in_domain is True


import pytest

from app.services.rag import RagService


@pytest.mark.asyncio
async def test_out_of_scope_query_is_rejected_before_embedding() -> None:
    class FailingOllama:
        async def embed(self, _text: str):
            raise AssertionError('No debe generarse un embedding para consultas fuera de dominio')

    service = RagService()
    service.ollama = FailingOllama()
    chunks_found = await service.search(
        'Cual es la capital de Australia?',
        content_types=['reference_document'],
    )
    assert chunks_found == []
    assert service.last_diagnostics.retrieval_decision == 'out_of_scope'
    assert service.last_diagnostics.domain_in_scope is False
