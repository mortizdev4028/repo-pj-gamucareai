"""Prometheus metrics shared by infrastructure-facing services."""
from prometheus_client import Counter, Gauge, Histogram, Info

from app.config import get_settings
from app.version import APP_VERSION

settings = get_settings()

APP_INFO = Info('gamucare_app', 'GamuCare application build information')
APP_INFO.info({'version': APP_VERSION, 'environment': settings.app_env})

DEPENDENCY_UP = Gauge(
    'gamucare_dependency_up',
    'Whether a required dependency answered the last active check.',
    ['dependency'],
)
DEPENDENCY_LATENCY = Gauge(
    'gamucare_dependency_latency_seconds',
    'Latency of the last active dependency check.',
    ['dependency'],
)
OLLAMA_REQUESTS = Counter(
    'gamucare_ollama_requests_total',
    'Logical Ollama operations by type and outcome.',
    ['operation', 'outcome'],
)
OLLAMA_DURATION = Histogram(
    'gamucare_ollama_request_duration_seconds',
    'Ollama request latency by logical operation.',
    ['operation'],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 120, 240),
)
OLLAMA_TOKENS = Counter(
    'gamucare_ollama_tokens_total',
    'Prompt and completion tokens reported by Ollama.',
    ['kind'],
)
QDRANT_SEARCHES = Counter(
    'gamucare_qdrant_searches_total',
    'Vector searches by content mode and outcome.',
    ['mode', 'outcome'],
)
QDRANT_DURATION = Histogram(
    'gamucare_qdrant_search_duration_seconds',
    'Qdrant vector search latency.',
    ['mode'],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)
RAG_RESULTS = Histogram(
    'gamucare_vetia_retrieved_chunks',
    'Number of chunks selected after reranking.',
    ['mode'],
    buckets=(0, 1, 2, 3, 4, 6, 8, 12, 20, 30),
)
VETIA_REQUESTS = Counter(
    'gamucare_vetia_requests_total',
    'VetIA questions by scope and outcome.',
    ['scope', 'outcome'],
)
VETIA_DURATION = Histogram(
    'gamucare_vetia_request_duration_seconds',
    'End-to-end VetIA answer latency.',
    ['scope'],
    buckets=(0.25, 0.5, 1, 2, 5, 10, 20, 40, 90, 180, 300),
)
BACKUP_OPERATIONS = Counter(
    'gamucare_backup_operations_total',
    'Backup and restore operations reported through the API.',
    ['operation', 'outcome'],
)
