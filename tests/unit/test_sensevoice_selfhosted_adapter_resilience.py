"""Offline resilience contracts for the self-hosted SenseVoice STT adapter."""

import asyncio
import contextlib
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrbot.core.provider.sources import sensevoice_selfhosted_source
from astrbot.core.provider.sources.sensevoice_selfhosted_source import (
    ProviderSenseVoiceSTTSelfHost,
)

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


class _ImmediateLoop:
    def __init__(self, event_loop: asyncio.AbstractEventLoop) -> None:
        self.event_loop = event_loop

    def run_in_executor(self, _executor, callback, *args):  # noqa: ANN001
        future = self.event_loop.create_future()
        try:
            future.set_result(callback(*args))
        except BaseException as exc:
            future.set_exception(exc)
        return future


class _ControlledLoop:
    def __init__(self, event_loop: asyncio.AbstractEventLoop) -> None:
        self.event_loop = event_loop
        self.submitted = event_loop.create_future()
        self.future: asyncio.Future | None = None

    def run_in_executor(self, _executor, _callback, *_args):  # noqa: ANN001
        self.future = self.event_loop.create_future()
        self.submitted.set_result(None)
        return self.future


class _FakeResolvedAudio:
    def __init__(self) -> None:
        self.path = Path("audio.wav")


class _FakeMediaResolver:
    def __init__(self, audio: _FakeResolvedAudio) -> None:
        self.audio = audio
        self.closed = False

    def as_path(self, *, target_format: str) -> _FakeMediaResolver:
        assert target_format == "wav"
        return self

    async def __aenter__(self) -> _FakeResolvedAudio:
        return self.audio

    async def __aexit__(self, exc_type, exc, traceback) -> None:  # noqa: ANN001
        self.closed = True


class _FakeModel:
    def __init__(
        self,
        result: object | None = None,
        failure: BaseException | None = None,
    ) -> None:
        self.result = result
        self.failure = failure
        self.calls: list[tuple[str, str, bool]] = []

    def __call__(self, audio_path: str, *, language: str, use_itn: bool):
        self.calls.append((audio_path, language, use_itn))
        if self.failure is not None:
            raise self.failure
        return self.result


class _FakePostprocess:
    def __init__(
        self,
        result: object = "transcribed text",
        failure: BaseException | None = None,
    ) -> None:
        self.result = result
        self.failure = failure
        self.calls: list[str] = []

    def rich_transcription_postprocess(self, text: str):
        self.calls.append(text)
        if self.failure is not None:
            raise self.failure
        return self.result


def _provider() -> ProviderSenseVoiceSTTSelfHost:
    provider = ProviderSenseVoiceSTTSelfHost.__new__(ProviderSenseVoiceSTTSelfHost)
    provider.model_name = "sensevoice-test-model"
    provider.model = None
    provider.is_emotion = False
    provider._executor_futures = set()
    return provider


def _assert_redacted(text: str) -> None:
    for sensitive_value in _SENSITIVE_VALUES:
        assert sensitive_value not in text


@pytest.mark.asyncio
async def test_sensevoice_load_failure_is_generic_and_redacted(
    monkeypatch, caplog
) -> None:
    event_loop = asyncio.get_running_loop()
    loop = _ImmediateLoop(event_loop)
    provider = _provider()

    def sensevoice_small(*_args, **_kwargs):
        raise RuntimeError(_SENSITIVE_ERROR)

    monkeypatch.setattr(
        sensevoice_selfhosted_source.importlib,
        "import_module",
        lambda name: (
            SimpleNamespace(SenseVoiceSmall=sensevoice_small)
            if name == "funasr_onnx"
            else None
        ),
    )
    monkeypatch.setattr(
        sensevoice_selfhosted_source.asyncio,
        "get_running_loop",
        lambda: loop,
    )

    with caplog.at_level(logging.ERROR, logger="astrbot"):
        with pytest.raises(RuntimeError) as error:
            await provider.initialize()

    assert str(error.value) == "SenseVoice model initialization failed."
    assert provider.model is None
    _assert_redacted(str(error.value))
    _assert_redacted(caplog.text)


