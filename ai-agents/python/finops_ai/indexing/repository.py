from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .contracts import ChunkToIndex, IndexingPlan


@dataclass(frozen=True)
class EmbeddingUpsertCounters:
    embedded: int


class IndexingRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    @classmethod
    def from_url(cls, db_url: str) -> "IndexingRepository":
        engine = create_engine(db_url, future=True)
        return cls(session_factory=sessionmaker(bind=engine, future=True))

    def create_run(self, source_id: str | None, run_type: str = "index") -> str:
        run_id = str(uuid4())
        with self._session_factory() as session:
            session.execute(
                text(
                    """
                    INSERT INTO finops.kb_ingestion_runs (
                      id, run_type, source_id, status,
                      documents_processed, chunks_created, chunks_updated, chunks_deprecated,
                      errors, started_at, completed_at
                    ) VALUES (
                      :id, :run_type, :source_id, 'running',
                      0, 0, 0, 0,
                      NULL, :started_at, NULL
                    )
                    """
                ),
                {
                    "id": run_id,
                    "run_type": run_type,
                    "source_id": source_id,
                    "started_at": datetime.now(timezone.utc),
                },
            )
            session.commit()
        return run_id

    def complete_run(
        self,
        run_id: str,
        status: str,
        chunks_created: int,
        chunks_updated: int,
        chunks_deprecated: int,
        errors: list[dict[str, str]],
    ) -> None:
        with self._session_factory() as session:
            session.execute(
                text(
                    """
                    UPDATE finops.kb_ingestion_runs
                    SET status = :status,
                        chunks_created = :chunks_created,
                        chunks_updated = :chunks_updated,
                        chunks_deprecated = :chunks_deprecated,
                        errors = :errors,
                        completed_at = :completed_at
                    WHERE id = :id
                    """
                ),
                {
                    "id": run_id,
                    "status": status,
                    "chunks_created": chunks_created,
                    "chunks_updated": chunks_updated,
                    "chunks_deprecated": chunks_deprecated,
                    "errors": {"items": errors} if errors else None,
                    "completed_at": datetime.now(timezone.utc),
                },
            )
            session.commit()

    def get_indexing_plan(
        self,
        mode: str,
        provider: str | None,
        model_version: str,
    ) -> IndexingPlan:
        provider_filter = ""
        params: dict[str, object] = {"model_version": model_version}
        if provider:
            provider_filter = "AND c.provider = :provider"
            params["provider"] = provider

        if mode == "full":
            embed_query = f"""
                SELECT c.id AS chunk_id, c.content
                FROM finops.kb_chunks c
                WHERE c.is_deprecated = false
                {provider_filter}
                ORDER BY c.id
            """
            skipped_query = "SELECT 0 AS skipped"
        else:
            embed_query = f"""
                SELECT c.id AS chunk_id, c.content
                FROM finops.kb_chunks c
                LEFT JOIN finops.kb_embeddings e ON e.chunk_id = c.id
                WHERE c.is_deprecated = false
                  {provider_filter}
                  AND (
                    e.id IS NULL
                    OR e.model_version <> :model_version
                    OR c.updated_at > e.created_at
                  )
                ORDER BY c.id
            """
            skipped_query = f"""
                SELECT COUNT(*) AS skipped
                FROM finops.kb_chunks c
                LEFT JOIN finops.kb_embeddings e ON e.chunk_id = c.id
                WHERE c.is_deprecated = false
                  {provider_filter}
                  AND e.id IS NOT NULL
                  AND e.model_version = :model_version
                  AND c.updated_at <= e.created_at
            """

        deprecate_query = f"""
            SELECT c.id AS chunk_id
            FROM finops.kb_chunks c
            JOIN finops.kb_embeddings e ON e.chunk_id = c.id
            WHERE c.is_deprecated = true
            {provider_filter}
            ORDER BY c.id
        """

        with self._session_factory() as session:
            to_embed_rows = session.execute(text(embed_query), params).mappings().all()
            to_deprecate_rows = session.execute(text(deprecate_query), params).mappings().all()
            skipped_row = session.execute(text(skipped_query), params).mappings().one()

        to_embed = [ChunkToIndex(chunk_id=row["chunk_id"], content=row["content"]) for row in to_embed_rows]
        to_deprecate = [row["chunk_id"] for row in to_deprecate_rows]

        return IndexingPlan(
            to_embed=to_embed,
            to_deprecate=to_deprecate,
            skipped=int(skipped_row["skipped"]),
        )

    def upsert_embedding(
        self,
        chunk_id: str,
        vector: list[float],
        model_version: str,
    ) -> None:
        vector_literal = "[" + ",".join(f"{item:.8f}" for item in vector) + "]"

        with self._session_factory() as session:
            session.execute(
                text(
                    """
                    INSERT INTO finops.kb_embeddings (id, chunk_id, embedding, model_version, created_at)
                    VALUES (:id, :chunk_id, CAST(:embedding AS vector), :model_version, :created_at)
                    ON CONFLICT (chunk_id)
                    DO UPDATE SET
                      embedding = EXCLUDED.embedding,
                      model_version = EXCLUDED.model_version,
                      created_at = EXCLUDED.created_at
                    """
                ),
                {
                    "id": str(uuid4()),
                    "chunk_id": chunk_id,
                    "embedding": vector_literal,
                    "model_version": model_version,
                    "created_at": datetime.now(timezone.utc),
                },
            )
            session.commit()

    def delete_embeddings_for_chunks(self, chunk_ids: list[str]) -> int:
        if not chunk_ids:
            return 0

        with self._session_factory() as session:
            result = session.execute(
                text("DELETE FROM finops.kb_embeddings WHERE chunk_id = ANY(:chunk_ids)"),
                {"chunk_ids": chunk_ids},
            )
            session.commit()
            return int(result.rowcount or 0)
