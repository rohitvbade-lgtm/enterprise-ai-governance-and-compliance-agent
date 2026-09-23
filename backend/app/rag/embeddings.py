"""
Local embedding model abstraction.

Supports two providers:
  - sentence-transformers: all-MiniLM-L6-v2 (384 dims) — no external API calls
  - ollama: nomic-embed-text (768 dims) — local Ollama instance

The model is cached in memory after first load.
"""
from __future__ import annotations

import structlog
from functools import lru_cache

from backend.app.config.settings import get_settings

logger = structlog.get_logger(__name__)


class EmbeddingWrapper:
    """Wraps either SentenceTransformer or OllamaEmbeddings with a unified interface."""

    def __init__(self, provider: str, model_name: str, base_url: str = ""):
        self.provider = provider
        if provider == "sentence-transformers":
            from sentence_transformers import SentenceTransformer
            logger.info("loading_embedding_model", model=model_name)
            self.model = SentenceTransformer(model_name)
            logger.info("embedding_model_loaded", model=model_name)
        elif provider == "ollama":
            from langchain_ollama import OllamaEmbeddings
            logger.info("loading_ollama_embedding_model", model=model_name)
            self.model = OllamaEmbeddings(model=model_name, base_url=base_url.rstrip("/v1").rstrip("/"))
            logger.info("ollama_embedding_model_loaded", model=model_name)
        else:
            raise ValueError(f"Unknown embedding provider: {provider!r}. Supported: 'sentence-transformers', 'ollama'")

    def embed_text(self, text: str) -> list[float]:
        """Embed a single string into a vector."""
        if self.provider == "sentence-transformers":
            return self.model.encode(text, normalize_embeddings=True).tolist()
        else:
            return self.model.embed_query(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple strings in a batch."""
        if self.provider == "sentence-transformers":
            return [v.tolist() for v in self.model.encode(texts, normalize_embeddings=True, batch_size=32)]
        else:
            return self.model.embed_documents(texts)


@lru_cache(maxsize=1)
def _load_model(provider: str, model_name: str, base_url: str) -> EmbeddingWrapper:
    """Load and cache the embedding model. Called once on first use."""
    return EmbeddingWrapper(provider, model_name, base_url)


def get_embedding_model() -> EmbeddingWrapper:
    """Return the configured (cached) embedding model."""
    settings = get_settings()
    return _load_model(settings.embedding_provider, settings.embedding_model, settings.embedding_base_url)


def embed_text(text: str) -> list[float]:
    """
    Embed a single string into a vector.

    PII detection must run before this — don't embed raw sensitive data.
    """
    model = get_embedding_model()
    return model.embed_text(text)


def embed_batch(texts: list[str]) -> list[list[float]]:
    """
    Embed multiple strings in a single batch call for efficiency.
    """
    model = get_embedding_model()
    return model.embed_batch(texts)
