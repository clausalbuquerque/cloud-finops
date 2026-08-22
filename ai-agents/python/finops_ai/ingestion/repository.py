from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .contracts import ChunkUpsertResult, ChunkedDocument, UpsertDocumentResult


class Base(DeclarativeBase):
    pass


class KbDocumentRecord(Base):
    __tablename__ = "kb_documents"
    __table_args__ = {"schema": "finops"}

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    source_id: Mapped[str] = mapped_column(String, unique=True)
    source_url: Mapped[str] = mapped_column(String)
    provider: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    content_hash: Mapped[str] = mapped_column(String)
    last_fetched: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_changed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetch_status: Mapped[str] = mapped_column(String, default="success")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class KbIngestionRunRecord(Base):
    __tablename__ = "kb_ingestion_runs"
    __table_args__ = {"schema": "finops"}

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    run_type: Mapped[str] = mapped_column(String)
    source_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String)
    documents_processed: Mapped[int] = mapped_column(Integer, default=0)
    chunks_created: Mapped[int] = mapped_column(Integer, default=0)
    chunks_updated: Mapped[int] = mapped_column(Integer, default=0)
    chunks_deprecated: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class KbChunkRecord(Base):
    __tablename__ = "kb_chunks"
    __table_args__ = {"schema": "finops"}

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    document_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String)
    provider: Mapped[str] = mapped_column(String)
    resource_type: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    source_url: Mapped[str] = mapped_column(String)
    last_verified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_deprecated: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)


class IngestionRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    @classmethod
    def from_url(cls, db_url: str) -> "IngestionRepository":
        engine = create_engine(db_url, future=True)
        return cls(session_factory=sessionmaker(bind=engine, future=True))

    def create_run(self, source_id: str | None, run_type: str = "ingest") -> str:
        run_id = str(uuid4())
        now = datetime.now(timezone.utc)

        with self._session_factory() as session:
            session.add(
                KbIngestionRunRecord(
                    id=run_id,
                    run_type=run_type,
                    source_id=source_id,
                    status="running",
                    documents_processed=0,
                    chunks_created=0,
                    chunks_updated=0,
                    chunks_deprecated=0,
                    errors=None,
                    started_at=now,
                    completed_at=None,
                )
            )
            session.commit()

        return run_id

    def complete_run(
        self,
        run_id: str,
        status: str,
        documents_processed: int,
        chunks_created: int,
        chunks_updated: int,
        chunks_deprecated: int,
        errors: list[dict[str, str]],
    ) -> None:
        with self._session_factory() as session:
            run = session.get(KbIngestionRunRecord, run_id)
            if run is None:
                raise RuntimeError(f"Unknown ingestion run id: {run_id}")

            run.status = status
            run.documents_processed = documents_processed
            run.chunks_created = chunks_created
            run.chunks_updated = chunks_updated
            run.chunks_deprecated = chunks_deprecated
            run.errors = {"items": errors} if errors else None
            run.completed_at = datetime.now(timezone.utc)
            session.commit()

    def upsert_document(
        self,
        source_id: str,
        source_url: str,
        provider: str,
        category: str,
        content_hash: str,
        fetched_at: datetime,
        force_full: bool,
    ) -> UpsertDocumentResult:
        with self._session_factory() as session:
            existing = session.execute(
                select(KbDocumentRecord).where(KbDocumentRecord.source_id == source_id)
            ).scalar_one_or_none()

            if existing is None:
                document_id = str(uuid4())
                session.add(
                    KbDocumentRecord(
                        id=document_id,
                        source_id=source_id,
                        source_url=source_url,
                        provider=provider,
                        category=category,
                        content_hash=content_hash,
                        last_fetched=fetched_at,
                        last_changed=fetched_at,
                        fetch_status="success",
                        is_active=True,
                    )
                )
                session.commit()
                return UpsertDocumentResult(changed=True, document_id=document_id)

            content_changed = force_full or existing.content_hash != content_hash
            existing.source_url = source_url
            existing.provider = provider
            existing.category = category
            existing.fetch_status = "success"
            existing.last_fetched = fetched_at
            if content_changed:
                existing.content_hash = content_hash
                existing.last_changed = fetched_at

            session.commit()
            return UpsertDocumentResult(changed=content_changed, document_id=existing.id)

    def upsert_chunks(
        self,
        document_id: str,
        chunks: list[ChunkedDocument],
        fetched_at: datetime,
        provider: str,
        resource_type: str,
        category: str,
        source_url: str,
    ) -> ChunkUpsertResult:
        with self._session_factory() as session:
            existing_rows = session.execute(
                select(KbChunkRecord).where(KbChunkRecord.document_id == document_id)
            ).scalars()
            existing_by_index = {row.chunk_index: row for row in existing_rows}

            created = 0
            updated = 0
            deprecated = 0

            active_indices: set[int] = set()
            for chunk in chunks:
                active_indices.add(chunk.chunk_index)
                existing = existing_by_index.get(chunk.chunk_index)

                if existing is None:
                    session.add(
                        KbChunkRecord(
                            id=str(uuid4()),
                            document_id=document_id,
                            chunk_index=chunk.chunk_index,
                            content=chunk.content,
                            token_count=chunk.token_count,
                            content_hash=chunk.content_hash,
                            provider=provider,
                            resource_type=resource_type,
                            category=category,
                            source_url=source_url,
                            last_verified=fetched_at,
                            is_deprecated=False,
                            metadata_json=chunk.metadata,
                        )
                    )
                    created += 1
                    continue

                has_changes = (
                    existing.content_hash != chunk.content_hash
                    or existing.content != chunk.content
                    or existing.token_count != chunk.token_count
                    or existing.is_deprecated
                    or existing.metadata_json != chunk.metadata
                )

                existing.content = chunk.content
                existing.token_count = chunk.token_count
                existing.content_hash = chunk.content_hash
                existing.provider = provider
                existing.resource_type = resource_type
                existing.category = category
                existing.source_url = source_url
                existing.last_verified = fetched_at
                existing.is_deprecated = False
                existing.metadata_json = chunk.metadata

                if has_changes:
                    updated += 1

            for idx, row in existing_by_index.items():
                if idx not in active_indices and not row.is_deprecated:
                    row.is_deprecated = True
                    deprecated += 1

            session.commit()
            return ChunkUpsertResult(created=created, updated=updated, deprecated=deprecated)
