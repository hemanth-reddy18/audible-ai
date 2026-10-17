"""Audible AI — Pipecat compatibility helpers and enums."""

from abc import ABC, abstractmethod
from enum import Enum
import sys
import types
from typing import Any, Dict
from pipecat.audio.mixers.base_audio_mixer import BaseAudioMixer


class EndTaskReason(str, Enum):
    SYSTEM_CANCELLED = "system_cancelled"
    USER_HANGUP = "user_hangup"
    END_CALL = "end_call"
    TRANSFER_CALL = "transfer_call"
    CALL_TRANSFERRED = "call_transferred"
    VOICEMAIL_DETECTED = "voicemail_detected"
    CALL_DURATION_EXCEEDED = "call_duration_exceeded"
    USER_IDLE_MAX_DURATION_EXCEEDED = "user_idle_max_duration_exceeded"
    PIPELINE_ERROR = "pipeline_error"
    UNEXPECTED_ERROR = "unexpected_error"


class RealtimeFeedbackType(str, Enum):
    NODE_TRANSITION = "node_transition"
    USER_TRANSCRIPTION = "user_transcription"
    BOT_TEXT = "bot_text"
    FUNCTION_CALL_START = "function_call_start"
    FUNCTION_CALL_END = "function_call_end"
    TTFB_METRIC = "ttfb_metric"
    PIPELINE_ERROR = "pipeline_error"


class SilenceAudioMixer(BaseAudioMixer):
    """Audio mixer that outputs clean silence (passes audio through unmixed)."""

    async def start(self, sample_rate: int):
        pass

    async def stop(self):
        pass

    async def process_frame(self, frame):
        pass

    async def mix(self, audio: bytes) -> bytes:
        return audio


class HangupStrategy(ABC):
    @abstractmethod
    async def execute_hangup(self, context: Dict[str, Any]) -> bool:
        pass


class TransferStrategy(ABC):
    @abstractmethod
    async def execute_transfer(self, context: Dict[str, Any]) -> bool:
        pass


