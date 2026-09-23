"""
Application configuration loaded from environment variables.

All settings are typed with Pydantic BaseSettings so they can be
overridden via .env file or environment variables without touching code.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        # Prefix prevents collision with system env vars like DEBUG, PATH, etc.
        # All our env vars use AGT_ prefix in the environment.
        # But we keep .env file keys un-prefixed for developer ergonomics
        # by NOT setting env_prefix here — instead we use explicit field aliases below.
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_name: str = "AI Governance Agent"
    app_version: str = "0.1.0"
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = False  # Use APP_DEBUG=true in .env, not DEBUG (system var)

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/ai_governance",
        description="Async PostgreSQL connection URL. Must point to a DB with pgvector installed.",
    )

    # ── LLM Provider ──────────────────────────────────────────────────────────
    llm_provider: Literal["groq", "ollama"] = Field(
        default="groq",
    llm_provider: Literal["groq", "ollama", "openai"] = Field(
        default="openai",
        description="LLM backend to use. Swap without changing agent logic.",
    )

    # Groq
    groq_api_key: str = Field(default="", description="Groq API key from console.groq.com")
    groq_model: str = Field(default="llama-3.1-8b-instant", description="Groq model name")
    llm_model: str = Field(default="llama-3.3-70b-versatile", description="LLM model name")
    llm_base_url: str = Field(default="https://api.groq.com/openai/v1", description="LLM server URL")
    llm_api_key: str = Field(default="", description="LLM API key")
    llm_temperature: float = Field(default=0.0, description="LLM temperature")

    # Ollama (local fallback)
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama server URL")
    ollama_model: str = Field(default="llama3.2", description="Ollama model name")

    # ── LangSmith Observability ───────────────────────────────────────────────
    langsmith_tracing: bool = Field(
        default=False,
        description="Enable LangSmith tracing. App runs fine without it.",
    )
    langsmith_api_key: str = Field(default="", description="LangSmith API key")
    langsmith_project: str = Field(default="ai-governance-agent")
    langsmith_endpoint: str = Field(default="https://api.smith.langchain.com", description="LangSmith endpoint")

    # ── Risk Engine Thresholds ────────────────────────────────────────────────
    risk_threshold_low: int = Field(
        default=30,
        description="Score below this is LOW risk. Range: 0-29 → LOW",
    )
    risk_threshold_medium: int = Field(
        default=60,
        description="Score below this is MEDIUM risk. Range: 30-59 → MEDIUM",
    )
    risk_threshold_high: int = Field(
        default=80,
        description="Score below this is HIGH risk. Range: 60-79 → HIGH. ≥80 → CRITICAL",
    )

    # Minimum risk score that triggers human-in-the-loop approval workflow
    approval_risk_threshold: int = Field(
        default=60,
        description="Risk score at or above this value requires human approval.",
    )

    # ── Embedding (local, no paid API) ────────────────────────────────────────
    embedding_provider: Literal["sentence-transformers", "ollama"] = Field(
        default="ollama",
        description="Embedding provider to use",
    )
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="SentenceTransformers model name. Produces 384-dim vectors.",
        default="nomic-embed-text:latest",
        description="Model name.",
    )
    embedding_dimensions: int = Field(
        default=384,
    embedding_base_url: str = Field(default="http://localhost:11434/v1", description="Embedding server URL")
    embedding_api_key: str = Field(default="ollama", description="Embedding API key")
    embedding_dimension: int = Field(
        default=768,
        description="Embedding vector size. Must match pgvector column definition.",
    )

    # ── RAG ───────────────────────────────────────────────────────────────────
    rag_top_k: int = Field(
        default=5,
    retrieval_top_k: int = Field(
        default=6,
        description="Number of policy chunks to retrieve per semantic query.",
    )
    chunk_size: int = Field(default=900, description="Chunk size for document splitting.")
    chunk_overlap: int = Field(default=150, description="Chunk overlap for document splitting.")

    # ── Integrations & Agent ──────────────────────────────────────────────────
    youtube_api_key: str = Field(default="", description="YouTube API Key")
    max_agent_retries: int = Field(default=2, description="Max Retries for Agent")

    # ── Risk Scoring Weights ──────────────────────────────────────────────────
    # These determine how much each risk dimension contributes to the total.
    # Must sum to 100.
    weight_data_risk: int = Field(default=30)
    weight_security_risk: int = Field(default=30)
    weight_compliance_risk: int = Field(default=20)
    weight_model_risk: int = Field(default=10)
    weight_business_impact: int = Field(default=10)

    @computed_field  # type: ignore[misc]
    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @computed_field  # type: ignore[misc]
    @property
    def langsmith_enabled(self) -> bool:
        return self.langsmith_tracing and bool(self.langsmith_api_key)


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance. Call this everywhere."""
    return Settings()

