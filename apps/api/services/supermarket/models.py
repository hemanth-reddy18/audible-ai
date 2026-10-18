"""
Audible AI — FreshMart Supermarket Receptionist
Typed Data Models & State Machine Definition
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ConversationState(str, Enum):
    IDLE = "IDLE"
    INCOMING_CALL = "INCOMING_CALL"
    ANSWERED = "ANSWERED"
    GREETING = "GREETING"
    LISTENING = "LISTENING"
    COLLECTING_ITEMS = "COLLECTING_ITEMS"
    ORDER_REVIEW = "ORDER_REVIEW"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    FAREWELL = "FAREWELL"
    HANGUP = "HANGUP"
    COMPLETED = "COMPLETED"


class ConfirmationStatus(str, Enum):
    PENDING = "PENDING"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class GroceryItem(BaseModel):
    name: str
    quantity: float
    unit: str = "piece"  # kg, litre, packet, dozen, piece, bottle, gram
    notes: Optional[str] = None
    original_text: Optional[str] = None

    def display_str(self) -> str:
        qty_str = f"{int(self.quantity)}" if self.quantity.is_integer() else f"{self.quantity}"
        # Pluralize units nicely
        u = self.unit.lower()
        if self.quantity > 1:
            if u == "kg":
                unit_display = "kilos"
            elif u == "litre":
                unit_display = "litres"
            elif u == "packet":
                unit_display = "packets"
            elif u == "dozen":
                unit_display = "dozen"
            elif u in ["piece", "egg"]:
                unit_display = "pieces" if u == "piece" else "eggs"
            else:
                unit_display = f"{u}s"
        else:
            if u == "kg":
                unit_display = "kilo"
            elif u == "litre":
                unit_display = "litre"
            elif u == "packet":
                unit_display = "packet"
            else:
                unit_display = u

        if self.name.lower() in ["egg", "eggs"] and u in ["piece", "egg", ""]:
            return f"{qty_str} eggs" if self.quantity != 1 else "1 egg"
            
        return f"{qty_str} {unit_display} of {self.name}"


class SupermarketOrder(BaseModel):
    session_id: str
    caller_id: str = "Unknown"
    state: ConversationState = ConversationState.IDLE
    confirmation_status: ConfirmationStatus = ConfirmationStatus.PENDING
    items: List[GroceryItem] = Field(default_factory=list)
    language: str = "en"  # "en", "te", "hi"
    transcript: List[Dict[str, str]] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    def get_order_summary(self, lang: str = "en") -> str:
        if not self.items:
            if lang == "te":
                return "Meeru inka eemee items add cheyaledu, sir."
            elif lang == "hi":
                return "Aapne abhi koi item nahi bataya hai, sir."
            return "No items have been added to your list yet, sir."

        item_strings = [item.display_str() for item in self.items]
        if len(item_strings) == 1:
            joined = item_strings[0]
        elif len(item_strings) == 2:
            joined = f"{item_strings[0]} and {item_strings[1]}"
        else:
            joined = ", ".join(item_strings[:-1]) + f", and {item_strings[-1]}"

        if lang == "te":
            return f"Nenu {joined} note cheskunnanu. Idi saripothunda, sir?"
        elif lang == "hi":
            return f"Maine {joined} note kar liya hai. Kya yeh sahi hai, sir?"
        return f"I've noted {joined}. Is that correct?"


class ReceptionistResponse(BaseModel):
    session_id: str
    state: ConversationState
    ai_text: str
    order: SupermarketOrder
    should_hangup: bool = False
    language_detected: str = "en"
