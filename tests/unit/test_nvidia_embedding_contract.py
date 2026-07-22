"""Offline error and lifecycle contracts for the NVIDIA embedding adapter."""

import asyncio
import logging

import pytest

from astrbot.core.provider.sources.nvidia_embedding_source import (
    NvidiaEmbeddingProvider,
)

pytestmark = pytest.mark.provider

_SENSITIVE_ERROR = (
    "api_key=nvidia-embedding-api-key "
    "Bearer nvidia-embedding-bearer "
    "password=nvidia-embedding-password "
    "https://internal.example/nvidia-embedding "
    "C:\\private\\nvidia-embedding.txt "
    "/srv/astrbot/nvidia-embedding.json"
)
_SENSITIVE_VALUES = (
    "nvidia-embedding-api-key",
    "nvidia-embedding-bearer",
    "nvidia-embedding-password",
    "https://internal.example/nvidia-embedding",
    "C:\\private\\nvidia-embedding.txt",
    "/srv/astrbot/nvidia-embedding.json",
)


def _assert_no_sensitive_values(*texts: object) -> None:
    for text in texts:
        for value in _SENSITIVE_VALUES:
            assert value not in str(text)


class _Response:
    def __init__(self, status: int, data: object | BaseException) -> None:
        self.status = status
        self.data = data

    async def __aenter__(self) -> _Response:
        if isinstance(self.data, asyncio.CancelledError):
            raise self.data
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def json(self) -> object:
        if isinstance(self.data, BaseException):
            raise self.data
        return self.data

    async def text(self) -> str:
        return _SENSITIVE_ERROR


class _Client:
    def __init__(self, response: _Response, *, closed: bool = False) -> None:
        self.response = response
        self.closed = closed
        self.closed_by_terminate = False

    def post(self, *_args: object, **_kwargs: object) -> _Response:
        return self.response

    async def close(self) -> None:
        self.closed = True
        self.closed_by_terminate = True


def _provider(client: _Client) -> NvidiaEmbeddingProvider:
    provider = NvidiaEmbeddingProvider.__new__(NvidiaEmbeddingProvider)
    provider.client = client
    provider.base_url = "https://embedding.example.test"
    provider.proxy = ""
    provider.model = "nvidia/test-embedding"
    provider.input_type = "passage"
    provider.provider_config = {}
    return provider


def test_nvidia_embedding_does_not_log_proxy_credentials(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="astrbot"):
        NvidiaEmbeddingProvider(
            {
                "type": "nvidia_embedding",
                "proxy": _SENSITIVE_ERROR,
            },
            {},
        )

    _assert_no_sensitive_values(caplog.text)


@pytest.mark.asyncio
async def test_nvidia_embedding_hides_provider_error_from_logs_and_exception(
    caplog,
) -> None:
    provider = _provider(_Client(_Response(500, {"detail": _SENSITIVE_ERROR})))

    with caplog.at_level(logging.ERROR, logger="astrbot"):
        with pytest.raises(
            RuntimeError, match="NVIDIA embedding request failed"
        ) as caught:
            await provider.get_embeddings(["text"])

    assert caught.value.__cause__ is None
    _assert_no_sensitive_values(caught.value, caplog.text)


@pytest.mark.asyncio
async def test_nvidia_embedding_rejects_malformed_response_shape() -> None:
    provider = _provider(
        _Client(
            _Response(
                200,
                {"data": [{"index": 0, "embedding": [_SENSITIVE_ERROR]}]},
            )
        )
    )

    with pytest.raises(RuntimeError, match="NVIDIA embedding request failed") as caught:
        await provider.get_embeddings(["text"])

    assert caught.value.__cause__ is None
    _assert_no_sensitive_values(caught.value)


@pytest.mark.asyncio
async def test_nvidia_embedding_propagates_cancellation() -> None:
    provider = _provider(_Client(_Response(200, asyncio.CancelledError())))

    with pytest.raises(asyncio.CancelledError):
        await provider.get_embeddings(["text"])


@pytest.mark.asyncio
async def test_nvidia_embedding_terminate_drops_an_already_closed_client() -> None:
    client = _Client(_Response(200, {"data": []}), closed=True)
    provider = _provider(client)

    await provider.terminate()

    assert provider.client is None
    assert client.closed_by_terminate is False
