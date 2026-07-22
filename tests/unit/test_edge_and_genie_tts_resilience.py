"""Offline resilience contracts for the Edge and Genie TTS adapters."""

import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrbot.core.provider.sources import edge_tts_source, genie_tts
from astrbot.core.provider.sources.edge_tts_source import ProviderEdgeTTS
from astrbot.core.provider.sources.genie_tts import GenieTTSProvider

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


def _edge_provider() -> ProviderEdgeTTS:
    return ProviderEdgeTTS(
        {
            "type": "edge_tts",
            "edge-tts-voice": "test-voice",
            "timeout": 30,
        },
        {},
    )


def _genie_provider() -> GenieTTSProvider:
    provider = GenieTTSProvider.__new__(GenieTTSProvider)
    provider.character_name = "test-character"
    return provider


class _ImmediateExecutorLoop:
    """Run a submitted callable synchronously and expose its result as a Future."""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def run_in_executor(self, _executor, callback, /, *args):  # noqa: ANN001
        future = self._loop.create_future()
        try:
            callback(*args)
        except BaseException as exc:
            future.set_exception(exc)
        else:
            future.set_result(None)
        return future


class _PendingExecutorLoop:
    """Run setup synchronously but retain a controlled in-flight Future."""

    def __init__(self, loop: asyncio.AbstractEventLoop, started: asyncio.Event) -> None:
        self._loop = loop
        self._started = started
        self.future: asyncio.Future[None] = loop.create_future()

    def run_in_executor(self, _executor, callback, /, *args):  # noqa: ANN001
        callback(*args)
        self._started.set()
        return self.future


@pytest.mark.asyncio
async def test_edge_tts_hides_temp_directory_failure(monkeypatch, caplog) -> None:
    class _Communicate:
        def __init__(self, **_kwargs: object) -> None:
            pass

    def _raise_mkdir(self, *_args: object, **_kwargs: object) -> None:  # noqa: ARG001
        raise OSError(_SENSITIVE_ERROR)

    monkeypatch.setattr(
        edge_tts_source.importlib,
        "import_module",
        lambda name: (
            SimpleNamespace(Communicate=_Communicate)
            if name == "edge_tts"
            else (_ for _ in ()).throw(ImportError(name))
        ),
    )
    monkeypatch.setattr(edge_tts_source.Path, "mkdir", _raise_mkdir)

    with caplog.at_level(logging.DEBUG, logger="astrbot"):
        with pytest.raises(RuntimeError) as caught:
            await _edge_provider().get_audio("hello")

    assert str(caught.value) == "Edge TTS audio generation failed."
    assert caught.value.__cause__ is None
    for sensitive_value in _SENSITIVE_VALUES:
        assert sensitive_value not in str(caught.value)
        assert sensitive_value not in caplog.text


@pytest.mark.asyncio
async def test_edge_tts_returns_nonempty_wav_and_removes_intermediate_mp3(
    monkeypatch,
    tmp_path: Path,
) -> None:
    communicate_calls: list[dict[str, object]] = []

    class _Communicate:
        def __init__(self, **kwargs: object) -> None:
            communicate_calls.append(kwargs)

        async def save(self, path: str) -> None:
            Path(path).write_bytes(b"mp3")

    class _FFmpeg:
        def convert(self, *, input_file: str, output_file: str) -> None:
            assert Path(input_file).read_bytes() == b"mp3"
            Path(output_file).write_bytes(b"wav")

    def _import_module(name: str):
        if name == "edge_tts":
            return SimpleNamespace(Communicate=_Communicate)
        if name == "pyffmpeg":
            return SimpleNamespace(FFmpeg=_FFmpeg)
        raise ImportError(name)

    monkeypatch.delenv("https_proxy", raising=False)
    monkeypatch.setattr(edge_tts_source, "get_astrbot_temp_path", lambda: tmp_path)
    monkeypatch.setattr(edge_tts_source.importlib, "import_module", _import_module)

    output_path = Path(await _edge_provider().get_audio("hello"))

    try:
        assert output_path.read_bytes() == b"wav"
        assert communicate_calls == [
            {"proxy": None, "text": "hello", "voice": "test-voice"}
        ]
        assert not list(tmp_path.glob("edge_tts_temp_*.mp3"))
    finally:
        output_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_genie_tts_hides_temp_directory_failure(monkeypatch, caplog) -> None:
    def _raise_mkdir(self, *_args: object, **_kwargs: object) -> None:  # noqa: ARG001
        raise OSError(_SENSITIVE_ERROR)

    monkeypatch.setattr(genie_tts.Path, "mkdir", _raise_mkdir)

    with caplog.at_level(logging.DEBUG, logger="astrbot"):
        with pytest.raises(RuntimeError) as caught:
            await _genie_provider().get_audio("hello")

    assert str(caught.value) == "Genie TTS audio generation failed."
    assert caught.value.__cause__ is None
    for sensitive_value in _SENSITIVE_VALUES:
        assert sensitive_value not in str(caught.value)
        assert sensitive_value not in caplog.text