@pytest.mark.asyncio
async def test_sensevoice_inference_failure_is_generic_and_releases_media(
    monkeypatch,
    caplog,
) -> None:
    event_loop = asyncio.get_running_loop()
    loop = _ImmediateLoop(event_loop)
    resolver = _FakeMediaResolver(_FakeResolvedAudio())
    provider = _provider()
    provider.model = _FakeModel(failure=RuntimeError(_SENSITIVE_ERROR))
    postprocess = _FakePostprocess()
    monkeypatch.setattr(
        sensevoice_selfhosted_source,
        "MediaResolver",
        lambda *_args, **_kwargs: resolver,
    )
    monkeypatch.setattr(
        sensevoice_selfhosted_source.importlib,
        "import_module",
        lambda name: (
            SimpleNamespace(
                rich_transcription_postprocess=postprocess.rich_transcription_postprocess
            )
            if name == "funasr_onnx.utils.postprocess_utils"
            else None
        ),
    )
    monkeypatch.setattr(
        sensevoice_selfhosted_source.asyncio,
        "get_running_loop",
        lambda: loop,
    )

    with caplog.at_level(logging.ERROR, logger="astrbot"):
        with pytest.raises(RuntimeError) as error:
            await provider.get_text("audio.wav")

    assert str(error.value) == "SenseVoice transcription failed."
    assert resolver.closed
    _assert_redacted(str(error.value))
    _assert_redacted(caplog.text)


@pytest.mark.asyncio
async def test_sensevoice_rejects_malformed_recognition_result(
    monkeypatch, caplog
) -> None:
    event_loop = asyncio.get_running_loop()
    loop = _ImmediateLoop(event_loop)
    resolver = _FakeMediaResolver(_FakeResolvedAudio())
    provider = _provider()
    provider.model = _FakeModel(result=[{"error": _SENSITIVE_ERROR}])
    postprocess = _FakePostprocess()
    monkeypatch.setattr(
        sensevoice_selfhosted_source,
        "MediaResolver",
        lambda *_args, **_kwargs: resolver,
    )
    monkeypatch.setattr(
        sensevoice_selfhosted_source.importlib,
        "import_module",
        lambda name: (
            SimpleNamespace(
                rich_transcription_postprocess=postprocess.rich_transcription_postprocess
            )
            if name == "funasr_onnx.utils.postprocess_utils"
            else None
        ),
    )
    monkeypatch.setattr(
        sensevoice_selfhosted_source.asyncio,
        "get_running_loop",
        lambda: loop,
    )

    with caplog.at_level(logging.WARNING, logger="astrbot"):
        with pytest.raises(RuntimeError) as error:
            await provider.get_text("audio.wav")

    assert str(error.value) == "SenseVoice transcription failed."
    assert resolver.closed
    assert postprocess.calls == []
    _assert_redacted(str(error.value))
    _assert_redacted(caplog.text)


@pytest.mark.asyncio
async def test_sensevoice_terminate_cancels_executor_work_and_releases_model(
    monkeypatch,
) -> None:
    event_loop = asyncio.get_running_loop()
    loop = _ControlledLoop(event_loop)
    resolver = _FakeMediaResolver(_FakeResolvedAudio())
    provider = _provider()
    provider.model = _FakeModel(result=["unused"])
    postprocess = _FakePostprocess()
    monkeypatch.setattr(
        sensevoice_selfhosted_source,
        "MediaResolver",
        lambda *_args, **_kwargs: resolver,
    )
    monkeypatch.setattr(
        sensevoice_selfhosted_source.importlib,
        "import_module",
        lambda name: (
            SimpleNamespace(
                rich_transcription_postprocess=postprocess.rich_transcription_postprocess
            )
            if name == "funasr_onnx.utils.postprocess_utils"
            else None
        ),
    )
    monkeypatch.setattr(
        sensevoice_selfhosted_source.asyncio,
        "get_running_loop",
        lambda: loop,
    )

    task = event_loop.create_task(provider.get_text("audio.wav"))
    try:
        await loop.submitted
        await provider.terminate()

        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    assert loop.future is not None and loop.future.cancelled()
    assert not provider._executor_futures
    assert provider.model is None
    assert resolver.closed
