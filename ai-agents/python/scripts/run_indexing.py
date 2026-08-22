from __future__ import annotations

import argparse
import os

from finops_ai.embedding import EmbeddingService, EmbeddingServiceConfig
from finops_ai.indexing import ChunkIndexerService, IndexChunksInput, IndexingRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Index chunks into pgvector embeddings")
    parser.add_argument("--mode", choices=["full", "incremental"], default="incremental")
    parser.add_argument("--provider", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is required")

    repository = IndexingRepository.from_url(db_url)
    embedding_service = EmbeddingService(config=EmbeddingServiceConfig.from_env())
    service = ChunkIndexerService(repository=repository, embedding_service=embedding_service)

    result = service.index_chunks(IndexChunksInput(mode=args.mode, provider=args.provider))

    print("Indexing run summary")
    print(f"run_id={result.run_id}")
    print(f"chunks_embedded={result.chunks_embedded}")
    print(f"chunks_skipped={result.chunks_skipped}")
    print(f"chunks_deprecated={result.chunks_deprecated}")
    print(f"errors={len(result.errors)}")


if __name__ == "__main__":
    main()
