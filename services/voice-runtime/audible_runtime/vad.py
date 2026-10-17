"""Audible AI Voice Engine — Voice Activity Detection & Barge-in Controller."""

import time
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class VADConfig:
    """Voice Activity Detection configuration."""
    sample_rate: int = 16000
    frame_duration_ms: int = 30
    energy_threshold: float = 0.015
    silence_duration_secs: float = 0.65
    speech_start_threshold_frames: int = 3
    speech_stop_threshold_frames: int = 8


class BargeInController:
    """Manages conversational interruptions (barge-in).
    
    When an agent is actively speaking (TTS audio is playing) and user speech
    is detected by VAD:
    1. Immediately signals the audio playback queue to stop and purge buffered frames.
    2. Signals the LLM synthesis pipeline to cancel current generation.
    3. Retains previous partial context and accepts new user input instantly.
    """

    def __init__(
        self,
        on_interrupt: Optional[Callable[[], None]] = None,
        config: Optional[VADConfig] = None,
    ):
        self.config = config or VADConfig()
        self.on_interrupt = on_interrupt
        self.is_agent_speaking = False
        self.is_user_speaking = False
        self.speech_frames_count = 0
        self.silence_frames_count = 0
        self.last_speech_time = 0.0
        self.interruption_count = 0

    def set_agent_speaking(self, speaking: bool) -> None:
        self.is_agent_speaking = speaking
        if speaking:
            self.speech_frames_count = 0

    def process_frame_energy(self, rms_energy: float) -> bool:
        """Process an incoming audio frame energy level.
        
        Returns True if a barge-in interruption was triggered.
        """
        now = time.time()
        is_frame_speech = rms_energy >= self.config.energy_threshold

        if is_frame_speech:
            self.speech_frames_count += 1
            self.silence_frames_count = 0
            self.last_speech_time = now

            if not self.is_user_speaking and self.speech_frames_count >= self.config.speech_start_threshold_frames:
                self.is_user_speaking = True
                if self.is_agent_speaking:
                    # Trigger barge-in
                    self.interruption_count += 1
                    if self.on_interrupt:
                        self.on_interrupt()
                    return True
        else:
            self.silence_frames_count += 1
            if self.is_user_speaking and self.silence_frames_count >= self.config.speech_stop_threshold_frames:
                self.is_user_speaking = False
                self.speech_frames_count = 0

        return False

    def reset(self) -> None:
        self.is_agent_speaking = False
        self.is_user_speaking = False
        self.speech_frames_count = 0
        self.silence_frames_count = 0
