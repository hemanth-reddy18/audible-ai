"""
Audible AI — Comprehensive Supermarket Conversation Engine Test Suite
Tests 20+ real-world conversational variations including corrections, deletions,
clarifications, multilingual dialogues (English, Telugu, Hindi, code-switching),
cancellations, and automated farewell/hangup transitions.
"""

import pytest
from api.services.supermarket.models import (
    SupermarketOrder,
    ConversationState,
    ConfirmationStatus,
    GroceryItem
)
from api.services.supermarket.engine import SupermarketEngine


@pytest.fixture
def engine():
    return SupermarketEngine()


def test_01_standard_multi_item_order_english(engine):
    order = SupermarketOrder(session_id="test_01")
    text = "Hello, I want two kilos of rice, one litre of milk, six eggs, and one packet of bread."
    resp = engine.process_turn(order, text)

    assert len(order.items) == 4
    names = [i.name.lower() for i in order.items]
    assert "rice" in names
    assert "milk" in names
    assert "eggs" in names
    assert "bread" in names

    rice = next(i for i in order.items if i.name == "rice")
    assert rice.quantity == 2.0
    assert rice.unit == "kg"

    milk = next(i for i in order.items if i.name == "milk")
    assert milk.quantity == 1.0
    assert milk.unit == "litre"

    eggs = next(i for i in order.items if i.name == "eggs")
    assert eggs.quantity == 6.0

    bread = next(i for i in order.items if i.name == "bread")
    assert bread.quantity == 1.0
    assert bread.unit == "packet"

    assert order.state == ConversationState.AWAITING_CONFIRMATION
    assert "Is that correct?" in resp.ai_text


def test_02_explicit_confirmation_and_farewell(engine):
    order = SupermarketOrder(session_id="test_02", state=ConversationState.AWAITING_CONFIRMATION)
    order.items = [
        GroceryItem(name="rice", quantity=2.0, unit="kg"),
        GroceryItem(name="milk", quantity=1.0, unit="litre"),
        GroceryItem(name="eggs", quantity=6.0, unit="piece"),
        GroceryItem(name="bread", quantity=1.0, unit="packet")
    ]

    resp = engine.process_turn(order, "Yes, that's correct.")
    assert order.state == ConversationState.CONFIRMED
    assert order.confirmation_status == ConfirmationStatus.CONFIRMED
    assert resp.should_hangup is True
    assert "Perfect, sir! Your list is confirmed." in resp.ai_text
    assert "Thank you for calling FreshMart Supermarket." in resp.ai_text


def test_03_quantity_correction(engine):
    order = SupermarketOrder(session_id="test_03", state=ConversationState.AWAITING_CONFIRMATION)
    order.items = [
        GroceryItem(name="rice", quantity=2.0, unit="kg"),
        GroceryItem(name="milk", quantity=1.0, unit="litre")
    ]

    resp = engine.process_turn(order, "Actually, change the milk to two litres.")
    milk = next(i for i in order.items if i.name == "milk")
    assert milk.quantity == 2.0
    assert "2 litres of milk" in resp.ai_text


def test_04_item_removal(engine):
    order = SupermarketOrder(session_id="test_04", state=ConversationState.AWAITING_CONFIRMATION)
    order.items = [
        GroceryItem(name="rice", quantity=2.0, unit="kg"),
        GroceryItem(name="eggs", quantity=6.0, unit="piece")
    ]

    resp = engine.process_turn(order, "Wait, remove the eggs.")
    assert len(order.items) == 1
    assert order.items[0].name == "rice"
    assert "rice" in resp.ai_text
    assert "eggs" not in resp.ai_text


def test_05_add_more_items(engine):
    order = SupermarketOrder(session_id="test_05", state=ConversationState.AWAITING_CONFIRMATION)
    order.items = [GroceryItem(name="rice", quantity=2.0, unit="kg")]

    resp = engine.process_turn(order, "Also add two packets of butter.")
    assert len(order.items) == 2
    butter = next(i for i in order.items if i.name == "butter")
    assert butter.quantity == 2.0
    assert butter.unit == "packet"


def test_06_telugu_conversation(engine):
    order = SupermarketOrder(session_id="test_06")
    resp = engine.process_turn(order, "Anna, two kilos biyyam kavali, and milk rendu packets add cheyyandi.")
    assert len(order.items) >= 2
    assert order.language == "te"
    assert "sir" in resp.ai_text.lower()


def test_07_telugu_confirmation(engine):
    order = SupermarketOrder(session_id="test_07", state=ConversationState.AWAITING_CONFIRMATION, language="te")
    order.items = [GroceryItem(name="rice", quantity=2.0, unit="kg")]

    resp = engine.process_turn(order, "Avunu, sari.")
    assert order.state == ConversationState.CONFIRMED
    assert resp.should_hangup is True
    assert "dhanyavadamulu" in resp.ai_text.lower()


def test_08_hindi_conversation(engine):
    order = SupermarketOrder(session_id="test_08")
    resp = engine.process_turn(order, "Bhaiya, do kilo chawal aur ek litre doodh chahiye.")
    assert len(order.items) >= 2
    assert order.language == "hi"
    assert "sir" in resp.ai_text.lower()