@pytest.mark.asyncio
async def test_genie_tts_returns_nonempty_audio(monkeypatch, tmp_path: Path) -> None:
    class _WritingGenie:
        def tts(self, **kwargs: object) -> None:
            Path(str(kwargs["save_path"])).write_bytes(b"wav")

    real_loop = asyncio.get_running_loop()
    monkeypatch.setattr(genie_tts, "genie", _WritingGenie())
    monkeypatch.setattr(genie_tts, "get_astrbot_temp_path", lambda: tmp_path)
    monkeypatch.setattr(
        genie_tts.asyncio,
        "get_running_loop",
        lambda: _ImmediateExecutorLoop(real_loop),
    )

    output_path = Path(await _genie_provider().get_audio("hello"))

    try:
        assert output_path.read_bytes() == b"wav"
    finally:
        output_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_edge_tts_hides_provider_failure_and_removes_partial_audio(
    monkeypatch,
    tmp_path: Path,
    caplog,
) -> None:
    class _FailingCommunicate:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def save(self, path: str) -> None:
            Path(path).write_bytes(b"partial mp3")
            raise RuntimeError(_SENSITIVE_ERROR)

    monkeypatch.setattr(
        edge_tts_source,
        "get_astrbot_temp_path",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        edge_tts_source.importlib,
        "import_module",
        lambda name: (
            SimpleNamespace(Communicate=_FailingCommunicate)
            if name == "edge_tts"
            else (_ for _ in ()).throw(ImportError(name))
        ),
    )

    with caplog.at_level(logging.DEBUG, logger="astrbot"):
        with pytest.raises(RuntimeError) as caught:
            await _edge_provider().get_audio("hello")

    assert str(caught.value) == "Edge TTS audio generation failed."
    assert caught.value.__cause__ is None
    assert not list(tmp_path.glob("edge_tts*"))
    for sensitive_value in _SENSITIVE_VALUES:
        assert sensitive_value not in str(caught.value)
        assert sensitive_value not in caplog.text


@pytest.mark.asyncio
async def test_edge_tts_hides_ffmpeg_output_and_rejects_failed_conversion(
    monkeypatch,
    tmp_path: Path,
    caplog,
) -> None:
    class _Communicate:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def save(self, path: str) -> None:
            Path(path).write_bytes(b"mp3")

    class _FailingFFmpeg:
        def convert(self, **_kwargs: object) -> None:
            raise RuntimeError(_SENSITIVE_ERROR)

    class _FailedProcess:
        returncode = 1

        async def communicate(self) -> tuple[bytes, bytes]:
            return _SENSITIVE_ERROR.encode(), _SENSITIVE_ERROR.encode()

    process = _FailedProcess()

    def _import_module(name: str):
        if name == "edge_tts":
            return SimpleNamespace(Communicate=_Communicate)
        if name == "pyffmpeg":
            return SimpleNamespace(FFmpeg=_FailingFFmpeg)
        raise ImportError(name)

    async def _create_subprocess(*_args: object, **_kwargs: object) -> _FailedProcess:
        return process

    monkeypatch.setattr(edge_tts_source, "get_astrbot_temp_path", lambda: tmp_path)
    monkeypatch.setattr(edge_tts_source.importlib, "import_module", _import_module)
    monkeypatch.setattr(
        edge_tts_source.asyncio,
        "create_subprocess_exec",
        _create_subprocess,
    )

    with caplog.at_level(logging.DEBUG, logger="astrbot"):
        with pytest.raises(RuntimeError) as caught:
            await _edge_provider().get_audio("hello")

    assert str(caught.value) == "Edge TTS audio generation failed."
    assert caught.value.__cause__ is None
    assert not list(tmp_path.glob("edge_tts*"))
    for sensitive_value in _SENSITIVE_VALUES:
        assert sensitive_value not in str(caught.value)
        assert sensitive_value not in caplog.text


