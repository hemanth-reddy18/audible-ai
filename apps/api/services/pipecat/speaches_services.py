"""Speaches and Local Offline Audio Services for Audible AI.

Provides:
- SpeachesLLMService / SpeachesLLMSettings (Ollama OpenAI-compatible adapter)
- SpeachesSTTService / SpeachesSTTSettings (Local STT adapter with speech_recognition fallback)
- SpeachesTTSService / SpeachesTTSSettings (Local Windows SAPI offline TTS adapter)
"""

import asyncio
import io
import time
from dataclasses import dataclass
from typing import AsyncGenerator

from loguru import logger
from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    TTSAudioRawFrame,
    TranscriptionFrame,
)
from pipecat.services.openai.base_llm import OpenAILLMSettings
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.settings import STTSettings, TTSSettings
from pipecat.services.stt_service import SegmentedSTTService
from pipecat.services.tts_service import TTSService
from pipecat.utils.time import time_now_iso8601


# ---------------------------------------------------------------------------
# LLM Service & Settings
# ---------------------------------------------------------------------------

class SpeachesLLMSettings(OpenAILLMSettings):
    """Configuration settings for Speaches / Ollama LLM service."""

    def __init__(self, model: str = "llama3.2:1b", **kwargs):
        super().__init__(model=model, **kwargs)


class SpeachesLLMService(OpenAILLMService):
    """Ollama OpenAI-compatible LLM service wrapper for local inference."""

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "none",
        settings: SpeachesLLMSettings | None = None,
        enable_direct_mode: bool = False,
        **kwargs,
    ):
        settings = settings or SpeachesLLMSettings(model="llama3.2:1b")
        super().__init__(
            base_url=base_url or "http://localhost:11434/v1",
            api_key=api_key or "none",
            settings=settings,
            **kwargs,
        )


# ---------------------------------------------------------------------------
# STT Service & Settings
# ---------------------------------------------------------------------------

@dataclass
class SpeachesSTTSettings(STTSettings):
    """Configuration settings for Speaches / Local STT service."""

    model: str = "Systran/faster-whisper-small"
    language: str | None = None


class SpeachesSTTService(SegmentedSTTService):
    """Local Speech-to-Text service supporting HTTP and offline recognition."""

    def __init__(
        self,
        *,
        base_url: str | None = "http://localhost:11434/v1",
        api_key: str = "none",
        settings: SpeachesSTTSettings | None = None,
        sample_rate: int = 16000,
        **kwargs,
    ):
        settings = settings or SpeachesSTTSettings()
        super().__init__(sample_rate=sample_rate, settings=settings, **kwargs)
        self._base_url = base_url
        self._api_key = api_key or "none"

    def _transcribe_offline_sync(self, audio_bytes: bytes, sample_rate: int) -> str:
        """Transcribe PCM audio bytes locally using SpeechRecognition."""
        try:
            import speech_recognition as sr

            r = sr.Recognizer()
            audio_data = sr.AudioData(audio_bytes, sample_rate, 2)
            lang = self._settings.language or "en-US"
            return r.recognize_google(audio_data, language=lang)
        except Exception:
            return ""

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame, None]:
        """Transcribe speech audio bytes into transcription frames."""
        if not audio or len(audio) < 1600:
            return

        try:
            await self.start_processing_metrics()
            text = ""

            # Attempt HTTP transcription if base_url is a non-Ollama remote/local STT service
            if (
                self._base_url
                and "11434" not in self._base_url
                and self._base_url.startswith("http")
            ):
                try:
                    import httpx

                    url = f"{self._base_url.rstrip('/')}/audio/transcriptions"
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        files = {"file": ("audio.wav", audio, "audio/wav")}
                        data = {"model": self._settings.model}
                        if self._settings.language:
                            data["language"] = self._settings.language
                        res = await client.post(
                            url,
                            headers={"Authorization": f"Bearer {self._api_key}"},
                            files=files,
                            data=data,
                        )
                        if res.status_code == 200:
                            json_data = res.json()
                            text = json_data.get("text", "").strip()
                except Exception as e:
                    logger.debug(f"Remote Speaches STT skipped: {e}")

            # Fall back to local SpeechRecognition if remote STT was not used or yielded empty
            if not text:
                text = await asyncio.to_thread(
                    self._transcribe_offline_sync,
                    audio,
                    self.sample_rate or 16000,
                )

            await self.stop_processing_metrics()

            if text and text.strip():
                logger.info(f"[SpeachesSTT] Transcribed user utterance: '{text}'")
                yield TranscriptionFrame(
                    text=text.strip(),
                    user_id=getattr(self, "_user_id", "user"),
                    timestamp=time_now_iso8601(),
                    finalized=True,
                )
        except Exception as e:
            logger.error(f"[SpeachesSTT] Error during transcription: {e}")
            yield ErrorFrame(error=f"STT Error: {e}")


