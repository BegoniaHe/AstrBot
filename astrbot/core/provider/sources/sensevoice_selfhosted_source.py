"""Author: diudiu62
Date: 2025-02-24 18:04:18
LastEditTime: 2025-02-25 14:06:30
"""

import asyncio
import importlib
import re
from typing import Any

from astrbot import logger
from astrbot.core.utils.error_redaction import safe_error
from astrbot.core.utils.media_utils import MediaResolver

from ..entities import ProviderType
from ..provider import STTProvider
from ..register import register_provider_adapter


@register_provider_adapter(
    "sensevoice_stt_selfhost",
    "SenseVoice 自托管语音识别 模型部署",
    provider_type=ProviderType.SPEECH_TO_TEXT,
)
class ProviderSenseVoiceSTTSelfHost(STTProvider):
    def __init__(
        self,
        provider_config: dict,
        provider_settings: dict,
    ) -> None:
        super().__init__(provider_config, provider_settings)
        self.set_model(provider_config["stt_model"])
        self.model: Any | None = None
        self.is_emotion = provider_config.get("is_emotion", False)
        self._executor_futures: set[asyncio.Future[Any]] = set()

    async def _run_in_executor(self, callback, *args):
        """Run blocking model work and track the submitted future for shutdown."""
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(None, callback, *args)
        self._executor_futures.add(future)
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            future.cancel()
            raise
        finally:
            self._executor_futures.discard(future)

    async def initialize(self) -> None:
        logger.info("下载或者加载 SenseVoice 模型中，这可能需要一些时间 ...")
        try:
            funasr_onnx = importlib.import_module("funasr_onnx")
        except ImportError as exc:
            logger.error("Failed to import funasr_onnx: %s", safe_error("", exc))
            raise RuntimeError("funasr_onnx is not installed") from None
        except Exception as exc:
            logger.error(
                "SenseVoice model initialization failed: %s",
                safe_error("", exc),
            )
            raise RuntimeError("SenseVoice model initialization failed.") from None

        try:
            model = await self._run_in_executor(
                lambda: funasr_onnx.SenseVoiceSmall(
                    self.model_name,
                    quantize=True,
                    batch_size=16,
                ),
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(
                "SenseVoice model initialization failed: %s",
                safe_error("", exc),
            )
            raise RuntimeError("SenseVoice model initialization failed.") from None

        if model is None:
            logger.error("SenseVoice model initialization returned no model.")
            raise RuntimeError("SenseVoice model initialization failed.")

        self.model = model

        logger.info("SenseVoice 模型加载完成。")

    async def get_text(self, audio_url: str) -> str:
        model = self.model
        if model is None:
            raise RuntimeError("SenseVoice model is not initialized.")

        try:
            postprocess_utils = importlib.import_module(
                "funasr_onnx.utils.postprocess_utils"
            )
            async with MediaResolver(
                audio_url,
                media_type="audio",
                default_suffix=".wav",
            ).as_path(target_format="wav") as audio:
                result = await self._run_in_executor(
                    lambda: model(str(audio.path), language="auto", use_itn=True),
                )

            if (
                not isinstance(result, (list, tuple))
                or not result
                or not isinstance(result[0], str)
            ):
                logger.warning("SenseVoice returned an invalid recognition response.")
                raise ValueError("invalid recognition response")

            source_text = result[0]
            text = postprocess_utils.rich_transcription_postprocess(source_text)
            if not isinstance(text, str):
                logger.warning("SenseVoice returned an invalid transcription response.")
                raise ValueError("invalid transcription response")

            if self.is_emotion:
                matches = re.findall(r"<\|([^|]+)\|>", source_text)
                if len(matches) >= 2:
                    emotion = matches[1]
                    text = f"(当前的情绪：{emotion}) {text}"
                else:
                    logger.warning("未能提取到情绪信息")
            return text
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("SenseVoice transcription failed: %s", safe_error("", exc))
            raise RuntimeError("SenseVoice transcription failed.") from None

    async def terminate(self) -> None:
        """Cancel pending model work and release the loaded model reference."""
        for future in tuple(self._executor_futures):
            future.cancel()
        self._executor_futures.clear()
        self.model = None
