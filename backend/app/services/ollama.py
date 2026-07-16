"""Small Ollama client isolated from business logic.

The wrapper keeps the rest of the application independent from Ollama-specific
HTTP payloads, and keeps provider-specific payloads outside the business services.
"""
from __future__ import annotations

import httpx
import time

from app.observability.metrics import OLLAMA_DURATION, OLLAMA_REQUESTS, OLLAMA_TOKENS

from app.config import get_settings

settings = get_settings()


class OllamaUnavailable(RuntimeError):
    """Raised when Ollama cannot be contacted or returns an invalid response."""


class OllamaClient:
    """Asynchronous client for chat generation and embeddings."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.ollama_url).rstrip('/')

    async def embed(self, text: str) -> list[float]:
        """Generate a vector, with a fallback for older Ollama endpoints."""
        started = time.perf_counter()
        outcome = 'error'
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                try:
                    response = await client.post(
                        f'{self.base_url}/api/embed',
                        json={'model': settings.ollama_embed_model, 'input': text},
                    )
                    response.raise_for_status()
                    data = response.json()
                    embeddings = data.get('embeddings')
                    if embeddings and isinstance(embeddings, list):
                        outcome = 'success'
                        return embeddings[0]
                except (httpx.HTTPError, KeyError, IndexError, TypeError):
                    pass

                try:
                    response = await client.post(
                        f'{self.base_url}/api/embeddings',
                        json={'model': settings.ollama_embed_model, 'prompt': text},
                    )
                    response.raise_for_status()
                    vector = response.json().get('embedding')
                    if isinstance(vector, list) and vector:
                        outcome = 'success'
                        return vector
                except httpx.HTTPError as exc:
                    raise OllamaUnavailable(f'No se pudo generar el embedding: {exc}') from exc

            raise OllamaUnavailable('Ollama no devolvio un embedding valido')
        finally:
            OLLAMA_REQUESTS.labels('embed', outcome).inc()
            OLLAMA_DURATION.labels('embed').observe(time.perf_counter() - started)


    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings in one request when supported by Ollama."""
        if not texts:
            return []
        started = time.perf_counter()
        outcome = 'error'
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                try:
                    response = await client.post(
                        f'{self.base_url}/api/embed',
                        json={'model': settings.ollama_embed_model, 'input': texts},
                    )
                    response.raise_for_status()
                    embeddings = response.json().get('embeddings')
                    if (
                        isinstance(embeddings, list)
                        and len(embeddings) == len(texts)
                        and all(isinstance(item, list) and item for item in embeddings)
                    ):
                        outcome = 'success'
                        return embeddings
                except (httpx.HTTPError, KeyError, TypeError):
                    pass

            result = [await self.embed(text) for text in texts]
            outcome = 'success'
            return result
        finally:
            OLLAMA_REQUESTS.labels('embed_many', outcome).inc()
            OLLAMA_DURATION.labels('embed_many').observe(time.perf_counter() - started)


    async def chat(self, system_prompt: str, user_prompt: str) -> str:
        """Generate one non-streaming response from the configured chat model."""
        payload = {
            'model': settings.ollama_chat_model,
            'stream': False,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            'options': {'temperature': 0.2, 'top_p': 0.9, 'top_k': 40},
        }
        started = time.perf_counter()
        outcome = 'error'
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                response = await client.post(f'{self.base_url}/api/chat', json=payload)
                response.raise_for_status()
                data = response.json()
                content = data.get('message', {}).get('content', '').strip()
                if not content:
                    raise OllamaUnavailable('Ollama devolvio una respuesta vacia')
                prompt_tokens = data.get('prompt_eval_count')
                completion_tokens = data.get('eval_count')
                if isinstance(prompt_tokens, int) and prompt_tokens >= 0:
                    OLLAMA_TOKENS.labels('prompt').inc(prompt_tokens)
                if isinstance(completion_tokens, int) and completion_tokens >= 0:
                    OLLAMA_TOKENS.labels('completion').inc(completion_tokens)
                outcome = 'success'
                return content
        except httpx.HTTPError as exc:
            raise OllamaUnavailable(f'No se pudo consultar el modelo: {exc}') from exc
        finally:
            OLLAMA_REQUESTS.labels('chat', outcome).inc()
            OLLAMA_DURATION.labels('chat').observe(time.perf_counter() - started)

