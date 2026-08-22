from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import time
from pathlib import Path

from sqlalchemy import create_engine, text

from finops_ai.embedding import EmbeddingService, EmbeddingServiceConfig
from finops_ai.retrieval import (
    ProviderContextRetrievalService,
    RetrieveProviderContextInput,
    RetrievalRepository,
)


PRESET_QUERIES: dict[str, list[str]] = {
    "finops": [
        "How can I reduce compute cost without impacting reliability?",
        "What are discount options for long-running workloads?",
        "How should I right-size underutilized virtual machines?",
    ],
    "sre": [
        "What reliability best practices should I apply to this architecture?",
        "How should monitoring and alerting be structured for production services?",
        "What are common failure domains and mitigation patterns?",
    ],
    "azure": [
        "What are Azure Well-Architected reliability recommendations?",
        "When should I use AKS vs App Service vs Functions?",
        "How should I design Azure networking for secure workloads?",
    ],
    "gcp": [
        "How do committed use discounts affect compute pricing?",
        "What are best practices for machine type recommendations?",
        "How should I organize projects and IAM for governance?",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start/check DB and run quick RAG retrieval smoke queries"
    )
    parser.add_argument("--provider", default="GCP", help="Provider filter (e.g., GCP, AZURE)")
    parser.add_argument("--resource-type", default="compute/instance")
    parser.add_argument("--category", default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-age-days", type=int, default=30)
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument(
        "--preset",
        choices=sorted(PRESET_QUERIES.keys()),
        default=None,
        help="Run a preset query pack",
    )
    parser.add_argument("--interactive", action="store_true", help="Prompt for queries in a loop")
    parser.add_argument("--start-db", action="store_true", help="Run docker compose up -d postgres")
    parser.add_argument("--db-timeout-sec", type=int, default=90)
    parser.add_argument("--show-stats", action="store_true", help="Print provider KB counts before querying")
    parser.add_argument(
        "--database-url",
        default=None,
        help="Optional override for DATABASE_URL",
    )
    parser.add_argument(
        "--compose-service",
        default="postgres",
        help="Compose service name for DB startup",
    )
    return parser.parse_args()


def _find_repo_root() -> Path:
    # scripts/ -> python/ -> ai-agents/ -> repo root
    return Path(__file__).resolve().parents[3]


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    print("$", " ".join(shlex.quote(part) for part in cmd))
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def _start_database_service(compose_service: str) -> None:
    repo_root = _find_repo_root()
    _run(["docker", "compose", "up", "-d", compose_service], cwd=repo_root)


def _wait_for_db(database_url: str, timeout_sec: int) -> None:
    deadline = time.time() + timeout_sec
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            engine = create_engine(database_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception as exc:  # pragma: no cover - connectivity is environment dependent
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f"Database did not become ready within {timeout_sec}s") from last_error


def _print_provider_stats(database_url: str, provider: str) -> None:
    engine = create_engine(database_url)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    (SELECT COUNT(*) FROM finops.kb_documents WHERE provider = :provider AND is_active = true) AS documents,
                    (SELECT COUNT(*) FROM finops.kb_chunks WHERE provider = :provider AND is_deprecated = false) AS chunks,
                    (SELECT COUNT(*) FROM finops.kb_embeddings e JOIN finops.kb_chunks c ON c.id = e.chunk_id WHERE c.provider = :provider) AS embeddings
                """
            ),
            {"provider": provider.upper()},
        ).mappings().one()
    print("Provider corpus stats")
    print(f"provider={provider.upper()} documents={row['documents']} chunks={row['chunks']} embeddings={row['embeddings']}")


def _query_once(
    service: ProviderContextRetrievalService,
    provider: str,
    resource_type: str,
    category: str | None,
    top_k: int,
    max_age_days: int,
    query: str,
) -> None:
    print("\n=== Query ===")
    print(query)

    result = service.retrieve_provider_context(
        RetrieveProviderContextInput(
            provider=provider,
            resource_type=resource_type,
            query=query,
            category=category,
            top_k=top_k,
            max_age_days=max_age_days,
        )
    )

    print("Retrieval result")
    print(f"total_candidates={result.metadata.total_candidates}")
    print(f"returned={len(result.chunks)}")
    print(f"latency_ms={result.metadata.search_latency_ms:.2f}")
    for idx, chunk in enumerate(result.chunks, start=1):
        snippet = chunk.content[:220].replace("\n", " ")
        print(f"[{idx}] score={chunk.score:.4f} source={chunk.source_url}")
        print(snippet)


def _resolve_queries(args: argparse.Namespace) -> list[str]:
    queries = list(args.query)
    if args.preset:
        queries.extend(PRESET_QUERIES[args.preset])
    return queries


def main() -> None:
    args = parse_args()

    database_url = args.database_url or os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required (or pass --database-url)")

    if args.start_db:
        _start_database_service(args.compose_service)

    _wait_for_db(database_url, args.db_timeout_sec)

    if args.show_stats:
        _print_provider_stats(database_url, args.provider)

    repository = RetrievalRepository.from_url(database_url)
    embedding_service = EmbeddingService(config=EmbeddingServiceConfig.from_env())
    service = ProviderContextRetrievalService(repository=repository, embedding_service=embedding_service)

    queries = _resolve_queries(args)
    for query in queries:
        _query_once(
            service=service,
            provider=args.provider,
            resource_type=args.resource_type,
            category=args.category,
            top_k=args.top_k,
            max_age_days=args.max_age_days,
            query=query,
        )

    if args.interactive:
        print("\nInteractive mode. Enter blank line or 'exit' to finish.")
        while True:
            query = input("query> ").strip()
            if not query or query.lower() in {"exit", "quit"}:
                break
            _query_once(
                service=service,
                provider=args.provider,
                resource_type=args.resource_type,
                category=args.category,
                top_k=args.top_k,
                max_age_days=args.max_age_days,
                query=query,
            )

    if not queries and not args.interactive:
        print("No queries provided. Use --query, --preset, or --interactive.")


if __name__ == "__main__":
    main()
