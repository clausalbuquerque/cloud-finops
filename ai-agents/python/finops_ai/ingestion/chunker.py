from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256

from .contracts import ChunkedDocument, ProviderDocSource


@dataclass(frozen=True)
class ChunkerConfig:
    max_tokens: int = 512
    overlap_tokens: int = 50
    min_chunk_tokens: int = 80


class SectionAwareChunker:
    def __init__(self, config: ChunkerConfig | None = None) -> None:
        self._config = config or ChunkerConfig()

    def chunk(self, normalized_text: str, source: ProviderDocSource) -> list[ChunkedDocument]:
        sections = self._split_sections(normalized_text)

        raw_chunks: list[ChunkedDocument] = []
        for section_title, section_text in sections:
            section_chunks = self._chunk_section(section_text)
            for chunk_text, token_count in section_chunks:
                metadata = {
                    "provider": source.provider,
                    "resource_type": source.resource_type,
                    "category": source.category,
                    "source_url": source.source_url,
                    "source_id": source.source_id,
                    "section": section_title,
                }
                content_hash = sha256(chunk_text.encode("utf-8")).hexdigest()
                raw_chunks.append(
                    ChunkedDocument(
                        chunk_index=0,
                        content=chunk_text,
                        token_count=token_count,
                        content_hash=content_hash,
                        metadata=metadata,
                    )
                )

        merged = self._merge_small_chunks(raw_chunks)
        deduped = self._deduplicate(merged)

        final_chunks: list[ChunkedDocument] = []
        for idx, chunk in enumerate(deduped):
            if not chunk.content.strip():
                continue
            if chunk.token_count > self._config.max_tokens:
                continue
            final_chunks.append(
                ChunkedDocument(
                    chunk_index=idx,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    content_hash=chunk.content_hash,
                    metadata=chunk.metadata,
                )
            )
        return final_chunks

    @staticmethod
    def tokenize(text: str) -> list[str]:
        return re.findall(r"\w+|[^\w\s]", text)

    @staticmethod
    def _split_sections(text: str) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        current_title = "untitled"
        current_lines: list[str] = []

        for line in text.splitlines():
            striped = line.strip()
            if striped.startswith("## ") or striped.startswith("### "):
                if current_lines:
                    sections.append((current_title, "\n".join(current_lines).strip()))
                current_title = striped.lstrip("# ").strip() or "untitled"
                current_lines = []
                continue
            current_lines.append(line)

        if current_lines:
            sections.append((current_title, "\n".join(current_lines).strip()))

        if not sections:
            return [("untitled", text)]
        return sections

    def _chunk_section(self, section_text: str) -> list[tuple[str, int]]:
        tokens = self.tokenize(section_text)
        if not tokens:
            return []

        step = max(1, self._config.max_tokens - self._config.overlap_tokens)
        chunks: list[tuple[str, int]] = []

        for start in range(0, len(tokens), step):
            end = start + self._config.max_tokens
            window = tokens[start:end]
            if not window:
                continue
            chunk_text = self._detokenize(window)
            chunks.append((chunk_text, len(window)))
            if end >= len(tokens):
                break

        return chunks

    @staticmethod
    def _detokenize(tokens: list[str]) -> str:
        text = " ".join(tokens)
        text = re.sub(r"\s+([.,;:!?])", r"\1", text)
        text = re.sub(r"\(\s+", "(", text)
        text = re.sub(r"\s+\)", ")", text)
        return text.strip()

    def _merge_small_chunks(self, chunks: list[ChunkedDocument]) -> list[ChunkedDocument]:
        if not chunks:
            return []

        merged: list[ChunkedDocument] = []
        for chunk in chunks:
            if (
                merged
                and chunk.token_count < self._config.min_chunk_tokens
                and merged[-1].metadata == chunk.metadata
            ):
                merged_content = f"{merged[-1].content}\n{chunk.content}".strip()
                merged_tokens = self.tokenize(merged_content)
                merged[-1] = ChunkedDocument(
                    chunk_index=0,
                    content=merged_content,
                    token_count=len(merged_tokens),
                    content_hash=sha256(merged_content.encode("utf-8")).hexdigest(),
                    metadata=merged[-1].metadata,
                )
            else:
                merged.append(chunk)

        return merged

    @staticmethod
    def _deduplicate(chunks: list[ChunkedDocument]) -> list[ChunkedDocument]:
        seen_hashes: set[str] = set()
        deduped: list[ChunkedDocument] = []

        for chunk in chunks:
            if chunk.content_hash in seen_hashes:
                continue
            seen_hashes.add(chunk.content_hash)
            deduped.append(chunk)

        return deduped
