#!/usr/bin/env python
"""
Policy ingestion script.

Reads all Markdown files from knowledge/policies/
and loads them into PostgreSQL with pgvector embeddings.

Usage:
    uv run python scripts/ingest_policies.py
    uv run python scripts/ingest_policies.py --policies-dir /path/to/policies
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def main() -> None:
    import argparse
    import structlog

    # Basic logging for script output
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
    )
    logger = structlog.get_logger()

    parser = argparse.ArgumentParser(description="Ingest governance policy documents into pgvector")
    parser.add_argument(
        "--policies-dir",
        type=Path,
        default=None,
        help="Path to policies directory (default: knowledge/policies/)",
    )
    args = parser.parse_args()

    logger.info("policy_ingestion_starting")

    from backend.app.rag.ingestion import ingest_all_policies

    results = await ingest_all_policies(policies_dir=args.policies_dir)

    print("\n" + "=" * 60)
    print("POLICY INGESTION COMPLETE")
    print("=" * 60)
    for r in results:
        print(f"  ✓ {r['policy_code']:20s}  {r['policy_name'][:40]:40s}  ({r['chunks_created']} chunks)")
    print(f"\nTotal policies ingested: {len(results)}")
    total_chunks = sum(r["chunks_created"] for r in results)
    print(f"Total chunks embedded:  {total_chunks}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

