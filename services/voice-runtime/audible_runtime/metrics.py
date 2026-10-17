"""Audible AI Voice Engine — Precision Real-time Latency Metrics Tracker."""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TurnLatencyRecord:
    """Detailed timing records for a conversational turn."""
    turn_id: str
    user_speech_ended_at: float = 0.0
    stt_final_transcript_at: float = 0.0
    llm_first_token_at: float = 0.0
    tts_first_audio_chunk_at: float = 0.0
    audio_playback_started_at: float = 0.0
    turn_completed_at: float = 0.0

    @property
    def stt_latency_ms(self) -> Optional[float]:
        if self.stt_final_transcript_at and self.user_speech_ended_at:
            return max(0.0, (self.stt_final_transcript_at - self.user_speech_ended_at) * 1000)
        return None

    @property
    def llm_ttft_ms(self) -> Optional[float]:
        """Time to First Token from STT final."""
        if self.llm_first_token_at and self.stt_final_transcript_at:
            return max(0.0, (self.llm_first_token_at - self.stt_final_transcript_at) * 1000)
        return None

    @property
    def tts_ttfb_ms(self) -> Optional[float]:
        """Time to First Audio Byte from LLM first token."""
        if self.tts_first_audio_chunk_at and self.llm_first_token_at:
            return max(0.0, (self.tts_first_audio_chunk_at - self.llm_first_token_at) * 1000)
        return None

    @property
    def conversational_turnaround_ms(self) -> Optional[float]:
        """Total turnaround time: user speech finished to agent voice heard."""
        if self.audio_playback_started_at and self.user_speech_ended_at:
            return max(0.0, (self.audio_playback_started_at - self.user_speech_ended_at) * 1000)
        return None


class LatencyTracker:
    """Collects and aggregates real-world latency metrics across calls."""

    def __init__(self):
        self.turns: Dict[str, TurnLatencyRecord] = {}

    def start_turn(self, turn_id: str, speech_ended_at: Optional[float] = None) -> TurnLatencyRecord:
        record = TurnLatencyRecord(
            turn_id=turn_id,
            user_speech_ended_at=speech_ended_at or time.time(),
        )
        self.turns[turn_id] = record
        return record

    def record_stt_final(self, turn_id: str) -> None:
        if turn_id in self.turns:
            self.turns[turn_id].stt_final_transcript_at = time.time()

    def record_llm_first_token(self, turn_id: str) -> None:
        if turn_id in self.turns:
            self.turns[turn_id].llm_first_token_at = time.time()

    def record_tts_first_audio(self, turn_id: str) -> None:
        if turn_id in self.turns:
            self.turns[turn_id].tts_first_audio_chunk_at = time.time()

    def record_playback_started(self, turn_id: str) -> None:
        if turn_id in self.turns:
            self.turns[turn_id].audio_playback_started_at = time.time()

    def get_turn_summary(self, turn_id: str) -> Dict[str, Optional[float]]:
        turn = self.turns.get(turn_id)
        if not turn:
            return {}
        return {
            "stt_latency_ms": turn.stt_latency_ms,
            "llm_ttft_ms": turn.llm_ttft_ms,
            "tts_ttfb_ms": turn.tts_ttfb_ms,
            "total_turnaround_ms": turn.conversational_turnaround_ms,
        }
