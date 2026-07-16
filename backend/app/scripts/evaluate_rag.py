"""Command-line entry point that persists a repeatable RAG evaluation."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json

from app.config import get_settings
from app.database import SessionLocal
from app.models import RagEvaluationRun
from app.services.rag_evaluation import RagEvaluator

settings = get_settings()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--with-generation', action='store_true', help='Generate answers and verify citation presence')
    args = parser.parse_args()
    evaluator = RagEvaluator()
    db = SessionLocal()
    run = RagEvaluationRun(
        mode='generation' if args.with_generation else 'retrieval',
        status='running',
        dataset_name=evaluator.dataset_path.stem,
        cases_total=len(evaluator.load_cases()),
        model_name=settings.ollama_chat_model if args.with_generation else settings.ollama_embed_model,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        report = await evaluator.run(with_generation=args.with_generation)
        run.status = 'completed'
        run.metrics = report['metrics']
        run.details = report['details']
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        print(json.dumps(report['metrics'], ensure_ascii=False, indent=2))
    except Exception as exc:
        run.status = 'failed'
        run.error = str(exc)[:2000]
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    asyncio.run(main())
