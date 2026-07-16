#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
[ -f .env ] || cp .env.example .env
docker compose up -d postgres qdrant ollama
sleep 10
docker compose --profile setup run --rm ollama-init
docker compose up -d --build api web
sleep 10
docker compose exec api python -m app.scripts.enrich_demo_histories
docker compose exec api python -m app.rag.ingest
docker compose exec api python -m app.scripts.enrich_alerts
docker compose exec api python -m app.scripts.evaluate_rag
docker compose --profile monitoring up -d postgres-exporter blackbox-exporter alertmanager prometheus grafana
printf '%s\n' 'GamuCare AI disponible en http://localhost:8080'
printf '%s\n' 'Grafana disponible en http://localhost:3000'
