from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class EmbeddingServiceConfig:
    model_name: str = "nomic-ai/nomic-embed-text-v1.5"
    dimensions: int = 768
    batch_size: int = 16
    timeout_seconds: float = 15.0
    max_retries: int = 3
    retry_backoff_seconds: float = 0.5
    huggingface_token: str | None = None
    local_files_only: bool = False

    @classmethod
    def from_env(cls) -> "EmbeddingServiceConfig":
        return cls(
            model_name=os.getenv("EMBEDDING_MODEL_NAME", cls.model_name),
            dimensions=int(os.getenv("EMBEDDING_DIMENSION", str(cls.dimensions))),
            batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", str(cls.batch_size))),
            timeout_seconds=float(
                os.getenv("EMBEDDING_TIMEOUT_SECONDS", str(cls.timeout_seconds))
            ),
            max_retries=int(os.getenv("EMBEDDING_MAX_RETRIES", str(cls.max_retries))),
            retry_backoff_seconds=float(
                os.getenv(
                    "EMBEDDING_RETRY_BACKOFF_SECONDS", str(cls.retry_backoff_seconds)
                )
            ),
            huggingface_token=(
                os.getenv("HF_TOKEN")
                or os.getenv("HUGGINGFACEHUB_API_TOKEN")
                or os.getenv("HUGGINGFACE_API_TOKEN")
                or os.getenv("hf_token")
            ),
            local_files_only=os.getenv("EMBEDDING_LOCAL_FILES_ONLY", "false").lower()
            in {"1", "true", "yes", "on"},
        )