# Register in sys.modules for backward-compatible imports
try:
    import pipecat
    import pipecat.utils
    import pipecat.frames.frames as pipecat_frames
    from dataclasses import dataclass, field
    from typing import Sequence

    if not hasattr(pipecat_frames, "FunctionCallsFromLLMInfoFrame"):
        @dataclass
        class FunctionCallsFromLLMInfoFrame(pipecat_frames.DataFrame):
            function_calls: Sequence[Any] = field(default_factory=list)
        pipecat_frames.FunctionCallsFromLLMInfoFrame = FunctionCallsFromLLMInfoFrame

    if not hasattr(pipecat_frames, "NodeTransitionStartedFrame"):
        @dataclass
        class NodeTransitionStartedFrame(pipecat_frames.DataFrame):
            function_calls: Sequence[Any] = field(default_factory=list)
        pipecat_frames.NodeTransitionStartedFrame = NodeTransitionStartedFrame

    if not hasattr(pipecat_frames, "SpeechBoundaryFrame"):
        @dataclass
        class SpeechBoundaryFrame(pipecat_frames.DataFrame):
            speech_id: str = ""
            beginning: bool = True
        pipecat_frames.SpeechBoundaryFrame = SpeechBoundaryFrame
    
    enums_module = types.ModuleType("pipecat.utils.enums")
    enums_module.EndTaskReason = EndTaskReason
    enums_module.RealtimeFeedbackType = RealtimeFeedbackType
    pipecat.utils.enums = enums_module
    sys.modules["pipecat.utils.enums"] = enums_module

    import pipecat.audio.mixers
    silence_module = types.ModuleType("pipecat.audio.mixers.silence_mixer")
    silence_module.SilenceAudioMixer = SilenceAudioMixer
    pipecat.audio.mixers.silence_mixer = silence_module
    sys.modules["pipecat.audio.mixers.silence_mixer"] = silence_module

    import pipecat.serializers
    call_strategies_module = types.ModuleType("pipecat.serializers.call_strategies")
    call_strategies_module.HangupStrategy = HangupStrategy
    call_strategies_module.TransferStrategy = TransferStrategy
    pipecat.serializers.call_strategies = call_strategies_module
    sys.modules["pipecat.serializers.call_strategies"] = call_strategies_module

    # Tracing: attach langfuse_helpers to official pipecat.utils.tracing
    import pipecat.utils.tracing as pipecat_tracing
    from api.utils import tracing_compat

    langfuse_helpers = types.ModuleType("pipecat.utils.tracing.langfuse_helpers")
    langfuse_helpers.set_trace_public_resolver = tracing_compat.set_trace_public_resolver
    langfuse_helpers.traces_public_from_env = tracing_compat.traces_public_from_env
    langfuse_helpers.mark_trace_public = tracing_compat.mark_trace_public
    pipecat_tracing.langfuse_helpers = langfuse_helpers
    sys.modules["pipecat.utils.tracing.langfuse_helpers"] = langfuse_helpers

    # Managed cloud services compatibility
    from api.services.pipecat import managed_services

    dograh_svc_module = types.ModuleType("pipecat.services.dograh")
    sys.modules["pipecat.services.dograh"] = dograh_svc_module

    dograh_llm_mod = types.ModuleType("pipecat.services.dograh.llm")
    dograh_llm_mod.DograhLLMService = managed_services.DograhLLMService
    sys.modules["pipecat.services.dograh.llm"] = dograh_llm_mod

    dograh_stt_mod = types.ModuleType("pipecat.services.dograh.stt")
    dograh_stt_mod.DograhSTTService = managed_services.DograhSTTService
    dograh_stt_mod.DograhSTTSettings = managed_services.DograhSTTSettings
    sys.modules["pipecat.services.dograh.stt"] = dograh_stt_mod

    dograh_flux_mod = types.ModuleType("pipecat.services.dograh.flux")
    sys.modules["pipecat.services.dograh.flux"] = dograh_flux_mod
    dograh_flux_stt_mod = types.ModuleType("pipecat.services.dograh.flux.stt")
    dograh_flux_stt_mod.DograhFluxSTTService = managed_services.DograhFluxSTTService
    sys.modules["pipecat.services.dograh.flux.stt"] = dograh_flux_stt_mod

    dograh_tts_mod = types.ModuleType("pipecat.services.dograh.tts")
    dograh_tts_mod.DograhTTSService = managed_services.DograhTTSService
    dograh_tts_mod.DograhTTSSettings = managed_services.DograhTTSSettings
    sys.modules["pipecat.services.dograh.tts"] = dograh_tts_mod

    # XMLFunctionTagFilter
    import re
    from pipecat.utils.text.base_text_filter import BaseTextFilter

    class XMLFunctionTagFilter(BaseTextFilter):
        """Filter that strips XML function / tool invocation tags from text."""

        def __init__(self):
            super().__init__()
            self._pattern = re.compile(r"<[^>]+>")

        async def filter(self, text: str) -> str:
            if not text:
                return text
            return self._pattern.sub("", text)

    xml_filter_mod = types.ModuleType("pipecat.utils.text.xml_function_tag_filter")
    xml_filter_mod.XMLFunctionTagFilter = XMLFunctionTagFilter
    sys.modules["pipecat.utils.text.xml_function_tag_filter"] = xml_filter_mod

    # MiniMaxLLMService
    from pipecat.services.openai.llm import OpenAILLMService

    class MiniMaxLLMService(OpenAILLMService):
        class Settings(OpenAILLMService.Settings):
            pass

    import pipecat.services.minimax as pipecat_minimax
    minimax_llm_mod = types.ModuleType("pipecat.services.minimax.llm")
    minimax_llm_mod.MiniMaxLLMService = MiniMaxLLMService
    pipecat_minimax.llm = minimax_llm_mod
    sys.modules["pipecat.services.minimax.llm"] = minimax_llm_mod

    # CallbackUserMuteStrategy
    import asyncio
    from pipecat.turns.user_mute.base_user_mute_strategy import BaseUserMuteStrategy
    import pipecat.turns.user_mute as pipecat_user_mute

    class CallbackUserMuteStrategy(BaseUserMuteStrategy):
        def __init__(self, callback: Any = None, *, should_mute_callback: Any = None, **kwargs):
            super().__init__(**kwargs)
            self.should_mute_callback = should_mute_callback or callback

        async def process_frame(self, frame) -> bool:
            if self.should_mute_callback:
                try:
                    res = self.should_mute_callback()
                    if asyncio.iscoroutine(res):
                        return await res
                    return bool(res)
                except Exception:
                    return False
            return False

    pipecat_user_mute.CallbackUserMuteStrategy = CallbackUserMuteStrategy
except Exception:
    pass
