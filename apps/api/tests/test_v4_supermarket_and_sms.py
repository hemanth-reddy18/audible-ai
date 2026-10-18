"""
Audible AI V4 — Supermarket SQLite Persistence, Two-Way SMS,
and Kokoro-82M Neural TTS Automated Test Suite
"""

import os
import io
import pytest
import soundfile as sf
from datetime import datetime

from api.services.supermarket.models import GroceryItem, SupermarketOrder, ConversationState
from api.services.supermarket.db import OrderDatabase, OrderRecord
from api.services.supermarket.sms_handler import SMSProcessor
from api.services.supermarket.session_manager import SupermarketSessionManager
from api.services.supermarket.engine import SupermarketEngine
from api.services.tts.kokoro_engine import KokoroTTSEngine


@pytest.fixture
def temp_db(tmp_path):
    test_db_path = str(tmp_path / "test_freshmart.db")
    db = OrderDatabase(db_path=test_db_path)
    return db


@pytest.fixture
def sms_proc(temp_db):
    engine = SupermarketEngine()
    return SMSProcessor(db=temp_db, engine=engine)


def test_01_sqlite_order_creation_and_retrieval(temp_db):
    items = [
        GroceryItem(name="basmati rice", quantity=2.0, unit="kg"),
        GroceryItem(name="tomatoes", quantity=1.0, unit="kg")
    ]
    order = temp_db.save_order(
        session_id="session_test_01",
        caller_number="+919876543210",
        items=items,
        status="CONFIRMED"
    )

    assert order is not None
    assert order.order_id == "FM-1001"
    assert order.caller_number == "+919876543210"
    assert order.total_items_count == 2
    assert order.revision_number == 1
    assert "FM-1001" in order.sms_text
    assert "CONFIRMED" in order.sms_text

    # Retrieve by ID
    fetched = temp_db.get_order("FM-1001")
    assert fetched is not None
    assert fetched.order_id == "FM-1001"
    assert len(fetched.items) == 2


def test_02_sequential_order_id_generation(temp_db):
    id1 = temp_db.generate_order_id()
    assert id1 == "FM-1001"

    # Save order
    temp_db.save_order("sess_1", "+911111111111", [GroceryItem(name="milk", quantity=1.0, unit="litre")])

    id2 = temp_db.generate_order_id()
    assert id2 == "FM-1002"

    temp_db.save_order("sess_2", "+912222222222", [GroceryItem(name="bread", quantity=2.0, unit="packet")])

    id3 = temp_db.generate_order_id()
    assert id3 == "FM-1003"


def test_03_order_amendment_and_revision_increment(temp_db):
    initial_items = [
        GroceryItem(name="rice", quantity=2.0, unit="kg"),
        GroceryItem(name="milk", quantity=1.0, unit="litre")
    ]
    order = temp_db.save_order("sess_rev", "+919876543210", initial_items)
    assert order.revision_number == 1

    # Amend order
    updated_items = [
        GroceryItem(name="rice", quantity=2.0, unit="kg"),
        GroceryItem(name="milk", quantity=1.0, unit="litre"),
        GroceryItem(name="bread", quantity=2.0, unit="packet")
    ]
    rev2 = temp_db.update_order_items(
        order_id="FM-1001",
        new_items=updated_items,
        source="VOICE_CALL",
        change_notes="Added bread"
    )

    assert rev2 is not None
    assert rev2.revision_number == 2
    assert rev2.status == "MODIFIED"
    assert rev2.total_items_count == 3
    assert "Rev 2" in rev2.sms_text


def test_04_repeat_caller_recognition(temp_db):
    caller = "+919988776655"
    # No prior order
    assert temp_db.get_recent_order_for_caller(caller) is None

    # Place order
    temp_db.save_order("sess_caller", caller, [GroceryItem(name="sunflower oil", quantity=1.0, unit="litre")])

    recent = temp_db.get_recent_order_for_caller(caller)
    assert recent is not None
    assert recent.caller_number == caller
    assert recent.order_id == "FM-1001"


def test_05_sms_inbound_change_modification(temp_db, sms_proc):
    # Setup initial order
    items = [
        GroceryItem(name="rice", quantity=2.0, unit="kg"),
        GroceryItem(name="tomatoes", quantity=1.0, unit="kg")
    ]
    temp_db.save_order("sess_sms", "+919876543210", items)

    # Customer sends SMS modification
    sms_text = "CHANGE FM-1001: remove tomatoes, add 1L milk"
    result = sms_proc.process_inbound_sms("+919876543210", sms_text)

    assert result["success"] is True
    assert result["action"] == "ORDER_MODIFIED"
    assert result["revision_number"] == 2
    assert "FM-1001" in result["reply_sms"]
    assert "UPDATED (Rev 2)" in result["reply_sms"]

    # Verify updated DB state
    order = temp_db.get_order("FM-1001")
    item_names = [it["name"].lower() for it in order.items]
    assert "tomatoes" not in item_names
    assert "milk" in item_names
    assert "rice" in item_names


def test_06_sms_inbound_status_inquiry(temp_db, sms_proc):
    items = [GroceryItem(name="eggs", quantity=12.0, unit="egg")]
    temp_db.save_order("sess_status", "+919876543210", items)

    result = sms_proc.process_inbound_sms("+919876543210", "STATUS FM-1001")
    assert result["success"] is True
    assert result["action"] == "ORDER_STATUS"
    assert "FM-1001" in result["reply_sms"]
    assert "CONFIRMED" in result["reply_sms"]


def test_07_sms_inbound_cancellation(temp_db, sms_proc):
    items = [GroceryItem(name="apples", quantity=1.0, unit="kg")]
    temp_db.save_order("sess_cancel", "+919876543210", items)

    result = sms_proc.process_inbound_sms("+919876543210", "CANCEL FM-1001")
    assert result["success"] is True
    assert result["action"] == "ORDER_CANCELLED"
    assert "CANCELLED" in result["reply_sms"]

    order = temp_db.get_order("FM-1001")
    assert order.status == "CANCELLED"


def test_08_session_manager_deduplication_and_ack():
    sm = SupermarketSessionManager()
    session_id = "test_sess_ack"

    # Queue first speech
    cmd_id1 = sm.queue_command(session_id, "SPEAK", {"text": "Hello, how can I help you?"})
    assert cmd_id1 != "duplicate_suppressed"

    # Queue exact duplicate speech immediately
    cmd_id2 = sm.queue_command(session_id, "SPEAK", {"text": "Hello, how can I help you?"})
    assert cmd_id2 == "duplicate_suppressed"

    # Queue different speech
    cmd_id3 = sm.queue_command(session_id, "SPEAK", {"text": "I've noted 2 kilos of rice."})
    assert cmd_id3 != "duplicate_suppressed"

    # Pop commands
    popped = sm.pop_commands(session_id)
    assert len(popped) == 2
    assert popped[0]["command_id"] == cmd_id1
    assert popped[1]["command_id"] == cmd_id3

    # Ack command
    assert sm.ack_command(cmd_id1) is True


def test_09_kokoro_neural_tts_engine():
    tts = KokoroTTSEngine.get_instance()
    assert tts is not None

    phrase = "Your FreshMart order is ready for delivery."
    wav_bytes, sr = tts.synthesize(phrase, voice="af")

    assert len(wav_bytes) > 1000
    assert sr == 24000

    # Verify WAV header
    with io.BytesIO(wav_bytes) as buf:
        data, sample_rate = sf.read(buf)
        assert sample_rate == 24000
        assert len(data) > 0
        duration = len(data) / sample_rate
        assert 1.0 < duration < 5.0