def test_09_hindi_confirmation(engine):
    order = SupermarketOrder(session_id="test_09", state=ConversationState.AWAITING_CONFIRMATION, language="hi")
    order.items = [GroceryItem(name="rice", quantity=2.0, unit="kg")]

    resp = engine.process_turn(order, "Haan, theek hai.")
    assert order.state == ConversationState.CONFIRMED
    assert resp.should_hangup is True
    assert "dhanyawad" in resp.ai_text.lower()


def test_10_mixed_code_switching(engine):
    order = SupermarketOrder(session_id="test_10")
    resp = engine.process_turn(order, "Two kilos rice and paalu rendu packets ivvandi.")
    assert len(order.items) >= 2
    names = [i.name.lower() for i in order.items]
    assert "rice" in names
    assert "milk" in names


def test_11_fractional_quantities(engine):
    order = SupermarketOrder(session_id="test_11")
    resp = engine.process_turn(order, "I need half kilo sugar and one kilo salt.")
    sugar = next(i for i in order.items if i.name == "sugar")
    assert sugar.quantity == 0.5
    salt = next(i for i in order.items if i.name == "salt")
    assert salt.quantity == 1.0


def test_12_store_hours_inquiry(engine):
    order = SupermarketOrder(session_id="test_12")
    resp = engine.process_turn(order, "What time do you close today?")
    assert "10 PM" in resp.ai_text
    assert order.state == ConversationState.IDLE or order.state == ConversationState.ANSWERED


def test_13_delivery_inquiry(engine):
    order = SupermarketOrder(session_id="test_13")
    resp = engine.process_turn(order, "Can you deliver groceries to my apartment?")
    assert "home delivery" in resp.ai_text.lower()


def test_14_pricing_inquiry(engine):
    order = SupermarketOrder(session_id="test_14")
    resp = engine.process_turn(order, "How much is the price of sunflower oil?")
    assert "billing" in resp.ai_text.lower() or "rates" in resp.ai_text.lower()


def test_15_hesitation_and_pause(engine):
    order = SupermarketOrder(session_id="test_15")
    resp = engine.process_turn(order, "Wait, let me think for a second...")
    assert "take your time" in resp.ai_text.lower()


def test_16_order_cancellation(engine):
    order = SupermarketOrder(session_id="test_16")
    order.items = [GroceryItem(name="rice", quantity=2.0, unit="kg")]
    resp = engine.process_turn(order, "Cancel the order, I will call back later.")
    assert order.state == ConversationState.FAREWELL
    assert order.confirmation_status == ConfirmationStatus.CANCELLED
    assert resp.should_hangup is True


def test_17_single_item_order(engine):
    order = SupermarketOrder(session_id="test_17")
    resp = engine.process_turn(order, "Just one packet of bread, that's it.")
    assert len(order.items) == 1
    assert order.items[0].name == "bread"
    assert order.state == ConversationState.AWAITING_CONFIRMATION


def test_18_negative_confirmation_followed_by_update(engine):
    order = SupermarketOrder(session_id="test_18", state=ConversationState.AWAITING_CONFIRMATION)
    order.items = [GroceryItem(name="rice", quantity=2.0, unit="kg")]

    resp = engine.process_turn(order, "No, change the rice to three kilos.")
    rice = next(i for i in order.items if i.name == "rice")
    assert rice.quantity == 3.0
    assert order.state == ConversationState.AWAITING_CONFIRMATION


def test_19_initial_greeting_multilingual(engine):
    en_greeting = engine.get_initial_greeting("en")
    assert "FreshMart Supermarket" in en_greeting
    te_greeting = engine.get_initial_greeting("te")
    assert "Namaskaram" in te_greeting
    hi_greeting = engine.get_initial_greeting("hi")
    assert "Namaste" in hi_greeting


def test_20_full_dialogue_lifecycle(engine):
    # Complete end-to-end multi-turn interaction
    order = SupermarketOrder(session_id="test_lifecycle")

    # Turn 1: Caller places initial order
    r1 = engine.process_turn(order, "Hello, I want two kilos of rice, one litre of milk, six eggs, and one packet of bread.")
    assert len(order.items) == 4
    assert order.state == ConversationState.AWAITING_CONFIRMATION

    # Turn 2: Caller makes a correction
    r2 = engine.process_turn(order, "Actually, change the milk to two litres.")
    milk = next(i for i in order.items if i.name == "milk")
    assert milk.quantity == 2.0
    assert len(order.items) == 4

    # Turn 3: Caller confirms
    r3 = engine.process_turn(order, "Yes, that's correct.")
    assert order.state == ConversationState.CONFIRMED
    assert r3.should_hangup is True
    assert "Perfect, sir! Your list is confirmed." in r3.ai_text


def test_21_dozen_and_bottle_units(engine):
    order = SupermarketOrder(session_id="test_21")
    resp = engine.process_turn(order, "Give me one dozen eggs and two bottles of oil.")
    eggs = next(i for i in order.items if i.name == "eggs")
    assert eggs.quantity == 12.0 or eggs.unit == "dozen"
    oil = next(i for i in order.items if i.name == "oil")
    assert oil.quantity == 2.0
    assert oil.unit == "bottle"
