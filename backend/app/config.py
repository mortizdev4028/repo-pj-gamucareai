"""Centralised application configuration.

All values can be overridden through environment variables. Keeping the
configuration in one place makes the local Docker deployment easier to configure, compare and audit.
"""
from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime settings loaded from the environment."""

    model_config = SettingsConfigDict(env_file='.env', extra='ignore', case_sensitive=False)

    app_name: str = 'GamuCare AI'
    app_env: str = 'development'
    log_level: str = 'INFO'
    log_file: str | None = None
    log_max_bytes: int = 10_485_760
    log_backup_count: int = 5
    seed_on_startup: bool = True

    database_url: str = 'postgresql+psycopg://gamucare:gamucare_dev_password@postgres:5432/gamucare'

    jwt_secret: str = 'change-this-local-secret-before-production'
    jwt_algorithm: str = 'HS256'
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    refresh_cookie_name: str = 'gamucare_refresh'
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: str = 'lax'
    max_failed_login_attempts: int = 5
    login_lock_minutes: int = 15
    password_min_length: int = 12

    ollama_url: str = 'http://ollama:11434'
    ollama_chat_model: str = 'gamucare-llm'
    ollama_embed_model: str = 'nomic-embed-text'

    qdrant_url: str = 'http://qdrant:6333'
    qdrant_collection: str = 'gamucare_knowledge'
    rag_min_score: float = 0.42
    rag_candidate_k: int = 24
    rag_top_k: int = 6
    rag_clinical_top_k: int = 12
    rag_alert_top_k: int = 8
    rag_documents_path: str = '/app/data/rag'
    rag_external_documents_path: str = '/app/data/rag_external'
    rag_source_manifest: str = '/app/data/rag_sources/sources.json'
    rag_source_max_bytes: int = 26_214_400
    rag_evaluation_dataset: str = '/app/data/evaluation/rag_cases_v2.json'
    system_acceptance_dataset: str = '/app/data/evaluation/acceptance_criteria_v1.json'
    alert_evaluation_dataset: str = '/app/data/evaluation/alert_cases_v1.json'
    quality_reports_path: str = '/app/data/reports'
    quality_base_url: str = 'http://localhost:8000'

    cors_origins: list[str] = ['http://localhost:8080', 'http://localhost:5173']

    @field_validator('cors_origins', mode='before')
    @classmethod
    def split_origins(cls, value: object) -> object:
        """Allow a comma-separated value in Docker environment files."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(',') if item.strip()]
        return value


    @model_validator(mode='after')
    def validate_security_settings(self) -> 'Settings':
        """Reject development secrets when the application is marked as production."""
        if self.app_env.lower() == 'production':
            if self.jwt_secret == 'change-this-local-secret-before-production' or len(self.jwt_secret) < 32:
                raise ValueError('JWT_SECRET debe ser aleatorio y tener al menos 32 caracteres en produccion')
            if not self.refresh_cookie_secure:
                raise ValueError('REFRESH_COOKIE_SECURE debe estar habilitado en produccion')
        if self.refresh_cookie_samesite not in {'lax', 'strict', 'none'}:
            raise ValueError('REFRESH_COOKIE_SAMESITE debe ser lax, strict o none')
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance for dependency injection."""
    return Settings()
