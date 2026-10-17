"""Audible AI / Dograh managed cloud provider services compatibility shim."""

import json
from typing import Any, Optional
from pydantic import BaseModel
from pipecat.frames.frames import TTSStartedFrame
from pipecat.services.openai.llm import OpenAILLMService


class DograhLLMService(OpenAILLMService):
    """Managed LLM Service implementation."""

    def __init__(
        self,
        api_key: str = "",
        correlation_id: Optional[str] = None,
        base_url: Optional[str] = None,
        enable_direct_mode: bool = False,
        usage_context: Any = None,
        **kwargs,
    ):
        super().__init__(api_key=api_key, **kwargs)
        self.correlation_id = correlation_id
        self.base_url = base_url
        self.enable_direct_mode = enable_direct_mode
        self.usage_context = usage_context
        self._start_metadata: dict[str, Any] = {}

    def build_chat_completion_params(self, params: dict) -> dict:
        result = super().build_chat_completion_params(params)
        metadata = result.setdefault("metadata", {})
        if self.correlation_id:
            metadata["correlation_id"] = self.correlation_id
        metadata["mps_billing_version"] = "2"
        return result


class DograhSTTSettings(BaseModel):
    model: str = ""
    language: str = ""


class DograhSTTService:
    """Managed STT Service implementation."""

    def __init__(
        self,
        api_key: str = "",
        correlation_id: Optional[str] = None,
        sample_rate: int = 16000,
        base_url: str = "",
        settings: Any = None,
        keyterms: Any = None,
        should_interrupt: bool = False,
        **kwargs,
    ):
        self.api_key = api_key
        self.correlation_id = correlation_id
        self.sample_rate = sample_rate
        self.base_url = base_url
        self.settings = settings
        self.keyterms = keyterms
        self.should_interrupt = should_interrupt
        self._start_metadata: dict[str, Any] = {}
        self._websocket = None

    async def _websocket_connect(self, url, additional_headers):
        return None

    async def _connect_websocket(self):
        self._websocket = await self._websocket_connect(self.base_url, {})
        config_msg = {
            "type": "config",
            "correlation_id": self.correlation_id,
            "mps_billing_version": "2",
        }
        await self._websocket.send(json.dumps(config_msg))


class DograhFluxSTTService(DograhSTTService):
    pass


class DograhTTSSettings(BaseModel):
    model: str = ""
    voice: str = ""
    speed: float = 1.0


class DograhTTSService:
    """Managed TTS Service implementation."""

    def __init__(
        self,
        api_key: str = "",
        correlation_id: Optional[str] = None,
        sample_rate: int = 24000,
        base_url: str = "",
        settings: Any = None,
        text_filters: Any = None,
        skip_aggregator_types: Any = None,
        silence_time_s: float = 1.0,
        **kwargs,
    ):
        self.api_key = api_key
        self.correlation_id = correlation_id
        self.sample_rate = sample_rate
        self.base_url = base_url
        self.settings = settings
        self.text_filters = text_filters
        self.skip_aggregator_types = skip_aggregator_types
        self.silence_time_s = silence_time_s
        self._start_metadata: dict[str, Any] = {}
        self._websocket = None
        self._remote_initialized_context_ids: set[str] = set()

    async def _websocket_connect(self, url, additional_headers):
        return None

    async def _connect_websocket(self):
        self._websocket = await self._websocket_connect(self.base_url, {})
        config_msg = {
            "type": "config",
            "correlation_id": self.correlation_id,
            "mps_billing_version": "2",
        }
        await self._websocket.send(json.dumps(config_msg))

    async def run_tts(self, text: str, context_id: str):
        yield TTSStartedFrame()
        if self._websocket:
            ctx_msg = {
                "type": "create_context",
                "correlation_id": self.correlation_id,
                "mps_billing_version": "2",
                "context_id": context_id,
            }
            await self._websocket.send(json.dumps(ctx_msg))

    async def _receive_messages(self):
        if not self._websocket:
            return
        async for msg_str in self._websocket:
            msg = json.loads(msg_str)
            if msg.get("type") == "final":
                ctx_id = msg.get("context_id")
                if ctx_id:
                    self._remote_initialized_context_ids.discard(ctx_id)
                if (
                    ctx_id
                    and hasattr(self, "audio_context_available")
                    and not self.audio_context_available(ctx_id)
                ):
                    continue
                if hasattr(self, "remove_audio_context"):
                    await self.remove_audio_context(ctx_id)


__all__ = [
    "DograhLLMService",
    "DograhSTTSettings",
    "DograhSTTService",
    "DograhFluxSTTService",
    "DograhTTSSettings",
    "DograhTTSService",
]
