"""
Audible AI — Kokoro-82M High-Quality Neural TTS Engine
Self-hosted, zero-recurring-cost offline neural text-to-speech engine.
Runs locally on Windows host via ONNX Runtime with sub-second latency.
"""

import os
import io
import time
from typing import Optional, Dict, Tuple
import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro
from loguru import logger

# Base directory of audible ai repository
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
MODEL_DIR = os.path.join(REPO_ROOT, "models", "kokoro")
ONNX_PATH = os.path.join(MODEL_DIR, "kokoro-v0_19.onnx")
VOICES_PATH = os.path.join(MODEL_DIR, "voices.bin")


class KokoroTTSEngine:
    _instance: Optional["KokoroTTSEngine"] = None

    def __init__(self, onnx_path: str = ONNX_PATH, voices_path: str = VOICES_PATH):
        self.onnx_path = onnx_path
        self.voices_path = voices_path
        self._kokoro: Optional[Kokoro] = None
        self._cache: Dict[str, bytes] = {}
        self.default_voice = "af"
        self._load_model()

    @classmethod
    def get_instance(cls) -> "KokoroTTSEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_model(self):
        if not os.path.exists(self.onnx_path) or not os.path.exists(self.voices_path):
            logger.warning(f"Kokoro model files not found at {self.onnx_path}. TTS fallback enabled.")
            return

        try:
            t0 = time.time()
            self._kokoro = Kokoro(self.onnx_path, self.voices_path)
            logger.info(f"Kokoro Neural TTS initialized in {time.time()-t0:.2f}s with voices: {self._kokoro.get_voices()}")
        except Exception as e:
            logger.error(f"Failed to load Kokoro ONNX model: {e}")
            self._kokoro = None

    def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = 1.0,
        lang: str = "en-us"
    ) -> Tuple[bytes, int]:
        """
        Synthesizes text into 24kHz 16-bit PCM WAV bytes.
        Returns: (wav_bytes, sample_rate)
        """
        if not self._kokoro:
            raise RuntimeError("Kokoro TTS engine is not loaded.")

        clean_text = text.strip()
        cache_key = f"{clean_text}_{voice or self.default_voice}_{speed}"
        if cache_key in self._cache:
            return self._cache[cache_key], 24000

        target_voice = voice or self.default_voice
        if target_voice not in self._kokoro.get_voices():
            target_voice = self.default_voice

        t0 = time.time()
        samples, sample_rate = self._kokoro.create(clean_text, voice=target_voice, speed=speed, lang=lang)
        duration = len(samples) / sample_rate
        elapsed = time.time() - t0
        logger.info(f"Kokoro TTS: '{clean_text[:40]}...' in {elapsed:.2f}s (audio: {duration:.2f}s, RTF: {elapsed/duration:.3f})")

        # Encode to WAV in memory
        buffer = io.BytesIO()
        sf.write(buffer, samples, sample_rate, format='WAV', subtype='PCM_16')
        wav_bytes = buffer.getvalue()

        # Cache short phrases (< 120 chars)
        if len(clean_text) < 120:
            self._cache[cache_key] = wav_bytes

        return wav_bytes, sample_rate

    def synthesize_raw_pcm16(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = 1.0,
        lang: str = "en-us"
    ) -> Tuple[bytes, int]:
        """
        Synthesizes text into raw little-endian 16-bit mono PCM bytes for direct streaming.
        Returns: (pcm_bytes, sample_rate)
        """
        if not self._kokoro:
            raise RuntimeError("Kokoro TTS engine is not loaded.")

        target_voice = voice or self.default_voice
        if target_voice not in self._kokoro.get_voices():
            target_voice = self.default_voice

        samples, sample_rate = self._kokoro.create(text.strip(), voice=target_voice, speed=speed, lang=lang)
        # Convert float32 [-1.0, 1.0] to int16
        int16_samples = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
        return int16_samples.tobytes(), sample_rate
