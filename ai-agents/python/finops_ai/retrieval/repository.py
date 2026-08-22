from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .contracts import RetrievedChunk


class RetrievalRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    @classmethod
    def from_url(cls, db_url: str) -> "RetrievalRepository":
        engine = create_engine(db_url, future=True)
        return cls(session_factory=sessionmaker(bind=engine, future=True))

    def search_chunks(
        self,
        query_vector: list[float],
        provider: str,
        resource_type: str,
        category: str | None,
        fresh_after: datetime,
        top_k: int,
    ) -> list[RetrievedChunk]:
        vector_literal = "[" + ",".join(f"{item:.8f}" for item in query_vector) + "]"

        sql = text(
            """
            SELECT
              c.id AS chunk_id,
              c.content,
              (1 - (e.embedding <=> CAST(:query_vector AS vector))) AS score,
              c.source_url,
              c.last_verified,
              c.category,
              c.provider,
              c.resource_type
            FROM finops.kb_chunks c
            JOIN finops.kb_embeddings e ON e.chunk_id = c.id
            WHERE c.provider = :provider
              AND c.resource_type = :resource_type
              AND c.is_deprecated = false
              AND c.last_verified >= :fresh_after
                            AND (CAST(:category AS text) IS NULL OR c.category = CAST(:category AS text))
            ORDER BY e.embedding <=> CAST(:query_vector AS vector)
            LIMIT :top_k
            """
        )

        params = {
            "query_vector": vector_literal,
            "provider": provider,
            "resource_type": resource_type,
            "fresh_after": fresh_after,
            "category": category,
            "top_k": top_k,
        }

        with self._session_factory() as session:
            rows = session.execute(sql, params).mappings().all()

        return [
            RetrievedChunk(
                content=row["content"],
                score=float(row["score"]),
                source_url=row["source_url"],
                last_verified=row["last_verified"],
                category=row["category"],
                provider=row["provider"],
                resource_type=row["resource_type"],
                chunk_id=row["chunk_id"],
            )
            for row in rows
        ]

    def count_candidates(
        self,
        provider: str,
        resource_type: str,
        category: str | None,
        fresh_after: datetime,
    ) -> int:
        sql = text(
            """
            SELECT COUNT(*) AS count
            FROM finops.kb_chunks c
            JOIN finops.kb_embeddings e ON e.chunk_id = c.id
            WHERE c.provider = :provider
              AND c.resource_type = :resource_type
              AND c.is_deprecated = false
              AND c.last_verified >= :fresh_after
                            AND (CAST(:category AS text) IS NULL OR c.category = CAST(:category AS text))
            """
        )

        params = {
            "provider": provider,
            "resource_type": resource_type,
            "fresh_after": fresh_after,
            "category": category,
        }

        with self._session_factory() as session:
            row = session.execute(sql, params).mappings().one()
        return int(row["count"])
