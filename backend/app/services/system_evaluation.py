"""Formal, repeatable evaluation of the GamuCare MVP.

The evaluator combines deterministic acceptance criteria, preventive-alert
cases, security checks, the existing VetIA retrieval dataset, automated tests
and a small API latency benchmark. Results are designed to be repeatable and
suitable as evidence for the master's project report.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any
import uuid
import xml.etree.ElementTree as ET

import httpx
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import validate_password_policy
from app.models import (
    ClinicalEvent,
    HealthPlan,
    Owner,
    Pet,
    PetPlanSubscription,
    RagDocument,
    RiskAlert,
    RiskRule,
    User,
)
from app.services.audit import sanitize_mapping
from app.services.rag_evaluation import RagEvaluator
from app.services.risk_engine import matches
from app.version import APP_VERSION

settings = get_settings()


def _percent(numerator: int, denominator: int) -> float:
    return round((numerator / denominator) * 100, 2) if denominator else 0.0


class SystemEvaluator:
    """Run the versioned quality suite and return a serialisable report."""

    def __init__(self) -> None:
        self.acceptance_path = Path(settings.system_acceptance_dataset)
        self.alert_path = Path(settings.alert_evaluation_dataset)
        self.reports_path = Path(settings.quality_reports_path)

    def load_acceptance_criteria(self) -> list[dict[str, Any]]:
        return json.loads(self.acceptance_path.read_text(encoding='utf-8'))['criteria']

    def load_alert_cases(self) -> dict[str, Any]:
        return json.loads(self.alert_path.read_text(encoding='utf-8'))

    def evaluate_acceptance(self, db: Session) -> dict[str, Any]:
        """Evaluate business and data-integrity criteria against PostgreSQL."""
        inspector = inspect(db.get_bind())
        table_names = set(inspector.get_table_names())
        roles = set(db.scalars(select(User.role).distinct()).all())
        active_owners = list(db.scalars(select(Owner).where(Owner.is_active.is_(True))).all())
        plans_species = set(db.scalars(select(HealthPlan.species).where(HealthPlan.is_active.is_(True))).all())
        subscriptions = list(db.scalars(select(PetPlanSubscription)).all())
        sourced_rules = list(db.scalars(select(RiskRule).where(RiskRule.is_active.is_(True))).all())
        duplicate_alerts = db.execute(
            select(RiskAlert.pet_id, RiskAlert.rule_code, func.count(RiskAlert.id))
            .where(RiskAlert.status.in_(['new', 'reviewed']))
            .group_by(RiskAlert.pet_id, RiskAlert.rule_code)
            .having(func.count(RiskAlert.id) > 1)
        ).all()

        checks: dict[str, tuple[bool, str]] = {
            'roles_present': ({'clinic', 'staff', 'owner', 'technical'}.issubset(roles), f'roles={sorted(roles)}'),
            'owner_accounts_linked': (
                bool(active_owners) and all(owner.user_id is not None for owner in active_owners),
                f'{sum(owner.user_id is not None for owner in active_owners)}/{len(active_owners)} propietarios enlazados',
            ),
            'active_pets_present': (
                (count := int(db.scalar(select(func.count(Pet.id)).where(Pet.is_active.is_(True))) or 0)) > 0,
                f'{count} mascotas activas',
            ),
            'clinical_history_present': (
                (count := int(db.scalar(select(func.count(ClinicalEvent.id))) or 0)) > 0,
                f'{count} eventos clinicos',
            ),
            'plans_for_both_species': ({'dog', 'cat'}.issubset(plans_species), f'especies={sorted(plans_species)}'),
            'active_subscriptions_present': (
                any(item.status in {'active', 'expiring'} for item in subscriptions),
                f'{sum(item.status in {"active", "expiring"} for item in subscriptions)} suscripciones vigentes',
            ),
            'installments_consistent': (
                all(0 <= item.installments_paid <= item.installments_total <= 12 for item in subscriptions),
                f'{len(subscriptions)} suscripciones revisadas',
            ),
            'risk_rules_sourced': (
                bool(sourced_rules) and all(
                    bool(rule.source)
                    and (bool(rule.source_url) or rule.source.casefold().startswith('regla operativa interna'))
                    for rule in sourced_rules
                ),
                f'{sum(bool(rule.source) and (bool(rule.source_url) or rule.source.casefold().startswith("regla operativa interna")) for rule in sourced_rules)}/{len(sourced_rules)} reglas trazables',
            ),
            'no_duplicate_active_alerts': (not duplicate_alerts, f'{len(duplicate_alerts)} duplicados activos'),
            'rag_documents_ingested': (
                (count := int(db.scalar(select(func.count(RagDocument.id)).where(RagDocument.ingestion_status == 'completed')) or 0)) > 0,
                f'{count} documentos completados',
            ),
            'chat_sessions_traceable': (
                'chat_sessions' in table_names and {'user_id', 'pet_id'}.issubset({c['name'] for c in inspector.get_columns('chat_sessions')}),
                'columnas user_id y pet_id disponibles',
            ),
            'password_policy_enabled': (settings.password_min_length >= 12, f'minimo={settings.password_min_length}'),
            'lockout_enabled': (
                settings.max_failed_login_attempts > 0 and settings.login_lock_minutes > 0,
                f'{settings.max_failed_login_attempts} intentos / {settings.login_lock_minutes} min',
            ),
            'jwt_secret_not_default': (
                settings.jwt_secret != 'change-this-local-secret-before-production' and len(settings.jwt_secret) >= 32,
                f'longitud={len(settings.jwt_secret)}',
            ),
            'audit_table_available': ('audit_logs' in table_names, 'tabla audit_logs'),
            'wakyma_traceability_available': (
                {'import_batches', 'import_batch_items'}.issubset(table_names),
                'tablas de lotes y registros',
            ),
        }

        results = []
        for criterion in self.load_acceptance_criteria():
            passed, evidence = checks.get(criterion['check'], (False, 'Comprobacion no implementada'))
            results.append({**criterion, 'passed': bool(passed), 'evidence': evidence})
        passed = sum(item['passed'] for item in results)
        return {
            'dataset': self.acceptance_path.stem,
            'total': len(results),
            'passed': passed,
            'failed': len(results) - passed,
            'pass_rate': round(passed / len(results), 4) if results else 0.0,
            'cases': results,
        }

    def evaluate_security(self) -> dict[str, Any]:
        """Check security controls without exposing secret values."""
        redacted = sanitize_mapping({
            'password': 'NeverStoreThis',
            'token_hash': 'abcdef',
            'email': 'owner@example.test',
            'diagnosis': 'dato clinico',
        })
        checks = [
            {
                'id': 'SEC-001',
                'description': 'Politica de contraseña fuerte',
                'passed': validate_password_policy('ClaveSegura2026!', email='owner@example.test') == [],
            },
            {
                'id': 'SEC-002',
                'description': 'Secreto JWT no predeterminado',
                'passed': settings.jwt_secret != 'change-this-local-secret-before-production' and len(settings.jwt_secret) >= 32,
            },
            {
                'id': 'SEC-003',
                'description': 'Bloqueo de cuenta configurado',
                'passed': settings.max_failed_login_attempts > 0 and settings.login_lock_minutes > 0,
            },
            {
                'id': 'SEC-004',
                'description': 'Token de acceso de corta duracion',
                'passed': 1 <= settings.access_token_expire_minutes <= 60,
            },
            {
                'id': 'SEC-005',
                'description': 'Redaccion de credenciales y datos clinicos',
                'passed': redacted['password'] == '[REDACTED]'
                and redacted['token_hash'] == '[REDACTED]'
                and redacted['diagnosis'] == '[CLINICAL DATA REDACTED]',
            },
        ]
        passed = sum(item['passed'] for item in checks)
        return {
            'total': len(checks),
            'passed': passed,
            'failed': len(checks) - passed,
            'pass_rate': round(passed / len(checks), 4),
            'cases': checks,
        }

    def evaluate_alerts(self) -> dict[str, Any]:
        """Measure deterministic alert rules against a controlled dataset."""
        dataset = self.load_alert_cases()
        reference_date = date.fromisoformat(dataset['reference_date'])
        details: list[dict[str, Any]] = []
        true_positive = true_negative = false_positive = false_negative = 0

        for case in dataset['cases']:
            pet_data = case['pet']
            pet = Pet(
                id=uuid.uuid4(),
                owner_id=uuid.uuid4(),
                external_id=f"EVAL-{case['id']}",
                name=case['id'],
                species=pet_data['species'],
                breed=pet_data['breed'],
                birth_date=date.fromisoformat(pet_data['birth_date']),
                sex='unknown',
                weight_kg=Decimal(str(pet_data['weight_kg'])),
                neutered=False,
            )
            for index, event in enumerate(case.get('events', []), start=1):
                pet.clinical_events.append(
                    ClinicalEvent(
                        id=uuid.uuid4(),
                        external_id=f"{case['id']}-EV-{index}",
                        event_date=datetime.combine(
                            reference_date - timedelta(days=int(event['days_ago'])),
                            datetime.min.time(),
                            tzinfo=timezone.utc,
                        ),
                        event_type='consultation',
                        title=event['title'],
                        description=event.get('description', event['title']),
                        weight_kg=Decimal(str(event['weight_kg'])) if event.get('weight_kg') is not None else None,
                        visible_to_owner=True,
                    )
                )
            actual, evidence = matches(pet, case['conditions'], reference_date)
            expected = bool(case['expected'])
            if expected and actual:
                true_positive += 1
            elif not expected and not actual:
                true_negative += 1
            elif not expected and actual:
                false_positive += 1
            else:
                false_negative += 1
            details.append({
                'id': case['id'],
                'description': case['description'],
                'expected': expected,
                'actual': actual,
                'passed': expected == actual,
                'evidence': evidence,
            })

        total = len(details)
        correct = true_positive + true_negative
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 1.0
        recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 1.0
        return {
            'dataset': self.alert_path.stem,
            'total': total,
            'passed': correct,
            'failed': total - correct,
            'accuracy': round(correct / total, 4) if total else 0.0,
            'precision': round(precision, 4),
            'recall': round(recall, 4),
            'confusion_matrix': {
                'true_positive': true_positive,
                'true_negative': true_negative,
                'false_positive': false_positive,
                'false_negative': false_negative,
            },
            'cases': details,
        }

    def run_tests(self) -> dict[str, Any]:
        """Execute pytest with JUnit and coverage outputs inside the API image."""
        reports = self.reports_path
        reports.mkdir(parents=True, exist_ok=True)
        junit_path = reports / 'junit-v0.11.0.xml'
        coverage_path = reports / 'coverage-v0.11.0.json'
        command = [
            sys.executable, '-m', 'pytest', '-q', '/app/tests',
            f'--junitxml={junit_path}', '--cov=app', f'--cov-report=json:{coverage_path}',
        ]
        if not Path('/app/tests').exists():
            command[4] = str(Path(__file__).resolve().parents[2] / 'tests')
        started = time.perf_counter()
        completed = subprocess.run(command, cwd='/app' if Path('/app').exists() else None, capture_output=True, text=True)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)

        total = passed = failed = skipped = errors = 0
        if junit_path.exists():
            root = ET.parse(junit_path).getroot()
            suite = root if root.tag == 'testsuite' else root.find('testsuite')
            if suite is not None:
                total = int(suite.attrib.get('tests', 0))
                failed = int(suite.attrib.get('failures', 0))
                errors = int(suite.attrib.get('errors', 0))
                skipped = int(suite.attrib.get('skipped', 0))
                passed = total - failed - errors - skipped
        coverage = None
        if coverage_path.exists():
            payload = json.loads(coverage_path.read_text(encoding='utf-8'))
            coverage = round(float(payload.get('totals', {}).get('percent_covered', 0.0)), 2)

        return {
            'status': 'passed' if completed.returncode == 0 else 'failed',
            'exit_code': completed.returncode,
            'total': total,
            'passed': passed,
            'failed': failed + errors,
            'skipped': skipped,
            'coverage_percent': coverage,
            'duration_ms': duration_ms,
            'stdout_tail': completed.stdout[-4000:],
            'stderr_tail': completed.stderr[-2000:],
        }

    async def evaluate_vetia(self) -> dict[str, Any]:
        """Reuse the versioned retrieval evaluator without generating answers."""
        try:
            report = await RagEvaluator().run(with_generation=False)
            return {'status': 'completed', **report}
        except Exception as exc:  # External services may be unavailable.
            return {'status': 'failed', 'error': str(exc)[:1000], 'metrics': {}, 'details': []}

    async def benchmark_api(self, requests: int = 30, concurrency: int = 5) -> dict[str, Any]:
        """Run a bounded smoke benchmark against the liveness endpoint."""
        semaphore = asyncio.Semaphore(concurrency)
        latencies: list[float] = []
        failures = 0

        async def one(client: httpx.AsyncClient) -> None:
            nonlocal failures
            async with semaphore:
                start = time.perf_counter()
                try:
                    response = await client.get('/health/live')
                    if response.status_code != 200:
                        failures += 1
                except Exception:
                    failures += 1
                finally:
                    latencies.append((time.perf_counter() - start) * 1000)

        try:
            async with httpx.AsyncClient(base_url=settings.quality_base_url, timeout=10) as client:
                await asyncio.gather(*(one(client) for _ in range(requests)))
        except Exception as exc:
            return {'status': 'failed', 'error': str(exc)[:1000], 'requests': requests, 'failures': requests}

        ordered = sorted(latencies)
        p95_index = max(0, min(len(ordered) - 1, int(len(ordered) * 0.95) - 1))
        return {
            'status': 'completed' if failures == 0 else 'degraded',
            'requests': requests,
            'concurrency': concurrency,
            'failures': failures,
            'success_rate': round((requests - failures) / requests, 4),
            'latency_mean_ms': round(statistics.mean(latencies), 2),
            'latency_p50_ms': round(statistics.median(latencies), 2),
            'latency_p95_ms': round(ordered[p95_index], 2),
        }

    def _score(self, sections: dict[str, Any]) -> tuple[float, bool]:
        acceptance = sections['acceptance']['pass_rate'] * 30
        tests = (1.0 if sections.get('tests', {}).get('status') == 'passed' else 0.0) * 25
        alerts = sections['alerts']['accuracy'] * 20
        security = sections['security']['pass_rate'] * 10
        vetia_metrics = sections.get('vetia', {}).get('metrics', {})
        vetia_rate = float(vetia_metrics.get('retrieval_hit_rate', 0.0)) if sections.get('vetia') else 0.0
        vetia = vetia_rate * 10
        performance = sections.get('performance', {})
        performance_score = float(performance.get('success_rate', 0.0)) * 5
        score = round(acceptance + tests + alerts + security + vetia + performance_score, 2)
        critical_ok = (
            sections['security']['failed'] == 0
            and sections.get('tests', {}).get('status') != 'failed'
            and sections.get('vetia', {}).get('status') != 'failed'
        )
        return score, score >= 80 and critical_ok

    def build_report(self, sections: dict[str, Any], score: float, passed: bool) -> str:
        """Generate a compact Markdown report for evidence and version control."""
        tests = sections.get('tests', {})
        vetia = sections.get('vetia', {})
        vetia_metrics = vetia.get('metrics', {})
        performance = sections.get('performance', {})
        failed_acceptance = [item for item in sections['acceptance']['cases'] if not item['passed']]
        failed_alerts = [item for item in sections['alerts']['cases'] if not item['passed']]
        vetia_value = (
            f"{float(vetia_metrics['retrieval_hit_rate']) * 100:.1f}%"
            if isinstance(vetia_metrics.get('retrieval_hit_rate'), (int, float))
            else 'n/d'
        )
        lines = [
            f'# Informe de evaluacion GamuCare AI {APP_VERSION}',
            '',
            f'- Resultado global: **{"APTO" if passed else "REQUIERE REVISION"}**',
            f'- Puntuacion automatica: **{score}/100**',
            f'- Fecha UTC: {datetime.now(timezone.utc).isoformat()}',
            '',
            '## Resumen',
            '',
            '| Area | Resultado |',
            '|---|---:|',
            f"| Criterios de aceptacion | {sections['acceptance']['passed']}/{sections['acceptance']['total']} |",
            f"| Pruebas automatizadas | {tests.get('passed', 0)}/{tests.get('total', 0)} |",
            f"| Cobertura de codigo | {tests.get('coverage_percent', 'n/d')}% |",
            f"| Casos de avisos preventivos | {sections['alerts']['passed']}/{sections['alerts']['total']} |",
            f"| Controles de seguridad | {sections['security']['passed']}/{sections['security']['total']} |",
            f"| Acierto de recuperacion VetIA | {vetia_value} |",
            f"| P95 API | {performance.get('latency_p95_ms', 'n/d')} ms |",
            '',
            '## Incidencias automaticas',
            '',
        ]
        if not failed_acceptance and not failed_alerts and tests.get('status') != 'failed':
            lines.append('No se han detectado incidencias en los criterios automaticos ejecutados.')
        else:
            for item in failed_acceptance:
                lines.append(f"- {item['id']}: {item['description']} ({item['evidence']})")
            for item in failed_alerts:
                lines.append(f"- {item['id']}: resultado {item['actual']} y esperado {item['expected']}")
            if tests.get('status') == 'failed':
                lines.append(f"- Pytest ha finalizado con codigo {tests.get('exit_code')}.")
        lines.extend([
            '',
            '## Interpretacion',
            '',
            'Las metricas automaticas verifican comportamiento tecnico y criterios controlados. No sustituyen la validacion veterinaria humana de las recomendaciones ni convierten los avisos preventivos en diagnosticos.',
        ])
        return '\n'.join(lines) + '\n'

    async def run(
        self,
        db: Session,
        *,
        include_tests: bool = True,
        include_vetia: bool = True,
        include_performance: bool = True,
    ) -> dict[str, Any]:
        """Execute selected sections and return metrics, details and report."""
        sections: dict[str, Any] = {
            'acceptance': self.evaluate_acceptance(db),
            'alerts': self.evaluate_alerts(),
            'security': self.evaluate_security(),
        }
        sections['tests'] = self.run_tests() if include_tests else {
            'status': 'skipped', 'total': 0, 'passed': 0, 'failed': 0, 'coverage_percent': None,
        }
        sections['vetia'] = await self.evaluate_vetia() if include_vetia else {
            'status': 'skipped', 'metrics': {}, 'details': [],
        }
        sections['performance'] = await self.benchmark_api() if include_performance else {
            'status': 'skipped', 'success_rate': 0.0,
        }
        score, passed = self._score(sections)
        report = self.build_report(sections, score, passed)
        return {
            'metrics': {
                'overall_score': score,
                'overall_passed': passed,
                'acceptance_pass_rate': sections['acceptance']['pass_rate'],
                'alert_accuracy': sections['alerts']['accuracy'],
                'alert_precision': sections['alerts']['precision'],
                'alert_recall': sections['alerts']['recall'],
                'security_pass_rate': sections['security']['pass_rate'],
                'test_coverage_percent': sections['tests'].get('coverage_percent'),
                'vetia_retrieval_hit_rate': sections['vetia'].get('metrics', {}).get('retrieval_hit_rate'),
                'api_latency_p95_ms': sections['performance'].get('latency_p95_ms'),
            },
            'details': sections,
            'report_markdown': report,
            'tests_total': int(sections['tests'].get('total', 0)),
            'tests_passed': int(sections['tests'].get('passed', 0)),
            'tests_failed': int(sections['tests'].get('failed', 0)),
            'coverage_percent': sections['tests'].get('coverage_percent'),
        }