@pytest.mark.asyncio
async def test_edge_tts_cancellation_removes_partial_audio(
    monkeypatch,
    tmp_path: Path,
) -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    class _BlockingCommunicate:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def save(self, path: str) -> None:
            Path(path).write_bytes(b"partial mp3")
            started.set()
            await release.wait()

    monkeypatch.setattr(edge_tts_source, "get_astrbot_temp_path", lambda: tmp_path)
    monkeypatch.setattr(
        edge_tts_source.importlib,
        "import_module",
        lambda name: (
            SimpleNamespace(Communicate=_BlockingCommunicate)
            if name == "edge_tts"
            else (_ for _ in ()).throw(ImportError(name))
        ),
    )

    task = asyncio.create_task(_edge_provider().get_audio("hello"))
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    release.set()
    assert not list(tmp_path.glob("edge_tts*"))


@pytest.mark.asyncio
async def test_edge_tts_cancellation_terminates_ffmpeg_and_cleans_up(
    monkeypatch,
    tmp_path: Path,
) -> None:
    class _Communicate:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def save(self, path: str) -> None:
            Path(path).write_bytes(b"mp3")

    class _UnavailableFFmpeg:
        def convert(self, **_kwargs: object) -> None:
            raise RuntimeError("pyffmpeg unavailable")

    class _BlockingProcess:
        def __init__(self) -> None:
            self.returncode: int | None = None
            self.started = asyncio.Event()
            self.stopped = asyncio.Event()
            self.terminated = False

        async def communicate(self) -> tuple[bytes, bytes]:
            self.started.set()
            await self.stopped.wait()
            return b"", b""

        def terminate(self) -> None:
            self.terminated = True
            self.returncode = -15
            self.stopped.set()

        async def wait(self) -> int:
            await self.stopped.wait()
            assert self.returncode is not None
            return self.returncode

    process = _BlockingProcess()

    def _import_module(name: str):
        if name == "edge_tts":
            return SimpleNamespace(Communicate=_Communicate)
        if name == "pyffmpeg":
            return SimpleNamespace(FFmpeg=_UnavailableFFmpeg)
        raise ImportError(name)

    async def _create_subprocess(*_args: object, **_kwargs: object) -> _BlockingProcess:
        return process

    monkeypatch.setattr(edge_tts_source, "get_astrbot_temp_path", lambda: tmp_path)
    monkeypatch.setattr(edge_tts_source.importlib, "import_module", _import_module)
    monkeypatch.setattr(
        edge_tts_source.asyncio,
        "create_subprocess_exec",
        _create_subprocess,
    )

    task = asyncio.create_task(_edge_provider().get_audio("hello"))
    await process.started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert process.terminated
    assert not list(tmp_path.glob("edge_tts*"))


@pytest.mark.asyncio
async def test_genie_tts_hides_sdk_failure_and_removes_partial_audio(
    monkeypatch,
    tmp_path: Path,
    caplog,
) -> None:
    class _FailingGenie:
        def tts(self, **kwargs: object) -> None:
            Path(str(kwargs["save_path"])).write_bytes(b"partial wav")
            raise RuntimeError(_SENSITIVE_ERROR)

    real_loop = asyncio.get_running_loop()
    monkeypatch.setattr(genie_tts, "genie", _FailingGenie())
    monkeypatch.setattr(genie_tts, "get_astrbot_temp_path", lambda: tmp_path)
    monkeypatch.setattr(
        genie_tts.asyncio,
        "get_running_loop",
        lambda: _ImmediateExecutorLoop(real_loop),
    )

    with caplog.at_level(logging.DEBUG, logger="astrbot"):
        with pytest.raises(RuntimeError) as caught:
            await _genie_provider().get_audio("hello")

    assert str(caught.value) == "Genie TTS audio generation failed."
    assert caught.value.__cause__ is None
    assert not list(tmp_path.glob("genie_tts_*.wav"))
    for sensitive_value in _SENSITIVE_VALUES:
        assert sensitive_value not in str(caught.value)
        assert sensitive_value not in caplog.text


