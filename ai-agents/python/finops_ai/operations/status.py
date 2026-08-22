from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker


@dataclass(frozen=True)
class RunStatusRecord:
    id: str
    run_type: str
    source_id: str | None
    status: str
    documents_processed: int
    chunks_created: int
    chunks_updated: int
    chunks_deprecated: int
    started_at: datetime
    completed_at: datetime | None


class RunsStatusRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    @classmethod
    def from_url(cls, db_url: str) -> "RunsStatusRepository":
        engine = create_engine(db_url, future=True)
        return cls(session_factory=sessionmaker(bind=engine, future=True))

    def list_recent_runs(self, limit: int = 20) -> list[RunStatusRecord]:
        sql = text(
            """
            SELECT
              id,
              run_type,
              source_id,
              status,
              documents_processed,
              chunks_created,
              chunks_updated,
              chunks_deprecated,
              started_at,
              completed_at
            FROM finops.kb_ingestion_runs
            ORDER BY started_at DESC
            LIMIT :limit
            """
        )

        with self._session_factory() as session:
            rows = session.execute(sql, {"limit": limit}).mappings().all()

        return [
            RunStatusRecord(
                id=row["id"],
                run_type=row["run_type"],
                source_id=row["source_id"],
                status=row["status"],
                documents_processed=int(row["documents_processed"]),
                chunks_created=int(row["chunks_created"]),
                chunks_updated=int(row["chunks_updated"]),
                chunks_deprecated=int(row["chunks_deprecated"]),
                started_at=row["started_at"],
                completed_at=row["completed_at"],
            )
            for row in rows
        ]
