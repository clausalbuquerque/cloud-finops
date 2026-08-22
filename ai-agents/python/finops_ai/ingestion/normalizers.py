from __future__ import annotations

import io
import re
from datetime import datetime, timezone
from hashlib import sha256

from bs4 import BeautifulSoup
from pypdf import PdfReader

from .contracts import FetchedDocument, NormalizedDocument, SourceFormat


def normalize_document(document: FetchedDocument) -> NormalizedDocument:
    if document.source_format is SourceFormat.HTML:
        normalized_text = _normalize_html(document.raw_content)
    elif document.source_format is SourceFormat.MARKDOWN:
        normalized_text = _normalize_markdown(document.raw_content)
    elif document.source_format is SourceFormat.PDF:
        normalized_text = _normalize_pdf(document.raw_content)
    else:
        raise ValueError(f"Unsupported source format: {document.source_format}")

    normalized_text = _sanitize_adversarial_content(normalized_text)
    normalized_text = _collapse_whitespace(normalized_text)
    content_hash = sha256(normalized_text.encode("utf-8")).hexdigest()

    return NormalizedDocument(
        normalized_text=normalized_text,
        content_hash=content_hash,
        fetched_at=document.fetched_at.astimezone(timezone.utc),
    )


def _normalize_html(raw_content: bytes) -> str:
    soup = BeautifulSoup(raw_content.decode("utf-8", errors="ignore"), "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.extract()

    # Preserve section boundaries for downstream H2/H3-aware chunking.
    for heading in soup.find_all(["h2", "h3"]):
        prefix = "## " if heading.name == "h2" else "### "
        heading.insert_before(f"\n{prefix}{heading.get_text(strip=True)}\n")

    return soup.get_text(separator="\n")


def _normalize_markdown(raw_content: bytes) -> str:
    text = raw_content.decode("utf-8", errors="ignore")
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    return text


def _normalize_pdf(raw_content: bytes) -> str:
    reader = PdfReader(io.BytesIO(raw_content))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _collapse_whitespace(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _sanitize_adversarial_content(text: str) -> str:
    blocked_patterns = [
        r"ignore\s+previous\s+instructions",
        r"system\s+prompt",
        r"you\s+are\s+chatgpt",
        r"developer\s+message",
        r"do\s+not\s+follow\s+policy",
        r"BEGIN\s+PROMPT",
        r"END\s+PROMPT",
    ]
    compiled = [re.compile(pattern, flags=re.IGNORECASE) for pattern in blocked_patterns]

    safe_lines: list[str] = []
    for line in text.splitlines():
        if any(pattern.search(line) for pattern in compiled):
            continue
        safe_lines.append(line)

    return "\n".join(safe_lines)
