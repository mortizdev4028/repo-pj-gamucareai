"""Run and persist the formal GamuCare MVP evaluation from the command line."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path

from app.database import SessionLocal
from app.models import SystemEvaluationRun
from app.services.system_evaluation import SystemEvaluator
from app.version import APP_VERSION


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-tests', action='store_true')
    parser.add_argument('--skip-vetia', action='store_true')
    parser.add_argument('--skip-performance', action='store_true')
    args = parser.parse_args()

    evaluator = SystemEvaluator()
    db = SessionLocal()
    run = SystemEvaluationRun(app_version=APP_VERSION, status='running', suite_name='mvp_quality_v1')
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        result = await evaluator.run(
            db,
            include_tests=not args.skip_tests,
            include_vetia=not args.skip_vetia,
            include_performance=not args.skip_performance,
        )
        run.status = 'completed'
        run.tests_total = result['tests_total']
        run.tests_passed = result['tests_passed']
        run.tests_failed = result['tests_failed']
        run.coverage_percent = Decimal(str(result['coverage_percent'])) if result['coverage_percent'] is not None else None
        run.metrics = result['metrics']
        run.details = result['details']
        run.report_markdown = result['report_markdown']
        run.finished_at = datetime.now(timezone.utc)
        db.commit()

        evaluator.reports_path.mkdir(parents=True, exist_ok=True)
        report_path = evaluator.reports_path / f'gamucare-evaluation-{APP_VERSION}.md'
        json_path = evaluator.reports_path / f'gamucare-evaluation-{APP_VERSION}.json'
        report_path.write_text(result['report_markdown'], encoding='utf-8')
        json_path.write_text(json.dumps({'metrics': result['metrics'], 'details': result['details']}, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
        print(json.dumps(result['metrics'], ensure_ascii=False, indent=2))
        print(f'Informe: {report_path}')
        if result['tests_failed'] > 0:
            raise SystemExit(3)
    except Exception as exc:
        run.status = 'failed'
        run.error = str(exc)[:3000]
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    asyncio.run(main())
