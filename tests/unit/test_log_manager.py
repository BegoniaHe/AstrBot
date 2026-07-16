import io

from astrbot.core.log import _SafeConsoleStream


class _GbKTextStream:
    def __init__(self) -> None:
        self.buffer = io.BytesIO()
        self.encoding = "gbk"

    def write(self, message: str) -> None:
        self.buffer.write(message.encode(self.encoding))

    def flush(self) -> None:
        return

    def isatty(self) -> bool:
        return False


class _BrokenPipeStream:
    def __init__(self) -> None:
        self.write_calls = 0
        self.flush_calls = 0

    def write(self, message: str) -> None:
        del message
        self.write_calls += 1
        raise BrokenPipeError

    def flush(self) -> None:
        self.flush_calls += 1
        raise BrokenPipeError


def test_safe_console_stream_falls_back_when_stream_encoding_rejects_unicode():
    stream = _GbKTextStream()
    sink = _SafeConsoleStream(stream)

    sink.write("AstrBot ✨ ready\n")

    assert stream.buffer.getvalue().decode("gbk") == "AstrBot \\u2728 ready\n"


def test_safe_console_stream_disables_broken_pipe_sink():
    write_stream = _BrokenPipeStream()
    write_sink = _SafeConsoleStream(write_stream)

    write_sink.write("first message")
    write_sink.write("second message")

    assert write_stream.write_calls == 1

    flush_stream = _BrokenPipeStream()
    flush_sink = _SafeConsoleStream(flush_stream)

    flush_sink.flush()
    flush_sink.flush()
    flush_sink.write("message after broken pipe")

    assert flush_stream.flush_calls == 1
    assert flush_stream.write_calls == 0
