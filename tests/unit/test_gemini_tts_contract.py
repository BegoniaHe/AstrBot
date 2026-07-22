"""Offline error, cancellation, and lifecycle contracts for Gemini TTS."""

import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrbot.core.provider.sources import gemini_tts_source
from astrbot.core.provider.sources.gemini_tts_source import ProviderGeminiTTSAPI

pytestmark = pytest.mark.provider

_SENSITIVE_ERROR = (
    "api_key=gemini-tts-api-key "
    "Bearer gemini-tts-bearer "
    "password=gemini-tts-password "
    "https://internal.example/gemini-tts "
    "C:\\private\\gemini-tts.txt "
    "/srv/astrbot/gemini-tts.json"
)
_SENSITIVE_VALUES = (
    "gemini-tts-api-key",
    "gemini-tts-bearer",
    "gemini-tts-password",
    "https://internal.example/gemini-tts",
    "C:\\private\\gemini-tts.txt",
    "/srv/astrbot/gemini-tts.json",
)


def _assert_no_sensitive_values(*texts: object) -> None:
    for text in texts:
        for value in _SENSITIVE_VALUES:
            assert value not in str(text)


class _Models:
    def __init__(self, response: object | BaseException) -> None:
        self.response = response

    async def generate_content(self, **_kwargs: object) -> object:
        if isinstance(self.response, BaseException):
            raise self.response
        return self.response


class _Client:
    def __init__(self, response: object | BaseException) -> None:
        self.models = _Models(response)
        self.closed = False
        self.close_error: BaseException | None = None

    async def aclose(self) -> None:
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


def _provider(client: _Client) -> ProviderGeminiTTSAPI:
    provider = ProviderGeminiTTSAPI.__new__(ProviderGeminiTTSAPI)
    provider.client = client
    provider.model = "gemini-tts-test"
    provider.prefix = None
    provider.voice_name = "test-voice"
    return provider


def _response(audio: object) -> SimpleNamespace:
    return SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[SimpleNamespace(inline_data=SimpleNamespace(data=audio))]
                )
            )
        ]
    )


def test_gemini_tts_constructor_hides_proxy_and_sets_model(
    monkeypatch: pytest.MonkeyPatch, caplog
) -> None:
    client = _Client(_response(b"audio"))
    monkeypatch.setattr(
        gemini_tts_source.genai,
        "Client",
        lambda **_kwargs: SimpleNamespace(aio=client),
    )

    with caplog.at_level(logging.INFO, logger="astrbot"):
        provider = ProviderGeminiTTSAPI(
            {
                "type": "gemini_tts",
                "gemini_tts_api_key": "test-key",
                "proxy": _SENSITIVE_ERROR,
                "gemini_tts_model": "gemini-tts-test",
            },
            {},
        )

    assert provider.get_model() == "gemini-tts-test"
    _assert_no_sensitive_values(caplog.text)


@pytest.mark.asyncio
async def test_gemini_tts_hides_sdk_error_from_logs_and_exception(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog
) -> None:
    monkeypatch.setattr(
        gemini_tts_source, "get_astrbot_temp_path", lambda: str(tmp_path)
    )
    provider = _provider(_Client(RuntimeError(_SENSITIVE_ERROR)))

    with caplog.at_level(logging.ERROR, logger="astrbot"):
        with pytest.raises(
            RuntimeError, match="Gemini TTS audio generation failed"
        ) as caught:
            await provider.get_audio("text")

    assert caught.value.__cause__ is None
    _assert_no_sensitive_values(caught.value, caplog.text)
    assert list(tmp_path.glob("*.wav")) == []


@pytest.mark.asyncio
async def test_gemini_tts_rejects_malformed_audio_and_cleans_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        gemini_tts_source, "get_astrbot_temp_path", lambda: str(tmp_path)
    )
    provider = _provider(_Client(_response(_SENSITIVE_ERROR)))

    with pytest.raises(
        RuntimeError, match="Gemini TTS audio generation failed"
    ) as caught:
        await provider.get_audio("text")

    assert caught.value.__cause__ is None
    _assert_no_sensitive_values(caught.value)
    assert list(tmp_path.glob("*.wav")) == []


@pytest.mark.asyncio
async def test_gemini_tts_cancellation_cleans_partial_audio(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        gemini_tts_source, "get_astrbot_temp_path", lambda: str(tmp_path)
    )
    provider = _provider(_Client(_response(b"audio")))

    class _Writer:
        def __init__(self, path: Path) -> None:
            self.path = path

        def __enter__(self) -> _Writer:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def setnchannels(self, _value: int) -> None:
            return None

        def setsampwidth(self, _value: int) -> None:
            return None

        def setframerate(self, _value: int) -> None:
            return None

        def writeframes(self, _value: bytes) -> None:
            self.path.write_bytes(b"partial")
            raise asyncio.CancelledError()

    monkeypatch.setattr(
        gemini_tts_source.wave,
        "open",
        lambda path, *_args: _Writer(Path(path)),
    )

    with pytest.raises(asyncio.CancelledError):
        await provider.get_audio("text")

    assert list(tmp_path.glob("*.wav")) == []


@pytest.mark.asyncio
async def test_gemini_tts_terminate_drops_client_and_hides_close_error(caplog) -> None:
    client = _Client(_response(b"audio"))
    client.close_error = RuntimeError(_SENSITIVE_ERROR)
    provider = _provider(client)

    with caplog.at_level(logging.WARNING, logger="astrbot"):
        await provider.terminate()

    assert client.closed is True
    assert provider.client is None
    _assert_no_sensitive_values(caplog.text)


@pytest.mark.asyncio
async def test_gemini_tts_terminate_propagates_cancellation_after_dropping_client() -> (
    None
):
    client = _Client(_response(b"audio"))
    client.close_error = asyncio.CancelledError()
    provider = _provider(client)

    with pytest.raises(asyncio.CancelledError):
        await provider.terminate()

    assert client.closed is True
    assert provider.client is None
