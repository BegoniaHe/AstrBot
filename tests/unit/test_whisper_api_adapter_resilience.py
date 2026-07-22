"""Offline resilience contracts for the OpenAI Whisper STT adapter."""

import asyncio
import logging
from types import SimpleNamespace

import httpx
import pytest

from astrbot.core.provider.sources import whisper_api_source
from astrbot.core.provider.sources.whisper_api_source import ProviderOpenAIWhisperAPI

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


class _FakeAudioFile:
    def __init__(self) -> None:
        self.closed = False

    def __enter__(self) -> _FakeAudioFile:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:  # noqa: ANN001
        self.closed = True


class _FakeAudioPath:
    def __init__(self, audio_file: _FakeAudioFile) -> None:
        self.audio_file = audio_file

    def open(self, mode: str) -> _FakeAudioFile:
        assert mode == "rb"
        return self.audio_file


class _FakeMediaResolver:
    def __init__(self, audio_path: _FakeAudioPath) -> None:
        self.audio_path = audio_path
        self.closed = False

    def as_path(self, *, target_format: str) -> _FakeMediaResolver:
        assert target_format == "wav"
        return self

    async def __aenter__(self) -> _FakeAudioPath:
        return self.audio_path

    async def __aexit__(self, exc_type, exc, traceback) -> None:  # noqa: ANN001
        self.closed = True


class _FakeTranscriptions:
    def __init__(
        self,
        result: object | None = None,
        failure: BaseException | None = None,
    ) -> None:
        self.result = result
        self.failure = failure
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.failure is not None:
            raise self.failure
        return self.result


class _FakeClient:
    def __init__(
        self,
        transcriptions: _FakeTranscriptions,
        close_failure: BaseException | None = None,
    ) -> None:
        self.audio = SimpleNamespace(transcriptions=transcriptions)
        self.close_failure = close_failure
        self.close_calls = 0

    async def close(self) -> None:
        self.close_calls += 1
        if self.close_failure is not None:
            raise self.close_failure


def _provider(client: _FakeClient) -> ProviderOpenAIWhisperAPI:
    provider = ProviderOpenAIWhisperAPI.__new__(ProviderOpenAIWhisperAPI)
    provider.model_name = "whisper-test-model"
    provider.client = client
    return provider


def _resolver() -> tuple[_FakeMediaResolver, _FakeAudioFile]:
    audio_file = _FakeAudioFile()
    return _FakeMediaResolver(_FakeAudioPath(audio_file)), audio_file


def _http_failure() -> httpx.HTTPStatusError:
    request = httpx.Request(
        "POST",
        "https://internal.example/private/transcriptions?api_key=api-key-top-secret",
    )
    response = httpx.Response(502, request=request)
    return httpx.HTTPStatusError(_SENSITIVE_ERROR, request=request, response=response)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        RuntimeError(_SENSITIVE_ERROR),
        _http_failure(),
    ],
    ids=["sdk", "http"],
)
async def test_whisper_sdk_or_http_failure_is_generic_redacted_and_closes_media(
    monkeypatch,
    caplog,
    failure: BaseException,
) -> None:
    resolver, audio_file = _resolver()
    transcriptions = _FakeTranscriptions(failure=failure)
    provider = _provider(_FakeClient(transcriptions))
    monkeypatch.setattr(
        whisper_api_source,
        "MediaResolver",
        lambda *_args, **_kwargs: resolver,
    )

    with caplog.at_level(logging.ERROR, logger="astrbot"):
        with pytest.raises(RuntimeError) as error:
            await provider.get_text("audio.wav")

    assert str(error.value) == "OpenAI Whisper transcription failed."
    assert resolver.closed
    assert audio_file.closed
    assert transcriptions.calls[0]["file"] == ("audio.wav", audio_file)
    for sensitive_value in _SENSITIVE_VALUES:
        assert sensitive_value not in str(error.value)
        assert sensitive_value not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "result",
    [
        None,
        SimpleNamespace(text={"error": _SENSITIVE_ERROR}),
    ],
)
async def test_whisper_rejects_malformed_transcription_result(
    monkeypatch,
    result: object | None,
    caplog,
) -> None:
    resolver, audio_file = _resolver()
    provider = _provider(_FakeClient(_FakeTranscriptions(result=result)))
    monkeypatch.setattr(
        whisper_api_source,
        "MediaResolver",
        lambda *_args, **_kwargs: resolver,
    )

    with caplog.at_level(logging.WARNING, logger="astrbot"):
        with pytest.raises(RuntimeError) as error:
            await provider.get_text("audio.wav")

    assert str(error.value) == "OpenAI Whisper transcription failed."
    assert resolver.closed
    assert audio_file.closed
    for sensitive_value in _SENSITIVE_VALUES:
        assert sensitive_value not in str(error.value)
        assert sensitive_value not in caplog.text


@pytest.mark.asyncio
async def test_whisper_cancellation_propagates_and_closes_media(monkeypatch) -> None:
    resolver, audio_file = _resolver()
    provider = _provider(
        _FakeClient(_FakeTranscriptions(failure=asyncio.CancelledError()))
    )
    monkeypatch.setattr(
        whisper_api_source,
        "MediaResolver",
        lambda *_args, **_kwargs: resolver,
    )

    with pytest.raises(asyncio.CancelledError):
        await provider.get_text("audio.wav")

    assert resolver.closed
    assert audio_file.closed


@pytest.mark.asyncio
async def test_whisper_terminate_closes_client() -> None:
    client = _FakeClient(_FakeTranscriptions(result=SimpleNamespace(text="ok")))
    provider = _provider(client)

    await provider.terminate()

    assert client.close_calls == 1
    assert provider.client is None


@pytest.mark.asyncio
async def test_whisper_terminate_hides_close_failure_and_propagates_cancellation(
    caplog,
) -> None:
    failing_client = _FakeClient(
        _FakeTranscriptions(result=SimpleNamespace(text="ok")),
        close_failure=RuntimeError(_SENSITIVE_ERROR),
    )
    provider = _provider(failing_client)

    with caplog.at_level(logging.WARNING, logger="astrbot"):
        await provider.terminate()

    assert failing_client.close_calls == 1
    assert provider.client is failing_client
    for sensitive_value in _SENSITIVE_VALUES:
        assert sensitive_value not in caplog.text

    cancelling_client = _FakeClient(
        _FakeTranscriptions(result=SimpleNamespace(text="ok")),
        close_failure=asyncio.CancelledError(),
    )
    provider.client = cancelling_client

    with pytest.raises(asyncio.CancelledError):
        await provider.terminate()

    assert cancelling_client.close_calls == 1
