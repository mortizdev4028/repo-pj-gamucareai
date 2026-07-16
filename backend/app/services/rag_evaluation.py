"""Repeatable RAG evaluation using a versioned, fictitious test dataset."""
from __future__ import annotations

import json
from pathlib import Path
import statistics
import time
from typing import Any

from app.config import get_settings
from app.services.rag import RagService, RetrievedChunk

settings = get_settings()


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percentile)))
    return ordered[index]


def _rank_of_match(case: dict[str, Any], chunks: list[RetrievedChunk]) -> int | None:
    expected_categories = set(case.get('expected_categories') or [])
    expected_sources = [value.casefold() for value in case.get('expected_sources') or []]
    expected_pets = {value.casefold() for value in case.get('expected_pet_names') or []}
    expected_events = {value.casefold() for value in case.get('expected_event_types') or []}
    for rank, chunk in enumerate(chunks, start=1):
        source = chunk.source.casefold()
        matched = (
            (expected_categories and chunk.category in expected_categories)
            or (expected_sources and any(value in source for value in expected_sources))
            or (expected_pets and (chunk.pet_name or '').casefold() in expected_pets)
            or (expected_events and (chunk.event_type or '').casefold() in expected_events)
        )
        if matched:
            return rank
    return None


def _case_matches(case: dict[str, Any], chunks: list[RetrievedChunk]) -> dict[str, bool]:
    categories = {chunk.category for chunk in chunks if chunk.category}
    sources = ' '.join(chunk.source.casefold() for chunk in chunks)
    pets = {(chunk.pet_name or '').casefold() for chunk in chunks}
    events = {(chunk.event_type or '').casefold() for chunk in chunks}
    expected_categories = set(case.get('expected_categories') or [])
    expected_sources = [value.casefold() for value in case.get('expected_sources') or []]
    expected_pets = {value.casefold() for value in case.get('expected_pet_names') or []}
    expected_events = {value.casefold() for value in case.get('expected_event_types') or []}
    return {
        'category_hit': not expected_categories or bool(categories & expected_categories),
        'source_hit': not expected_sources or any(value in sources for value in expected_sources),
        'pet_hit': not expected_pets or bool(pets & expected_pets),
        'event_hit': not expected_events or bool(events & expected_events),
    }


