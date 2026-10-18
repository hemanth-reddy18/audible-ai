"""
Audible AI — Phase 2 Regression Test Suite: Command Queue, Idempotency & Session Management
Validates:
1. Unique call IDs and session isolation
2. Unique speech command IDs and sequential ordering
3. Atomic command claiming (no duplicate deliveries to polling clients)
4. Duplicate speech command suppression
5. One greeting per call session enforcement
6. Explicit acknowledgment handling and completion status
7. Session cancellation upon call hangup (no stale audio carryover)
8. Stale session pruning and memory bounds
"""

import time
import pytest
from api.services.supermarket.session_manager import SupermarketSessionManager, CommandState
from api.services.supermarket.models import ConversationState


@pytest.fixture
def session_mgr():
    mgr = SupermarketSessionManager.get_instance()
    # Reset any state
    mgr._sessions.clear()
    mgr._session_created_at.clear()
    mgr._pending_commands.clear()
    mgr._claimed_commands.clear()
    mgr._completed_commands.clear()
    mgr._last_speech_texts.clear()
    mgr._greeted_sessions.clear()
    mgr._active_session_id = None
    mgr._seq_counter = 0
    return mgr


def test_01_unique_call_ids_and_session_isolation(session_mgr):
    """Verify distinct call sessions maintain separate state and command queues."""
    session_a = "call_1001"
    session_b = "call_1002"

    order_a = session_mgr.get_or_create_session(session_a, caller_id="+919876543210")
    order_b = session_mgr.get_or_create_session(session_b, caller_id="+919876543211")

    assert order_a.session_id == session_a
    assert order_b.session_id == session_b
    assert order_a.caller_id != order_b.caller_id

    # Queue command to session A only
    cmd_a = session_mgr.queue_command(session_a, "SPEAK", {"text": "Hello Customer A"})
    
    # Session B should have zero commands
    cmds_b = session_mgr.claim_commands(session_b)
    assert len(cmds_b) == 0

    # Session A should have exactly 1 command
    cmds_a = session_mgr.claim_commands(session_a)
    assert len(cmds_a) == 1
    assert cmds_a[0]["command_id"] == cmd_a
    assert cmds_a[0]["text"] == "Hello Customer A"


def test_02_unique_speech_command_ids_and_sequence(session_mgr):
    """Verify all queued commands receive unique IDs and monotonically increasing sequences."""
    session_id = "call_2001"
    session_mgr.get_or_create_session(session_id)

    id_1 = session_mgr.queue_command(session_id, "SPEAK", {"text": "Phrase One"})
    id_2 = session_mgr.queue_command(session_id, "SPEAK", {"text": "Phrase Two"})
    id_3 = session_mgr.queue_command(session_id, "SEND_SMS", {"phone_number": "+919999999999", "message": "Test"})

    assert id_1 != id_2
    assert id_2 != id_3
    assert id_1.startswith("cmd_")
    assert id_2.startswith("cmd_")
    assert id_3.startswith("cmd_")

    claimed = session_mgr.claim_commands(session_id)
    assert len(claimed) == 3
    assert claimed[0]["seq"] < claimed[1]["seq"] < claimed[2]["seq"]


def test_03_atomic_command_claiming(session_mgr):
    """Verify that claiming commands moves them to in-flight and prevents double-delivery."""
    session_id = "call_3001"
    session_mgr.get_or_create_session(session_id)

    cmd_id = session_mgr.queue_command(session_id, "SPEAK", {"text": "Processing your order"})

    # First polling claim
    first_poll = session_mgr.claim_commands(session_id, client_id="client_worker_1")
    assert len(first_poll) == 1
    assert first_poll[0]["command_id"] == cmd_id
    assert first_poll[0]["status"] == CommandState.CLAIMED.value

    # Immediate second polling claim by another worker/thread
    second_poll = session_mgr.claim_commands(session_id, client_id="client_worker_2")
    assert len(second_poll) == 0  # Command is in-flight, must not be redelivered


def test_04_duplicate_command_suppression(session_mgr):
    """Verify that identical consecutive speech utterances are suppressed."""
    session_id = "call_4001"
    session_mgr.get_or_create_session(session_id)

    text = "Welcome to FreshMart! How may I assist you?"
    cmd1 = session_mgr.queue_command(session_id, "SPEAK", {"text": text})
    assert cmd1.startswith("cmd_")

    # Attempting to queue identical text immediately
    cmd2 = session_mgr.queue_command(session_id, "SPEAK", {"text": text})
    assert cmd2 == "duplicate_suppressed"

    # Claiming should only yield the first command
    claimed = session_mgr.claim_commands(session_id)
    assert len(claimed) == 1
    assert claimed[0]["command_id"] == cmd1


def test_05_one_greeting_per_call_enforcement(session_mgr):
    """Verify should_greet returns True once, and False on any subsequent attempts for same session."""
    session_id = "call_5001"
    session_mgr.get_or_create_session(session_id)

    # Initial check
    assert session_mgr.should_greet(session_id) is True

    # After greeting is queued/marked
    session_mgr.mark_greeted(session_id)
    assert session_mgr.should_greet(session_id) is False

    # Even if multiple offhook callbacks fire
    assert session_mgr.should_greet(session_id) is False

    # Another session still receives greeting
    new_session = "call_5002"
    assert session_mgr.should_greet(new_session) is True


def test_06_acknowledgment_lifecycle(session_mgr):
    """Verify acknowledgment marks commands completed and cleans in-flight tracking."""
    session_id = "call_6001"
    session_mgr.get_or_create_session(session_id)

    cmd_id = session_mgr.queue_command(session_id, "SPEAK", {"text": "Farewell message", "should_hangup": True})
    claimed = session_mgr.claim_commands(session_id)
    assert len(claimed) == 1

    # Client executes utterance and invokes ack
    acked = session_mgr.ack_command(cmd_id, status="COMPLETED")
    assert acked is True

    # Ensure it is moved to completed commands
    assert cmd_id in session_mgr._completed_commands
    assert session_mgr._completed_commands[cmd_id]["status"] == "COMPLETED"
    assert cmd_id not in session_mgr._claimed_commands


def test_07_cancellation_on_call_hangup(session_mgr):
    """Verify that when a call ends, in-flight/pending speech is cancelled so it never plays on next call."""
    session_id = "call_7001"
    session_mgr.get_or_create_session(session_id)

    cmd1 = session_mgr.queue_command(session_id, "SPEAK", {"text": "Slow utterance 1"})
    cmd2 = session_mgr.queue_command(session_id, "SPEAK", {"text": "Slow utterance 2"})
    
    # Claim cmd1
    session_mgr.claim_commands(session_id)

    # Remote caller hangs up suddenly
    cancelled = session_mgr.cancel_session_commands(session_id)
    assert cancelled >= 1

    # Ensure no commands remain for this session
    rem = session_mgr.claim_commands(session_id)
    assert len(rem) == 0


def test_08_stale_session_cleanup(session_mgr):
    """Verify stale sessions older than threshold are pruned."""
    old_session = "call_old_1"
    session_mgr.get_or_create_session(old_session)
    # Simulate session created 3600s ago
    from datetime import datetime, timedelta
    session_mgr._session_created_at[old_session] = datetime.utcnow() - timedelta(seconds=3600)

    recent_session = "call_recent_2"
    session_mgr.get_or_create_session(recent_session)

    pruned = session_mgr.cleanup_stale_sessions(max_age_seconds=1800)
    assert pruned == 1
    assert old_session not in session_mgr._sessions
    assert recent_session in session_mgr._sessions
