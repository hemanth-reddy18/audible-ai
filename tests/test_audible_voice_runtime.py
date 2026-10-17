"""Unit tests for Audible Voice Runtime components."""

import pytest
import time
import sys
import os

# Ensure services/voice-runtime is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "voice-runtime")))

from audible_runtime.vad import BargeInController, VADConfig
from audible_runtime.metrics import LatencyTracker, TurnLatencyRecord


def test_barge_in_controller_trigger():
    """Verify barge-in interruption triggers when agent is speaking and speech occurs."""
    interrupted = False

    def on_interrupt_callback():
        nonlocal interrupted
        interrupted = True

    config = VADConfig(
        energy_threshold=0.01,
        speech_start_threshold_frames=2,
    )
    controller = BargeInController(on_interrupt=on_interrupt_callback, config=config)

    # 1. Agent starts speaking
    controller.set_agent_speaking(True)
    assert controller.is_agent_speaking is True
    assert interrupted is False

    # 2. Quiet frame (no interruption)
    result = controller.process_frame_energy(0.002)
    assert result is False
    assert interrupted is False

    # 3. Speech frame 1 (below frame count threshold)
    result = controller.process_frame_energy(0.05)
    assert result is False
    assert interrupted is False

    # 4. Speech frame 2 (meets threshold -> barge in!)
    result = controller.process_frame_energy(0.05)
    assert result is True
    assert interrupted is True
    assert controller.interruption_count == 1


def test_latency_tracker_calculations():
    """Verify precision latency calculations for conversation turns."""
    tracker = LatencyTracker()
    now = time.time()

    turn = tracker.start_turn("turn-101", speech_ended_at=now)
    assert turn.turn_id == "turn-101"

    turn.stt_final_transcript_at = now + 0.120  # +120ms
    turn.llm_first_token_at = now + 0.280       # +160ms after STT
    turn.tts_first_audio_chunk_at = now + 0.350 # +70ms after LLM
    turn.audio_playback_started_at = now + 0.380 # +30ms network playback

    summary = tracker.get_turn_summary("turn-101")
    assert round(summary["stt_latency_ms"]) == 120
    assert round(summary["llm_ttft_ms"]) == 160
    assert round(summary["tts_ttfb_ms"]) == 70
    assert round(summary["total_turnaround_ms"]) == 380