class RagEvaluator:
    """Evaluate retrieval and optional generation without external SaaS services."""

    def __init__(self, dataset_path: str | Path | None = None) -> None:
        self.dataset_path = Path(dataset_path or settings.rag_evaluation_dataset)

    def load_cases(self) -> list[dict[str, Any]]:
        return json.loads(self.dataset_path.read_text(encoding='utf-8'))

    async def run(self, *, with_generation: bool = False) -> dict[str, Any]:
        cases = self.load_cases()
        details: list[dict[str, Any]] = []
        latencies: list[float] = []
        reciprocal_ranks: list[float] = []
        answerable_hits = 0
        no_context_hits = 0
        citation_hits = 0
        grounded_hits = 0
        category_hits = 0
        source_hits = 0
        pet_hits = 0
        event_hits = 0
        rejection_reasons: dict[str, int] = {}
        category_total = sum(1 for case in cases if case['answerable'] and case.get('expected_categories'))
        source_total = sum(1 for case in cases if case['answerable'] and case.get('expected_sources'))
        pet_total = sum(1 for case in cases if case['answerable'] and case.get('expected_pet_names'))
        event_total = sum(1 for case in cases if case['answerable'] and case.get('expected_event_types'))
        answerable_total = sum(1 for case in cases if case['answerable'])
        no_context_total = len(cases) - answerable_total

        for case in cases:
            service = RagService()
            started = time.perf_counter()
            content_types = (
                ['clinical_profile', 'clinical_event']
                if case['scope'] == 'clinical'
                else ['reference_document']
            )
            limit = settings.rag_clinical_top_k if case['scope'] == 'clinical' else settings.rag_top_k
            chunks = await service.search(case['question'], content_types=content_types, limit=limit)
            elapsed_ms = (time.perf_counter() - started) * 1000
            latencies.append(elapsed_ms)
            rank = _rank_of_match(case, chunks)
            matches = _case_matches(case, chunks)
            is_answerable = bool(chunks)
            diagnostics = service.last_diagnostics.as_dict()
            decision = str(diagnostics.get('retrieval_decision') or 'unknown')
            if not is_answerable:
                rejection_reasons[decision] = rejection_reasons.get(decision, 0) + 1

            if case['answerable']:
                if rank is not None:
                    answerable_hits += 1
                    reciprocal_ranks.append(1 / rank)
                else:
                    reciprocal_ranks.append(0.0)
                if case.get('expected_categories'):
                    category_hits += int(matches['category_hit'])
                if case.get('expected_sources'):
                    source_hits += int(matches['source_hit'])
                if case.get('expected_pet_names'):
                    pet_hits += int(matches['pet_hit'])
                if case.get('expected_event_types'):
                    event_hits += int(matches['event_hit'])
            else:
                no_context_hits += int(not is_answerable)

            generated_answer = None
            if with_generation:
                generated_answer, _, grounded = await service.answer(
                    case['question'], scope=case['scope']
                )
                grounded_hits += int(grounded == case['answerable'])
                citation_hits += int((not case['answerable']) or ('[F' in generated_answer))

            details.append({
                'id': case['id'],
                'scope': case['scope'],
                'question': case['question'],
                'expected_answerable': case['answerable'],
                'retrieved': len(chunks),
                'top_score': round(chunks[0].score, 4) if chunks else 0.0,
                'candidate_top_score': float(diagnostics.get('candidate_top_score') or 0.0),
                'retrieval_decision': decision,
                'domain_in_scope': bool(diagnostics.get('domain_in_scope', True)),
                'domain_reason': str(diagnostics.get('domain_reason') or ''),
                'first_relevant_rank': rank,
                'passed': (rank is not None) if case['answerable'] else not is_answerable,
                'matches': matches,
                'latency_ms': round(elapsed_ms, 1),
                'sources': [
                    {
                        'title': chunk.title,
                        'source': chunk.source,
                        'category': chunk.category,
                        'pet_name': chunk.pet_name,
                        'score': round(chunk.score, 4),
                    }
                    for chunk in chunks[:5]
                ],
                'answer': generated_answer,
            })

        retrieval_hit_rate = answerable_hits / answerable_total if answerable_total else 0.0
        metrics: dict[str, Any] = {
            'dataset': self.dataset_path.stem,
            'cases_total': len(cases),
            'answerable_cases': answerable_total,
            'no_context_cases': no_context_total,
            'retrieval_hit_rate': round(retrieval_hit_rate, 4),
            'mrr': round(statistics.mean(reciprocal_ranks), 4) if reciprocal_ranks else 0.0,
            'category_hit_rate': round(category_hits / category_total, 4) if category_total else 0.0,
            'source_hit_rate': round(source_hits / source_total, 4) if source_total else 0.0,
            'pet_hit_rate': round(pet_hits / pet_total, 4) if pet_total else 0.0,
            'event_type_hit_rate': round(event_hits / event_total, 4) if event_total else 0.0,
            'no_context_accuracy': round(no_context_hits / no_context_total, 4) if no_context_total else 1.0,
            'latency_p50_ms': round(_percentile(latencies, 0.50), 1),
            'latency_p95_ms': round(_percentile(latencies, 0.95), 1),
            'average_latency_ms': round(statistics.mean(latencies), 1) if latencies else 0.0,
            'passed_cases': sum(1 for item in details if item['passed']),
            'pass_rate': round(sum(1 for item in details if item['passed']) / len(details), 4) if details else 0.0,
            'generation_enabled': with_generation,
            'rejection_reasons': rejection_reasons,
        }
        if with_generation:
            metrics.update({
                'citation_presence_rate': round(citation_hits / len(cases), 4) if cases else 0.0,
                'grounded_decision_accuracy': round(grounded_hits / len(cases), 4) if cases else 0.0,
                'faithfulness_note': 'La fidelidad semantica requiere revision humana; no se infiere solo por presencia de citas.',
            })
        return {'metrics': metrics, 'details': details}
