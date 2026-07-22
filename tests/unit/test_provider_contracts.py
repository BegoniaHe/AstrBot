"""Offline contracts for non-chat provider base classes and adapters."""

import asyncio
from pathlib import Path

import pytest

from astrbot.core.provider.entities import RerankResult
from astrbot.core.provider.provider import (
    EmbeddingProvider,
    RerankProvider,
    STTProvider,
    TTSProvider,
)
from astrbot.core.provider.sources import openai_embedding_source
from astrbot.core.provider.sources.nvidia_embedding_source import (
    NvidiaEmbeddingProvider,
)
from astrbot.core.provider.sources.vllm_rerank_source import VLLMRerankProvider

pytestmark = pytest.mark.provider


class _RetryingEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        super().__init__({"type": "test"}, {})
        self.calls = 0

    async def get_embedding(self, text: str) -> list[float]:
        return [float(len(text))]

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary provider failure")
        return [[float(len(text))] for text in texts]


class _CancelledEmbeddingProvider(EmbeddingProvider):
    async def get_embedding(self, text: str) -> list[float]:
        return [float(len(text))]

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        raise asyncio.CancelledError


class _ShortEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        super().__init__({"type": "test"}, {})
        self.calls = 0

    async def get_embedding(self, text: str) -> list[float]:
        return [float(len(text))]

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [[1.0]]


class _ProgressFailingEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        super().__init__({"type": "test"}, {})
        self.calls = 0

    async def get_embedding(self, text: str) -> list[float]:
        return [float(len(text))]

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [[float(len(text))] for text in texts]


class _FileTTSProvider(TTSProvider):
    def __init__(self, output_path: Path) -> None:
        super().__init__({"type": "test"}, {})
        self.output_path = output_path

    async def get_audio(self, text: str) -> str:
        self.output_path.write_bytes(text.encode())
        return str(self.output_path)


class _BlockingAudioQueue:
    def __init__(self) -> None:
        self.put_started = asyncio.Event()
        self.release = asyncio.Event()

    async def put(self, _item: object) -> None:
        self.put_started.set()
        await self.release.wait()


class _RecordingSTTProvider(STTProvider):
    def __init__(self) -> None:
        super().__init__({"type": "test"}, {})
        self.audio_urls: list[str] = []

    async def get_text(self, audio_url: str) -> str:
        self.audio_urls.append(audio_url)
        return "transcript"


class _StaticRerankProvider(RerankProvider):
    def __init__(self, results: list[RerankResult]) -> None:
        super().__init__({"type": "test"}, {})
        self.results = results

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int | None = None,
    ) -> list[RerankResult]:
        return self.results


class _FakeResponse:
    async def json(self) -> dict:
        return {"results": [{"index": 1, "relevance_score": 0.9}]}


class _FakeRequest:
    async def __aenter__(self) -> _FakeResponse:
        return _FakeResponse()

    async def __aexit__(self, exc_type, exc, traceback) -> None:  # noqa: ANN001
        return None


class _FakeRerankClient:
    def __init__(self) -> None:
        self.posts: list[tuple[str, dict]] = []
        self.closed = False

    def post(self, url: str, *, json: dict) -> _FakeRequest:
        self.posts.append((url, json))
        return _FakeRequest()

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_embedding_batch_retries_with_controlled_backoff_and_progress(
    monkeypatch,
) -> None:
    provider = _RetryingEmbeddingProvider()
    delays: list[int] = []
    progress: list[tuple[int, int]] = []

    async def controlled_sleep(delay: int) -> None:
        delays.append(delay)

    async def record_progress(current: int, total: int) -> None:
        progress.append((current, total))

    monkeypatch.setattr(
        "astrbot.core.provider.provider.asyncio.sleep", controlled_sleep
    )

    result = await provider.get_embeddings_batch(
        ["first", "second"],
        batch_size=2,
        tasks_limit=1,
        max_retries=2,
        progress_callback=record_progress,
    )

    assert result == [[5.0], [6.0]]
    assert provider.calls == 2
    assert delays == [1]
    assert progress == [(2, 2)]


