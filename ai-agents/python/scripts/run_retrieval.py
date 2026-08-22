from __future__ import annotations

import argparse
import os

from finops_ai.embedding import EmbeddingService, EmbeddingServiceConfig
from finops_ai.retrieval import (
    ProviderContextRetrievalService,
    RetrieveProviderContextInput,
    RetrievalRepository,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrieve provider context from vector index")
    parser.add_argument("--provider", required=True)
    parser.add_argument("--resource-type", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--category", default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-age-days", type=int, default=30)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is required")

    repository = RetrievalRepository.from_url(db_url)
    embedding_service = EmbeddingService(config=EmbeddingServiceConfig.from_env())
    service = ProviderContextRetrievalService(repository=repository, embedding_service=embedding_service)

    result = service.retrieve_provider_context(
        RetrieveProviderContextInput(
            provider=args.provider,
            resource_type=args.resource_type,
            query=args.query,
            category=args.category,
            top_k=args.top_k,
            max_age_days=args.max_age_days,
        )
    )

    print("Retrieval result")
    print(f"total_candidates={result.metadata.total_candidates}")
    print(f"returned={len(result.chunks)}")
    print(f"latency_ms={result.metadata.search_latency_ms:.2f}")
    for idx, chunk in enumerate(result.chunks, start=1):
        print(f"[{idx}] score={chunk.score:.4f} source={chunk.source_url}")
        print(chunk.content[:240].replace("\n", " "))


if __name__ == "__main__":
    main()
