"""LLM factory for the FinOps/SRE agents.

Single source for constructing a configured ``crewai.LLM`` so the model is
swappable in one place. Targets **Google Gemini via Vertex AI** per
``ai-agents/docs/adr-agent-runtime.md``:

- **Dev/test:** Vertex AI *Express mode* — an API key in ``GCP_AGENTS_API_KEY``
  (root ``.env``). We set ``GOOGLE_GENAI_USE_VERTEXAI=true`` and pass the key.
- **Prod:** Application Default Credentials (no key) with ``GOOGLE_CLOUD_PROJECT``
  and ``GOOGLE_CLOUD_LOCATION`` (``gcloud auth application-default login``).

The Gemini model per role is chosen by ``tier`` ("pro" | "flash"), resolved from
``GEMINI_MODEL_PRO`` / ``GEMINI_MODEL_FLASH`` env vars with sensible defaults.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    # Use the OS trust store for TLS so the Gemini client works behind
    # enterprise TLS interception / self-signed corporate CA chains.
    import truststore

    truststore.inject_into_ssl()
except Exception:  # pragma: no cover - fallback to default SSL behavior
    pass

try:  # python-dotenv is a declared dependency, but keep import defensive.
    from dotenv import find_dotenv, load_dotenv
except ImportError:  # pragma: no cover - only if deps not installed yet
    find_dotenv = None  # type: ignore[assignment]
    load_dotenv = None  # type: ignore[assignment]

# Verify current IDs in the Vertex AI model catalog before pinning for prod.
DEFAULT_MODEL_PRO = "gemini/gemini-2.5-pro"
DEFAULT_MODEL_FLASH = "gemini/gemini-2.5-flash"

_FLASH_ALIASES = {"flash", "fast", "cheap", "lite"}


def _load_env() -> None:
    """Load environment variables from the nearest and the repo-root ``.env``.

    Values already present in ``os.environ`` win (``override=False``). The nearest
    ``.env`` (``ai-agents/python/.env``, synced from the root by
    ``scripts/sync-env.sh``) is loaded first, then the repository root ``.env`` as
    a fallback for direct runs.
    """
    if load_dotenv is None:
        return
    if find_dotenv is not None:
        nearest = find_dotenv(usecwd=True)
        if nearest:
            load_dotenv(nearest, override=False)
    # …/ai-agents/python/finops_ai/llm.py -> parents[3] == repo root
    root_env = Path(__file__).resolve().parents[3] / ".env"
    if root_env.is_file():
        load_dotenv(root_env, override=False)


def resolve_model(tier: str) -> str:
    """Map a role tier to a Gemini model string."""
    key = (tier or "pro").strip().lower()
    if key in _FLASH_ALIASES:
        return os.getenv("GEMINI_MODEL_FLASH", DEFAULT_MODEL_FLASH)
    return os.getenv("GEMINI_MODEL_PRO", DEFAULT_MODEL_PRO)


def build_llm(tier: str = "pro", **overrides: Any):
    """Build a configured ``crewai.LLM`` for Gemini via Vertex AI.

    Args:
        tier: Role tier — ``"pro"`` (deeper reasoning) or ``"flash"`` (cheaper/faster).
        **overrides: Passed through to ``crewai.LLM`` (e.g. ``model``, ``temperature``,
            ``max_tokens``, ``timeout``). ``model`` overrides the tier resolution.

    Returns:
        A ``crewai.LLM`` instance.

    Raises:
        RuntimeError: If no credentials are configured (neither an Express-mode API
            key nor a GCP project for ADC).
    """
    _load_env()
    from crewai import LLM  # lazy import keeps module import cheap and dependency-light

    model = overrides.pop("model", None) or resolve_model(tier)

    api_key = (
        os.getenv("GCP_AGENTS_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or None
    location = os.getenv("GOOGLE_CLOUD_LOCATION") or None

    # Both Express-mode and service-account Vertex use the Vertex backend.
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")

    if api_key:
        # Vertex AI Express mode: API key only (no project/location).
        os.environ.setdefault("GOOGLE_API_KEY", api_key)
        return LLM(model=model, api_key=api_key, **overrides)

    if project:
        # Service-account / ADC mode.
        kwargs: dict[str, Any] = {"project": project}
        if location:
            kwargs["location"] = location
        kwargs.update(overrides)
        return LLM(model=model, **kwargs)

    raise RuntimeError(
        "No Gemini credentials found. Set GCP_AGENTS_API_KEY (Express mode) or "
        "GOOGLE_CLOUD_PROJECT + ADC (`gcloud auth application-default login`) in the "
        "root .env, then run ./scripts/sync-env.sh."
    )
