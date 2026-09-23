"""
Semantic policy retriever using pgvector cosine similarity search.

Agents call retrieve_policies() to get relevant policy chunks for
a given input. They never receive raw database access.
"""
from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import text

from backend.app.config.settings import get_settings
from backend.app.db.session import get_db
from backend.app.rag.embeddings import embed_text

logger = structlog.get_logger(__name__)


class PolicyRetriever:
    """
    Retrieves relevant policy chunks using cosine similarity on pgvector.

    Each result includes the chunk text and full policy metadata so
    agents can cite sources accurately.
    """

    def __init__(self, top_k: int | None = None):
        self.top_k = top_k or get_settings().retrieval_top_k

    async def retrieve(
        self,
        query: str,
        category_filter: list[str] | None = None,
        severity_filter: list[str] | None = None,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve the most relevant policy chunks for a query.

        Args:
            query: The text to find relevant policies for.
            category_filter: Optionally limit to specific policy categories.
            severity_filter: Optionally limit to specific severities.
            top_k: Override default number of results.

        Returns:
            List of dicts with chunk_text and all policy metadata.
        """
        k = top_k or self.top_k
        query_embedding = embed_text(query)

        # Build SQL with optional filters
        # We use raw SQL for the pgvector <=> (cosine distance) operator
        where_clauses = ["pc.severity IS NOT NULL"]  # always at least one clause
        params: dict[str, Any] = {
            "embedding": str(query_embedding),
            "top_k": k,
        }

        if category_filter:
            where_clauses.append("pc.category = ANY(:categories)")
            params["categories"] = category_filter

        if severity_filter:
            where_clauses.append("pc.severity = ANY(:severities)")
            params["severities"] = severity_filter

        where_sql = " AND ".join(where_clauses)

        sql = text(f"""
            SELECT
                pc.id::text            AS chunk_id,
                pc.policy_id::text     AS policy_id,
                pc.chunk_text,
                pc.chunk_index,
                pc.policy_code,
                pc.policy_name,
                pc.category,
                pc.severity,
                pc.version,
                pc.source_file,
                1 - (pc.embedding <=> CAST(:embedding AS vector)) AS similarity_score
            FROM policy_chunks pc
            JOIN policies p ON pc.policy_id = p.id
            WHERE p.active = true AND {where_sql}
            ORDER BY pc.embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """)

        async with get_db() as db:
            result = await db.execute(sql, params)
            rows = result.mappings().all()

        chunks = [dict(row) for row in rows]
        logger.info(
            "policies_retrieved",
            query_length=len(query),
            chunks_returned=len(chunks),
            top_k=k,
        )
        return chunks

    async def retrieve_for_input(self, input_text: str) -> list[dict[str, Any]]:
        """
        Convenience method — retrieve policies relevant to a governance input.
        Automatically broadens the query to cover multiple policy dimensions.
        """
        # Run two queries: one on full input, one on a policy-oriented reformulation
        results = await self.retrieve(query=input_text, top_k=self.top_k)

        # Deduplicate by chunk_id
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for chunk in results:
            if chunk["chunk_id"] not in seen:
                seen.add(chunk["chunk_id"])
                deduped.append(chunk)

        return deduped


# Module-level singleton for convenience
_retriever: PolicyRetriever | None = None


def get_retriever() -> PolicyRetriever:
    global _retriever
    if _retriever is None:
        _retriever = PolicyRetriever()
    return _retriever

