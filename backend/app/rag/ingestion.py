"""
Policy document ingestion pipeline.

Pipeline:
  Markdown files → Parse metadata → Chunk text → Embed → Upsert to pgvector

Run via: python scripts/ingest_policies.py
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

import structlog

from backend.app.config.settings import get_settings
from backend.app.db.session import get_db
from backend.app.models.policy import Policy, PolicyChunk
from backend.app.rag.embeddings import embed_batch

logger = structlog.get_logger(__name__)

# ── Metadata extraction from Markdown front-matter ────────────────────────────

_META_PATTERNS: dict[str, re.Pattern[str]] = {
    "policy_code": re.compile(r"\*\*Policy Code:\*\*\s*(.+)", re.IGNORECASE),
    "category": re.compile(r"\*\*Category:\*\*\s*(.+)", re.IGNORECASE),
    "severity": re.compile(r"\*\*Severity:\*\*\s*(.+)", re.IGNORECASE),
    "version": re.compile(r"\*\*Version:\*\*\s*(.+)", re.IGNORECASE),
    "effective_from": re.compile(r"\*\*Effective From:\*\*\s*(.+)", re.IGNORECASE),
}

# Map category strings from documents to canonical values
_CATEGORY_MAP = {
    "PII / DATA_PRIVACY": "PII",
    "DATA_PRIVACY": "DATA_PRIVACY",
    "PROMPT_SECURITY / SECURITY": "PROMPT_SECURITY",
    "PROMPT_SECURITY": "PROMPT_SECURITY",
    "SECURITY": "SECURITY",
    "DATA_RETENTION": "DATA_RETENTION",
    "ACCESS_CONTROL": "ACCESS_CONTROL",
    "MODEL_USAGE": "MODEL_USAGE",
    "FINANCIAL / REGULATORY": "FINANCIAL",
    "FINANCIAL": "FINANCIAL",
    "HR / REGULATORY": "HR",
    "HR": "HR",
    "REGULATORY": "REGULATORY",
}

_SEVERITY_MAP = {
    "CRITICAL": "CRITICAL",
    "HIGH": "HIGH",
    "MEDIUM": "MEDIUM",
    "LOW": "LOW",
}


def _extract_metadata(content: str, filename: str) -> dict[str, Any]:
    """Extract metadata from the Markdown document's front section."""
    meta: dict[str, Any] = {
        "policy_code": None,
        "category": "GENERAL",
        "severity": "MEDIUM",
        "version": "1.0",
        "effective_from": None,
    }

    for key, pattern in _META_PATTERNS.items():
        match = pattern.search(content)
        if match:
            value = match.group(1).strip()
            if key == "category":
                meta[key] = _CATEGORY_MAP.get(value.upper(), value.split("/")[0].strip().upper())
            elif key == "severity":
                meta[key] = _SEVERITY_MAP.get(value.upper(), "MEDIUM")
            else:
                meta[key] = value

    if not meta["policy_code"]:
        # Fallback: derive from filename
        meta["policy_code"] = f"POL-{filename.upper().replace('.MD', '').replace('_', '-')}"

    # Extract title (first # heading)
    title_match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
    meta["name"] = title_match.group(1).strip() if title_match else filename

    # Extract description (first paragraph after the title + metadata block)
    purpose_match = re.search(r"## Purpose\s+(.+?)(?=##|\Z)", content, re.DOTALL)
    if purpose_match:
        meta["description"] = purpose_match.group(1).strip()[:500]
    else:
        meta["description"] = meta["name"]

    return meta


