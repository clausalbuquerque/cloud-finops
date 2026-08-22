from __future__ import annotations

from typing import Protocol

from .contracts import EmbeddingMode

try:
    import truststore

    truststore.inject_into_ssl()
except Exception:  # pragma: no cover
    # If truststore is unavailable, fallback to default SSL behavior.
    pass


class EmbeddingBackend(Protocol):
    def embed_texts(self, texts: list[str], mode: EmbeddingMode) -> list[list[float]]:
        """Generate vectors for the provided texts."""


class NomicEmbeddingBackend:
    """
    Local OSS embedding backend using sentence-transformers.

    Uses the same model for both index and query embedding paths.
    """

    def __init__(
        self,
        model_name: str,
        huggingface_token: str | None = None,
        local_files_only: bool = False,
    ) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "sentence-transformers is required for NomicEmbeddingBackend"
            ) from exc

        self._model = SentenceTransformer(
            model_name,
            token=huggingface_token,
            local_files_only=local_files_only,
            trust_remote_code=True,
        )

    def embed_texts(self, texts: list[str], mode: EmbeddingMode) -> list[list[float]]:
        if not texts:
            return []

        prompt_prefix = "search_document: " if mode is EmbeddingMode.INDEX else "search_query: "
        prepared = [f"{prompt_prefix}{text}" for text in texts]

        vectors = self._model.encode(
            prepared,
            batch_size=len(prepared),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()
