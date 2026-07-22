"""Offline resilience contracts for the OpenAI TTS adapter."""

import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrbot.core.provider.sources import openai_tts_api_source
from astrbot.core.provider.sources.openai_tts_api_source import ProviderOpenAITTSAPI

_SENSITIVE_ERROR = (
    "api_key=api-key-top-secret "
    "Bearer bearer-secret-token "
    "password=dashboard-password "
    "https://internal.example/private/config "
    "C:\\private\\config\\secret.txt "
    "/srv/astrbot/private/config.json"
)
_SENSITIVE_VALUES = (
    "api-key-top-secret",
    "bearer-secret-token",
    "dashboard-password",
    "internal.example",
    "C:\\private\\config\\secret.txt",
    "/srv/astrbot/private/config.json",
)


class _FakeStreamingResponse:
    def __init__(
        self,
        chunks: list[bytes],
        failure: BaseException | None = None,
    ) -> None:
        self.chunks = chunks
        self.failure = failure
        self.closed = False

    async def __aenter__(self) -> _FakeStreamingResponse:
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:  # noqa: ANN001
        self.closed = True

    async def iter_bytes(self, chunk_size: int):  # noqa: ARG002
        for chunk in self.chunks:
            yield chunk
        if self.failure is not None:
            raise self.failure


def _provider_with_response(response: _FakeStreamingResponse) -> ProviderOpenAITTSAPI:
    provider = ProviderOpenAITTSAPI.__new__(ProviderOpenAITTSAPI)
    provider.model_name = "test-tts-model"
    provider.voice = "test-voice"
    provider.client = SimpleNamespace(
        audio=SimpleNamespace(
            speech=SimpleNamespace(
                with_streaming_response=SimpleNamespace(
                    create=lambda **_kwargs: response,
                ),
            ),
        ),
    )
    return provider


@pytest.mark.asyncio
async def test_openai_tts_cancellation_removes_partially_written_audio(
    monkeypatch,
    tmp_path: Path,
) -> None:
    response = _FakeStreamingResponse([b"partial"], asyncio.CancelledError())
    provider = _provider_with_response(response)
    monkeypatch.setattr(
        openai_tts_api_source, "get_astrbot_temp_path", lambda: tmp_path
    )

    with pytest.raises(asyncio.CancelledError):
        await provider.get_audio("hello")

    assert response.closed
    assert not list(tmp_path.glob("openai_tts_api_*.wav"))


@pytest.mark.asyncio
async def test_openai_tts_sdk_failure_is_generic_and_redacted(
    monkeypatch,
    tmp_path: Path,
    caplog,
) -> None:
    response = _FakeStreamingResponse([b"partial"], RuntimeError(_SENSITIVE_ERROR))
    provider = _provider_with_response(response)
    monkeypatch.setattr(
        openai_tts_api_source, "get_astrbot_temp_path", lambda: tmp_path
    )

    with caplog.at_level(logging.ERROR, logger="astrbot"):
        with pytest.raises(RuntimeError) as error:
            await provider.get_audio("hello")

    assert str(error.value) == "OpenAI TTS audio generation failed."
    assert error.value.__cause__ is None
    assert response.closed
    assert not list(tmp_path.glob("openai_tts_api_*.wav"))
    for sensitive_value in _SENSITIVE_VALUES:
        assert sensitive_value not in str(error.value)
        assert sensitive_value not in caplog.text


@pytest.mark.asyncio
async def test_openai_tts_rejects_empty_stream_and_removes_empty_audio(
    monkeypatch,
    tmp_path: Path,
) -> None:
    response = _FakeStreamingResponse([])
    provider = _provider_with_response(response)
    monkeypatch.setattr(
        openai_tts_api_source, "get_astrbot_temp_path", lambda: tmp_path
    )

    with pytest.raises(RuntimeError, match="OpenAI TTS audio generation failed"):
        await provider.get_audio("hello")

    assert response.closed
    assert not list(tmp_path.glob("openai_tts_api_*.wav"))
