"""Audible AI Voice Engine — Decoupled Provider Adapters Specification."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional


class AdapterType(str, Enum):
    STT = "stt"
    LLM = "llm"
    TTS = "tts"
    S2S = "s2s"


@dataclass
class AudioChunk:
    """Raw audio chunk (16kHz / 24kHz PCM or Opus)."""
    data: bytes
    sample_rate: int = 16000
    channels: int = 1
    timestamp_ms: Optional[float] = None


@dataclass
class TranscriptResult:
    """Transcription fragment from STT engine."""
    text: str
    is_final: bool = False
    confidence: float = 1.0
    language: str = "en"
    start_time_ms: Optional[float] = None
    end_time_ms: Optional[float] = None


@dataclass
class ToolCallRequest:
    """Function / Tool call requested by LLM."""
    call_id: str
    function_name: str
    arguments: Dict[str, Any]


@dataclass
class LLMTokenResponse:
    """Token chunk emitted by LLM stream."""
    content: str
    is_final: bool = False
    tool_call: Optional[ToolCallRequest] = None


class BaseSTTAdapter(ABC):
    """Abstract interface for Speech-to-Text streaming engines."""

    @abstractmethod
    async def process_audio(self, chunk: AudioChunk) -> AsyncGenerator[TranscriptResult, None]:
        """Stream audio chunks into STT engine and yield transcripts."""
        pass

    @abstractmethod
    async def flush(self) -> Optional[TranscriptResult]:
        """Flush remaining audio buffer."""
        pass


class BaseLLMAdapter(ABC):
    """Abstract interface for LLM conversation engines."""

    @abstractmethod
    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[LLMTokenResponse, None]:
        """Stream tokens and tool calls from LLM."""
        pass


class BaseTTSAdapter(ABC):
    """Abstract interface for Text-to-Speech synthesis engines."""

    @abstractmethod
    async def synthesize_stream(
        self,
        text_stream: AsyncGenerator[str, None],
        voice_id: str,
    ) -> AsyncGenerator[AudioChunk, None]:
        """Convert incoming streaming text into streaming audio chunks."""
        pass


class BaseS2SAdapter(ABC):
    """Abstract interface for native Speech-to-Speech models (e.g. Gemini Live, OpenAI Realtime)."""

    @abstractmethod
    async def send_audio(self, chunk: AudioChunk) -> None:
        """Feed user mic audio to the model."""
        pass

    @abstractmethod
    async def receive_events(self) -> AsyncGenerator[Any, None]:
        """Yield mixed audio chunks, text transcripts, and tool calls."""
        pass
