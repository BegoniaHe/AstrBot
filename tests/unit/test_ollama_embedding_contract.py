"""Offline error and response contracts for the Ollama embedding adapter."""

import asyncio
import logging

import pytest

from astrbot.core.provider.sources.ollama_embedding_source import (
    OllamaEmbeddingProvider,
)

pytestmark = pytest.mark.provider

_SENSITIVE_ERROR = (
    "api_key=ollama-api-key "
    "Bearer ollama-bearer-token "
    "password=ollama-password "
    "https://internal.example/ollama "
    "C:\\private\\ollama.txt "
    "/srv/astrbot/ollama.json"
)
_SENSITIVE_VALUES = (
    "ollama-api-key",
    "ollama-bearer-token",
    "ollama-password",
    "https://internal.example/ollama",
    "C:\\private\\ollama.txt",
    "/srv/astrbot/ollama.json",
)


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


def _provider(client: _Client) -> OllamaEmbeddingProvider:
    provider = OllamaEmbeddingProvider.__new__(OllamaEmbeddingProvider)
    provider.client = client
    provider.base_url = "https://embedding.example.test"
    provider.proxy = ""
    provider.model = "test-embedding"
    provider.provider_config = {}
    return provider


def _assert_no_sensitive_values(*texts: object) -> None:
    for text in texts:
        for value in _SENSITIVE_VALUES:
            assert value not in str(text)


def test_ollama_embedding_does_not_log_proxy_credentials(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="astrbot"):
        OllamaEmbeddingProvider(
            {
                "type": "ollama_embedding",
                "proxy": _SENSITIVE_ERROR,
            },
            {},
        )

    _assert_no_sensitive_values(caplog.text)


@pytest.mark.asyncio
async def test_ollama_embedding_hides_provider_error_from_logs_and_exception(
    caplog,
) -> None:
    provider = _provider(_Client(_Response(500, {"detail": _SENSITIVE_ERROR})))

    with caplog.at_level(logging.ERROR, logger="astrbot"):
        with pytest.raises(
            RuntimeError, match="Ollama embedding request failed"
        ) as caught:
            await provider.get_embeddings(["text"])

    assert caught.value.__cause__ is None
    _assert_no_sensitive_values(caught.value, caplog.text)


@pytest.mark.asyncio
async def test_ollama_embedding_rejects_malformed_response_shape() -> None:
    provider = _provider(_Client(_Response(200, {"embeddings": _SENSITIVE_ERROR})))

    with pytest.raises(RuntimeError, match="Ollama embedding request failed") as caught:
        await provider.get_embeddings(["text"])

    assert caught.value.__cause__ is None
    _assert_no_sensitive_values(caught.value)


@pytest.mark.asyncio
async def test_ollama_embedding_propagates_cancellation() -> None:
    provider = _provider(_Client(_Response(200, asyncio.CancelledError())))

    with pytest.raises(asyncio.CancelledError):
        await provider.get_embeddings(["text"])


@pytest.mark.asyncio
async def test_ollama_embedding_terminate_drops_closed_client() -> None:
    client = _Client(_Response(200, {"embeddings": [[1.0]]}), closed=True)
    provider = _provider(client)

    await provider.terminate()

    assert provider.client is None
    assert client.closed_by_terminate is False
