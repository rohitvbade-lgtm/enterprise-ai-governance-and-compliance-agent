"""
LLM Provider abstraction.

Returns a LangChain BaseChatModel based on LLM_PROVIDER env var.
Agents never touch provider selection — they only use get_llm().

Supported providers:
  - openai  (OpenAI-compatible endpoint — used by Groq, local vLLM, etc.)
  - groq    (legacy: uses groq_api_key / groq_model fields)
  - ollama  (local fallback)
"""
from __future__ import annotations

import structlog
from langchain_core.language_models import BaseChatModel

from backend.app.config.settings import Settings, get_settings

logger = structlog.get_logger(__name__)


def get_llm(settings: Settings | None = None, temperature: float = 0.0) -> BaseChatModel:
    """
    Factory that returns the configured LLM provider.

    Args:
        settings: Optional settings override (uses global settings if None).
        temperature: LLM temperature. 0.0 for deterministic, 0.1+ for more creative.

    Returns:
        A LangChain BaseChatModel instance ready for agent use.

    Raises:
        ValueError: If LLM_PROVIDER is not one of the supported values.
        ImportError: If the required provider package is not installed.
    """
    if settings is None:
        settings = get_settings()

    provider = settings.llm_provider.lower()
    logger.info("initializing_llm_provider", provider=provider)

    if provider == "openai":
        # Generic OpenAI-compatible endpoint (works for Groq, OpenAI, local vLLM, etc.)
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as e:
            raise ImportError(
                "langchain-openai is required for the openai provider. "
                "Run: uv add langchain-openai"
            ) from e

        if not settings.llm_api_key:
            raise ValueError(
                "LLM_API_KEY is not set. Add it to your .env file."
            )

        return ChatOpenAI(
            api_key=settings.llm_api_key,  # type: ignore[arg-type]
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            temperature=temperature,
            max_retries=2,
        )

    elif provider == "groq":
        try:
            from langchain_groq import ChatGroq
        except ImportError as e:
            raise ImportError(
                "langchain-groq is required for the groq provider. "
                "Run: uv add langchain-groq"
            ) from e

        if not settings.groq_api_key:
            raise ValueError(
                "GROQ_API_KEY is not set. Add it to your .env file. "
                "Get a free key at console.groq.com"
            )

        return ChatGroq(
            api_key=settings.groq_api_key,  # type: ignore[arg-type]
            model=settings.groq_model,
            temperature=temperature,
            max_retries=2,
        )

    elif provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError as e:
            raise ImportError(
                "langchain-ollama is required for the ollama provider. "
                "Run: uv add langchain-ollama"
            ) from e

        return ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=temperature,
        )

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER: {provider!r}. "
            f"Supported values: 'openai', 'groq', 'ollama'"
        )