# ---------------------------------------------------------------------------
# TTS Service & Settings
# ---------------------------------------------------------------------------

@dataclass
class SpeachesTTSSettings(TTSSettings):
    """Configuration settings for Speaches / Local TTS service."""

    model: str = "tts-1"
    voice: str = "alloy"
    language: str | None = None
    speed: float | None = 1.0


class SpeachesTTSService(TTSService):
    """Local Text-to-Speech service using Windows SAPI for 100% offline synthesis."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str = "none",
        settings: SpeachesTTSSettings | None = None,
        sample_rate: int = 16000,
        **kwargs,
    ):
        settings = settings or SpeachesTTSSettings()
        super().__init__(settings=settings, sample_rate=sample_rate, **kwargs)
        self._base_url = base_url
        self._api_key = api_key or "none"
        self._voice_name = settings.voice

    def _sapi_synthesize_sync(self, text: str) -> bytes:
        """Synthesize text into raw 16kHz 16-bit Mono PCM bytes using Windows SAPI."""
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        try:
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            stream = win32com.client.Dispatch("SAPI.SpMemoryStream")
            fmt = win32com.client.Dispatch("SAPI.SpAudioFormat")
            fmt.Type = 18  # SAFT16kHz16BitMono (16000Hz 16-bit mono)
            stream.Format = fmt
            speaker.AudioOutputStream = stream

            if self._voice_name and self._voice_name != "alloy":
                for v in speaker.GetVoices():
                    if self._voice_name.lower() in v.GetDescription().lower():
                        speaker.Voice = v
                        break

            speed = getattr(self._settings, "speed", 1.0)
            if speed:
                rate = int((speed - 1.0) * 10)
                speaker.Rate = max(-10, min(10, rate))

            speaker.Speak(text)
            return bytes(stream.GetData())
        finally:
            pythoncom.CoUninitialize()

    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame, None]:
        """Synthesize text into PCM audio frames streamed via WebRTC."""
        if not text or not text.strip():
            return

        try:
            await self.start_tts_usage_metrics(text)

            # Synthesize via Windows SAPI in background thread
            pcm_bytes = await asyncio.to_thread(self._sapi_synthesize_sync, text)

            await self.stop_ttfb_metrics()

            if pcm_bytes:
                # Stream PCM in 100ms chunks (3200 bytes per chunk at 16kHz 16-bit mono)
                chunk_size = 3200
                for i in range(0, len(pcm_bytes), chunk_size):
                    chunk = pcm_bytes[i:i + chunk_size]
                    yield TTSAudioRawFrame(
                        audio=chunk,
                        sample_rate=self.sample_rate or 16000,
                        num_channels=1,
                        context_id=context_id,
                    )
        except Exception as e:
            logger.error(f"[SpeachesTTS] SAPI TTS synthesis failed: {e}")
            yield ErrorFrame(error=f"TTS synthesis error: {e}")