@pytest.mark.asyncio
async def test_genie_tts_stream_hides_failure_and_removes_partial_audio(
    monkeypatch,
    tmp_path: Path,
    caplog,
) -> None:
    class _FailingGenie:
        def tts(self, **kwargs: object) -> None:
            Path(str(kwargs["save_path"])).write_bytes(b"partial wav")
            raise RuntimeError(_SENSITIVE_ERROR)

    real_loop = asyncio.get_running_loop()
    monkeypatch.setattr(genie_tts, "genie", _FailingGenie())
    monkeypatch.setattr(genie_tts, "get_astrbot_temp_path", lambda: tmp_path)
    monkeypatch.setattr(
        genie_tts.asyncio,
        "get_running_loop",
        lambda: _ImmediateExecutorLoop(real_loop),
    )
    text_queue: asyncio.Queue[str | None] = asyncio.Queue()
    audio_queue: asyncio.Queue[bytes | tuple[str, bytes] | None] = asyncio.Queue()
    await text_queue.put("hello")
    await text_queue.put(None)

    with caplog.at_level(logging.DEBUG, logger="astrbot"):
        await _genie_provider().get_audio_stream(text_queue, audio_queue)

    assert await audio_queue.get() is None
    assert not list(tmp_path.glob("genie_tts_*.wav"))
    for sensitive_value in _SENSITIVE_VALUES:
        assert sensitive_value not in caplog.text


@pytest.mark.asyncio
async def test_genie_tts_cancellation_cleans_up_after_worker_finishes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    started = asyncio.Event()
    cleaned = asyncio.Event()

    class _WritingGenie:
        def tts(self, **kwargs: object) -> None:
            Path(str(kwargs["save_path"])).write_bytes(b"partial wav")

    real_loop = asyncio.get_running_loop()
    pending_loop = _PendingExecutorLoop(real_loop, started)
    remove_audio = GenieTTSProvider._remove_audio

    def _remove_audio(path: Path) -> None:
        remove_audio(path)
        cleaned.set()

    monkeypatch.setattr(genie_tts, "genie", _WritingGenie())
    monkeypatch.setattr(genie_tts, "get_astrbot_temp_path", lambda: tmp_path)
    monkeypatch.setattr(genie_tts.asyncio, "get_running_loop", lambda: pending_loop)
    monkeypatch.setattr(GenieTTSProvider, "_remove_audio", staticmethod(_remove_audio))

    task = asyncio.create_task(_genie_provider().get_audio("hello"))
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    if not pending_loop.future.done():
        pending_loop.future.set_result(None)
    await cleaned.wait()
    assert not list(tmp_path.glob("genie_tts_*.wav"))


def test_genie_tts_hides_initialization_failure(monkeypatch, caplog) -> None:
    class _FailingGenie:
        def load_character(self, **_kwargs: object) -> None:
            raise RuntimeError(_SENSITIVE_ERROR)

        def set_reference_audio(self, **_kwargs: object) -> None:
            raise AssertionError("reference audio setup should not run")

    monkeypatch.setattr(genie_tts, "genie", _FailingGenie())

    with caplog.at_level(logging.DEBUG, logger="astrbot"):
        with pytest.raises(RuntimeError) as caught:
            GenieTTSProvider(
                {
                    "type": "genie_tts",
                    "genie_character_name": "test-character",
                },
                {},
            )

    assert str(caught.value) == "Genie TTS initialization failed."
    assert caught.value.__cause__ is None
    for sensitive_value in _SENSITIVE_VALUES:
        assert sensitive_value not in str(caught.value)
        assert sensitive_value not in caplog.text