def _chunk_text(text: str, chunk_size: int = 600, overlap: int = 100) -> list[str]:
    """
    Split text into overlapping chunks by paragraph boundaries.
    Prefers paragraph breaks over hard character limits.
    """
    # Split by double newlines (paragraphs)
    paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]

    chunks: list[str] = []
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 <= chunk_size:
            current_chunk = f"{current_chunk}\n\n{para}".strip()
        else:
            if current_chunk:
                chunks.append(current_chunk)
            # If a single paragraph exceeds chunk_size, split by sentences
            if len(para) > chunk_size:
                sentences = re.split(r"(?<=[.!?])\s+", para)
                temp = ""
                for sent in sentences:
                    if len(temp) + len(sent) + 1 <= chunk_size:
                        temp = f"{temp} {sent}".strip()
                    else:
                        if temp:
                            chunks.append(temp)
                        temp = sent
                if temp:
                    current_chunk = temp
                else:
                    current_chunk = ""
            else:
                current_chunk = para

    if current_chunk:
        chunks.append(current_chunk)

    return [c for c in chunks if len(c) > 50]  # drop very short fragments


async def ingest_policy_file(file_path: Path) -> dict[str, Any]:
    """
    Ingest a single policy Markdown file into the database.

    Returns a summary dict with counts.
    """
    content = file_path.read_text(encoding="utf-8")
    meta = _extract_metadata(content, file_path.stem)
    chunks = _chunk_text(content)

    logger.info(
        "ingesting_policy",
        file=file_path.name,
        policy_code=meta["policy_code"],
        chunks=len(chunks),
    )

    async with get_db() as db:
        from sqlalchemy import select

        # Upsert Policy record
        result = await db.execute(
            select(Policy).where(Policy.policy_code == meta["policy_code"])
        )
        policy = result.scalar_one_or_none()

        if policy is None:
            policy = Policy(
                id=uuid.uuid4(),
                policy_code=meta["policy_code"],
                name=meta["name"],
                description=meta.get("description"),
                category=meta["category"],
                severity=meta["severity"],
                version=meta["version"],
                active=True,
                source_file=file_path.name,
            )
            db.add(policy)
            await db.flush()  # get the ID
            logger.info("policy_created", policy_code=meta["policy_code"])
        else:
            # Update existing
            policy.name = meta["name"]
            policy.description = meta.get("description")
            policy.category = meta["category"]
            policy.severity = meta["severity"]
            policy.source_file = file_path.name
            logger.info("policy_updated", policy_code=meta["policy_code"])

        # Delete existing chunks for this policy (full re-index)
        from sqlalchemy import delete
        await db.execute(delete(PolicyChunk).where(PolicyChunk.policy_id == policy.id))

        # Embed all chunks in a batch
        embeddings = embed_batch(chunks)

        # Insert new chunks
        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            chunk = PolicyChunk(
                id=uuid.uuid4(),
                policy_id=policy.id,
                chunk_text=chunk_text,
                chunk_index=idx,
                embedding=embedding,
                policy_code=policy.policy_code,
                policy_name=policy.name,
                category=policy.category,
                severity=policy.severity,
                version=policy.version,
                source_file=file_path.name,
            )
            db.add(chunk)

        await db.commit()

    return {
        "policy_code": meta["policy_code"],
        "policy_name": meta["name"],
        "file": file_path.name,
        "chunks_created": len(chunks),
    }


async def ingest_all_policies(policies_dir: Path | None = None) -> list[dict[str, Any]]:
    """
    Ingest all .md files from the knowledge/policies directory.
    """
    if policies_dir is None:
        # Resolve relative to project root
        project_root = Path(__file__).parent.parent.parent.parent.parent
        policies_dir = project_root / "knowledge" / "policies"

    if not policies_dir.exists():
        raise FileNotFoundError(f"Policies directory not found: {policies_dir}")

    md_files = sorted(policies_dir.glob("*.md"))
    if not md_files:
        logger.warning("no_policy_files_found", directory=str(policies_dir))
        return []

    results = []
    for md_file in md_files:
        try:
            result = await ingest_policy_file(md_file)
            results.append(result)
        except Exception as e:
            logger.error("policy_ingestion_failed", file=md_file.name, error=str(e))

    logger.info("ingestion_complete", total_policies=len(results))
    return results