@pytest.mark.asyncio
async def test_embedding_batch_propagates_provider_cancellation() -> None:
    provider = _CancelledEmbeddingProvider({"type": "test"}, {})

    with pytest.raises(asyncio.CancelledError):
        await provider.get_embeddings_batch(["cancelled"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kwargs", "parameter"),
    [
        ({"batch_size": 0}, "batch_size"),
        ({"tasks_limit": 0}, "tasks_limit"),
        ({"max_retries": 0}, "max_retries"),
    ],
)
async def test_embedding_batch_rejects_non_positive_limits(
    kwargs: dict[str, int],
    parameter: str,
) -> None:
    provider = _RetryingEmbeddingProvider()

    with pytest.raises(ValueError, match=parameter):
        await provider.get_embeddings_batch([], **kwargs)


@pytest.mark.asyncio
async def test_embedding_batch_rejects_incomplete_provider_output() -> None:
    provider = _ShortEmbeddingProvider()

    with pytest.raises(Exception, match="returned 1 embeddings for 2 texts"):
        await provider.get_embeddings_batch(
            ["first", "second"],
            batch_size=2,
            max_retries=3,
        )

    assert provider.calls == 1


@pytest.mark.asyncio
async def test_embedding_batch_does_not_retry_progress_callback_failures() -> None:
    provider = _ProgressFailingEmbeddingProvider()

    async def failing_progress(_current: int, _total: int) -> None:
        raise RuntimeError("progress callback failed")

    with pytest.raises(Exception, match="progress callback failed"):
        await provider.get_embeddings_batch(
            ["only"],
            max_retries=3,
            progress_callback=failing_progress,
        )

    assert provider.calls == 1


@pytest.mark.asyncio
async def test_default_tts_stream_cancellation_removes_generated_audio(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "generated.wav"
    provider = _FileTTSProvider(output_path)
    text_queue: asyncio.Queue[str | None] = asyncio.Queue()
    await text_queue.put("hello")
    await text_queue.put(None)
    audio_queue = _BlockingAudioQueue()

    task = asyncio.create_task(provider.get_audio_stream(text_queue, audio_queue))
    await asyncio.wait_for(audio_queue.put_started.wait(), timeout=1)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert not output_path.exists()


@pytest.mark.asyncio
async def test_default_tts_stream_outputs_accumulated_audio_and_cleans_up(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "generated.wav"
    provider = _FileTTSProvider(output_path)
    text_queue: asyncio.Queue[str | None] = asyncio.Queue()
    audio_queue: asyncio.Queue[bytes | tuple[str, bytes] | None] = asyncio.Queue()
    await text_queue.put("hello ")
    await text_queue.put("world")
    await text_queue.put(None)

    await provider.get_audio_stream(text_queue, audio_queue)

    assert await audio_queue.get() == ("hello world", b"hello world")
    assert await audio_queue.get() is None
    assert not output_path.exists()


@pytest.mark.asyncio
async def test_stt_health_check_uses_bundled_sample_path() -> None:
    provider = _RecordingSTTProvider()

    await provider.test()

    assert len(provider.audio_urls) == 1
    assert Path(provider.audio_urls[0]).name == "stt_health_check.wav"
    assert Path(provider.audio_urls[0]).parent.name == "samples"


@pytest.mark.asyncio
async def test_rerank_health_check_rejects_empty_results() -> None:
    await _StaticRerankProvider([RerankResult(index=0, relevance_score=1.0)]).test()

    with pytest.raises(Exception, match="no results"):
        await _StaticRerankProvider([]).test()


def test_nvidia_embedding_response_is_ordered_by_response_index() -> None:
    provider = NvidiaEmbeddingProvider.__new__(NvidiaEmbeddingProvider)

    result = provider._parse_response(
        {
            "data": [
                {"index": 1, "embedding": [2.0]},
                {"index": 0, "embedding": [1.0]},
            ]
        }
    )

    assert result == [[1.0], [2.0]]


@pytest.mark.asyncio
async def test_openai_embedding_sets_model_and_closes_its_client(monkeypatch) -> None:
    class FakeAsyncOpenAI:
        def __init__(self, **kwargs) -> None:  # noqa: ANN003
            self.kwargs = kwargs
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(openai_embedding_source, "AsyncOpenAI", FakeAsyncOpenAI)
    provider = openai_embedding_source.OpenAIEmbeddingProvider(
        {
            "type": "openai_embedding",
            "embedding_api_key": "test-key",
            "embedding_model": "test-embedding-model",
        },
        {},
    )
    client = provider.client

    try:
        assert provider.get_model() == "test-embedding-model"
    finally:
        await provider.terminate()

    assert client.closed
    assert provider.client is None


@pytest.mark.asyncio
async def test_vllm_rerank_payload_and_termination_contract() -> None:
    client = _FakeRerankClient()
    provider = VLLMRerankProvider.__new__(VLLMRerankProvider)
    provider.client = client
    provider.base_url = "https://rerank.example.test"
    provider.api_suffix = "/v1/rerank"
    provider.model = "test-reranker"

    result = await provider.rerank("query", ["a", "b"], top_n=1)

    assert result == [RerankResult(index=1, relevance_score=0.9)]
    assert client.posts == [
        (
            "https://rerank.example.test/v1/rerank",
            {
                "query": "query",
                "documents": ["a", "b"],
                "model": "test-reranker",
                "top_n": 1,
            },
        )
    ]

    await provider.terminate()

    assert client.closed
    assert provider.client is None
