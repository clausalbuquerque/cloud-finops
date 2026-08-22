from __future__ import annotations

import re

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_LONG_NUMBER = re.compile(r"\b\d{9,}\b")
_HF_TOKEN = re.compile(r"\b(hf_[A-Za-z0-9]{10,})\b")
_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]+")


def redact_text(value: str, max_len: int = 160) -> str:
    redacted = _EMAIL.sub("<email>", value)
    redacted = _LONG_NUMBER.sub("<number>", redacted)
    redacted = _HF_TOKEN.sub("<token>", redacted)
    redacted = _BEARER.sub("Bearer <token>", redacted)
    if len(redacted) <= max_len:
        return redacted
    return redacted[:max_len] + "..."
