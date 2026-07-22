"""Offline security contracts for embedding batch failures."""

import logging

import pytest

from astrbot.core.provider.provider import EmbeddingProvider

pytestmark = pytest.mark.provider

_SENSITIVE_ERROR = (
    "api_key=embedding-api-key "
    "Bearer embedding-bearer-token "
    "password=embedding-password "
    "https://internal.example/embedding "
    "C:\\private\\embedding.txt "
    "/srv/astrbot/embedding.json"
)
_SENSITIVE_VALUES = (
    "embedding-api-key",
    "embedding-bearer-token",
    "embedding-password",
    "https://internal.example/embedding",
    "C:\\private\\embedding.txt",
    "/srv/astrbot/embedding.json",
)


class _FailingEmbeddingProvider(EmbeddingProvider):
    async def get_embedding(self, _text: str) -> list[float]:
        return [0.0]

    async def get_embeddings(self, _texts: list[str]) -> list[list[float]]:
        raise RuntimeError(_SENSITIVE_ERROR)


@pytest.mark.asyncio
async def test_embedding_batch_hides_provider_failure_from_error_and_logs(
    caplog,
) -> None:
    provider = _FailingEmbeddingProvider({"type": "test"}, {})

    with caplog.at_level(logging.WARNING, logger="astrbot"):
        with pytest.raises(
            RuntimeError, match="Embedding batch processing failed"
        ) as caught:
            await provider.get_embeddings_batch(["text"], max_retries=1)

    assert caught.value.__cause__ is None
    for value in _SENSITIVE_VALUES:
        assert value not in str(caught.value)
        assert value not in caplog.text
