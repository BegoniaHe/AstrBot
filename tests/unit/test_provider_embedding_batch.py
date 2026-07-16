import asyncio

import pytest

from astrbot.core.provider.provider import EmbeddingProvider


class _OutOfOrderEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        super().__init__({"type": "test", "id": "test"}, {})

    async def get_embedding(self, text: str) -> list[float]:
        return [float(len(text))]

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        if texts[0] == "chunk-1":
            await asyncio.sleep(0.05)
        else:
            await asyncio.sleep(0.01)
        return [
            [float(idx)] for idx, _text in enumerate(texts, start=int(texts[0][-1]))
        ]

    def get_dim(self) -> int:
        return 1


class _DefaultDimEmbeddingProvider(EmbeddingProvider):
    async def get_embedding(self, text: str) -> list[float]:
        return [float(len(text))]

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text))] for text in texts]


def test_embedding_provider_uses_shared_dimension_configuration(caplog) -> None:
    provider = _DefaultDimEmbeddingProvider(
        {"type": "test", "embedding_dimensions": "1536"}, {}
    )
    invalid_provider = _DefaultDimEmbeddingProvider(
        {"type": "test", "embedding_dimensions": "not-a-number"}, {}
    )

    assert provider.get_dim() == 1536
    assert invalid_provider.get_dim() == 0
    assert "embedding_dimensions" in caplog.text


@pytest.mark.asyncio
async def test_get_embeddings_batch_preserves_input_order() -> None:
    provider = _OutOfOrderEmbeddingProvider()

    result = await provider.get_embeddings_batch(
        ["chunk-1", "chunk-2", "chunk-3", "chunk-4"],
        batch_size=2,
        tasks_limit=2,
    )

    assert result == [[1.0], [2.0], [3.0], [4.0]]
