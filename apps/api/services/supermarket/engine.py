"""
Audible AI — FreshMart Supermarket Conversational Engine
Implements dynamic conversational understanding, multilingual support (EN, TE, HI),
structured order extraction, state tracking, and farewell/hangup coordination.
"""

import re
import json
import urllib.request
from typing import List, Tuple, Optional, Dict, Any
from loguru import logger

from api.services.supermarket.models import (
    ConversationState,
    ConfirmationStatus,
    GroceryItem,
    SupermarketOrder,
    ReceptionistResponse
)

# Multilingual number mappings
NUMBER_WORDS = {
    # English
    "half": 0.5, "one": 1, "a": 1, "an": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "dozen": 12, "half dozen": 6,
    # Telugu
    "okka": 1, "okati": 1, "rendu": 2, "moodu": 3, "naalugu": 4, "aidu": 5, "aaru": 6,
    "yeedu": 7, "enimidi": 8, "thommidi": 9, "padi": 10, "sagamu": 0.5, "ara": 0.5,
    # Hindi
    "aadha": 0.5, "ek": 1, "do": 2, "teen": 3, "chaar": 4, "paanch": 5, "chhe": 6,
    "saat": 7, "aath": 8, "nau": 9, "das": 10
}

UNIT_WORDS = {
    # Weight
    "kg": "kg", "kgs": "kg", "kilo": "kg", "kilos": "kg", "kilogram": "kg", "kilograms": "kg",
    "gram": "gram", "grams": "gram", "gm": "gram", "gms": "gram",
    # Volume
    "litre": "litre", "litres": "litre", "liter": "litre", "liters": "litre", "l": "litre",
    "ml": "ml", "packet": "packet", "packets": "packet", "pkt": "packet", "pkts": "packet",
    "bag": "packet", "bags": "packet", "bottle": "bottle", "bottles": "bottle",
    # Count
    "dozen": "dozen", "piece": "piece", "pieces": "piece", "pcs": "piece",
    "egg": "egg", "eggs": "egg"
}

KNOWN_PRODUCTS = [
    "rice", "milk", "egg", "eggs", "bread", "sugar", "salt", "tea", "coffee",
    "butter", "cheese", "oil", "sunflower oil", "dal", "toor dal", "onion", "onions",
    "potato", "potatoes", "tomato", "tomatoes", "atta", "wheat flour", "flour",
    "soap", "shampoo", "toothpaste", "apples", "apple", "banana", "bananas"
]

TELUGU_PRODUCT_MAP = {
    "biyyam": "rice", "paalu": "milk", "guddu": "eggs", "gudlu": "eggs", "kodi gudlu": "eggs",
    "rotte": "bread", "panchadara": "sugar", "uppu": "salt", "nune": "oil", "pappu": "toor dal",
    "ullipayalu": "onions", "bangaladumpalu": "potatoes", "tamatalu": "tomatoes"
}

HINDI_PRODUCT_MAP = {
    "chawal": "rice", "doodh": "milk", "ande": "eggs", "anda": "eggs", "double roti": "bread",
    "cheeni": "sugar", "namak": "salt", "tel": "oil", "daal": "toor dal", "pyaaz": "onions",
    "aaloo": "potatoes", "tamatar": "tomatoes"
}


class SupermarketEngine:
    def __init__(self, ollama_url: str = "http://127.0.0.1:11434"):
        self.ollama_url = ollama_url
        self.model_name = "llama3.2:1b"

    def get_initial_greeting(self, language: str = "en") -> str:
        if language == "te":
            return "Namaskaram! FreshMart Supermarket ki swagatham. Nenu meeku ela sahayapadagalanu, sir?"
        elif language == "hi":
            return "Namaste! FreshMart Supermarket mein aapka swagat hai. Main aapki kya madad kar sakta hoon, sir?"
        return "Hello! Thank you for calling FreshMart Supermarket. How may I help you today, sir?"

    def detect_language(self, text: str) -> str:
        text_lower = text.lower()
        te_keywords = ["kavali", "rendu", "moodu", "cheyyandi", "biyyam", "paalu", "gudlu", "avunu", "kadhu", "cheppandi", "namaskaram", "anna"]
        hi_keywords = ["chahiye", "karo", "kijiye", "bhaiya", "chawal", "doodh", "namaste", "haan", "nahi", "theek", "batao"]

        for kw in te_keywords:
            if re.search(r'\b' + kw + r'\b', text_lower):
                return "te"
        for kw in hi_keywords:
            if re.search(r'\b' + kw + r'\b', text_lower):
                return "hi"
        return "en"

    def parse_number_and_unit(self, phrase: str) -> Tuple[Optional[float], Optional[str]]:
        phrase = phrase.lower().strip()
        # Direct numeric match
        num_match = re.search(r'(\d+(?:\.\d+)?)', phrase)
        num = float(num_match.group(1)) if num_match else None

        # Word numeric match
        if num is None:
            for word, val in NUMBER_WORDS.items():
                if re.search(r'\b' + word + r'\b', phrase):
                    num = val
                    break

        unit = None
        for word, u_std in UNIT_WORDS.items():
            if re.search(r'\b' + word + r'\b', phrase):
                unit = u_std
                break

        return num, unit

    def extract_items_from_text(self, text: str) -> List[GroceryItem]:
        """Extract one or more grocery items from natural multi-item utterance."""
        items: List[GroceryItem] = []
        text_lower = text.lower()

        # Check for Telugu / Hindi translations first
        normalized = text_lower
        for te_word, std_name in TELUGU_PRODUCT_MAP.items():
            normalized = re.sub(r'\b' + te_word + r'\b', std_name, normalized)
        for hi_word, std_name in HINDI_PRODUCT_MAP.items():
            normalized = re.sub(r'\b' + hi_word + r'\b', std_name, normalized)

        # Split on commas, 'and', 'also', 'mariyu', 'aur', 'plus'
        clauses = re.split(r'[,;]|\band\b|\balso\b|\bmariyu\b|\baur\b|\bplus\b', normalized)

        for clause in clauses:
            clause = clause.strip()
            if not clause:
                continue

            for prod in KNOWN_PRODUCTS:
                # Match product name
                pattern = r'\b' + prod + r'\b'
                if re.search(pattern, clause):
                    qty, unit = self.parse_number_and_unit(clause)
                    if qty is None:
                        qty = 1.0
                    if unit is None:
                        if prod in ["egg", "eggs"]:
                            unit = "piece"
                        elif prod in ["milk", "oil", "sunflower oil"]:
                            unit = "litre"
                        elif prod in ["bread", "butter"]:
                            unit = "packet"
                        elif prod in ["rice", "sugar", "salt", "atta", "dal", "toor dal", "onions", "potatoes"]:
                            unit = "kg"
                        else:
                            unit = "piece"

                    std_name = "eggs" if prod in ["egg", "eggs"] else prod
                    items.append(GroceryItem(name=std_name, quantity=qty, unit=unit, original_text=clause))
                    break

        return items

    def is_confirmation_intent(self, text: str) -> Optional[bool]:
        """Determine if caller is confirming or rejecting."""
        text_clean = text.lower().strip()
        positive_patterns = [
            r'\byes\b', r'\byeah\b', r'\byep\b', r'\bcorrect\b', r'\bthat\'?s correct\b',
            r'\bthat\'?s right\b', r'\bconfirm\b', r'\bconfirmed\b', r'\bperfect\b',
            r'\bavunu\b', r'\bsari\b', r'\bhann?\b', r'\btheek hai\b', r'\bsahi hai\b',
            r'\bproceed\b', r'\bok\b', r'\bokay\b', r'\ball good\b'
        ]
        negative_patterns = [
            r'\bno\b', r'\bnope\b', r'\bnot correct\b', r'\bwrong\b', r'\bwait\b',
            r'\bkadhu\b', r'\bledhu\b', r'\bnahi\b', r'\bgalat\b', r'\bchange\b',
            r'\bactually\b', r'\bstop\b'
        ]

        # Prioritize correction / negative
        for pat in negative_patterns:
            if re.search(pat, text_clean):
                return False

        for pat in positive_patterns:
            if re.search(pat, text_clean):
                return True

        return None

    def process_turn(self, order: SupermarketOrder, caller_speech: str) -> ReceptionistResponse:
        """Core state machine and conversational turn processor."""
        caller_speech = caller_speech.strip()
        lang = self.detect_language(caller_speech)
        order.language = lang
        order.transcript.append({"role": "caller", "text": caller_speech})

        # Check for order cancellation
        if re.search(r'\b(cancel|vaddu|nahi chahiye|call back later|cut the call)\b', caller_speech.lower()):
            order.state = ConversationState.FAREWELL
            order.confirmation_status = ConfirmationStatus.CANCELLED
            if lang == "te":
                resp_text = "Sare sir, mee order cancel cheyabadindi. Malli call cheyandi. Have a good day!"
            elif lang == "hi":
                resp_text = "Theek hai sir, aapka order cancel kar diya gaya hai. Shubh din!"
            else:
                resp_text = "Certainly, sir. Your order request has been cancelled. Thank you for calling FreshMart. Have a wonderful day!"
            order.transcript.append({"role": "assistant", "text": resp_text})
            return ReceptionistResponse(
                session_id=order.session_id,
                state=ConversationState.FAREWELL,
                ai_text=resp_text,
                order=order,
                should_hangup=True,
                language_detected=lang
            )

        # 1. State: AWAITING_CONFIRMATION
        if order.state == ConversationState.AWAITING_CONFIRMATION:
            confirm = self.is_confirmation_intent(caller_speech)
            if confirm is True:
                order.state = ConversationState.CONFIRMED
                order.confirmation_status = ConfirmationStatus.CONFIRMED
                if lang == "te":
                    farewell = "Chaala santhosham sir! Mee list confirm ayindi. FreshMart Supermarket ki call chesinanduku dhanyavadamulu. Have a wonderful day!"
                elif lang == "hi":
                    farewell = "Bahut badiya sir! Aapki list confirm ho gayi hai. FreshMart Supermarket ko call karne ke liye dhanyawad. Aapka din shubh ho!"
                else:
                    farewell = "Perfect, sir! Your list is confirmed. Thank you for calling FreshMart Supermarket. Have a wonderful day!"
                
                order.transcript.append({"role": "assistant", "text": farewell})
                return ReceptionistResponse(
                    session_id=order.session_id,
                    state=ConversationState.CONFIRMED,
                    ai_text=farewell,
                    order=order,
                    should_hangup=True,
                    language_detected=lang
                )
            elif confirm is False:
                # Caller has a correction or removal
                removals = self._detect_removal(caller_speech)
                if removals:
                    for r in removals:
                        order.items = [i for i in order.items if i.name.lower() != r.lower()]

                extracted = [i for i in self.extract_items_from_text(caller_speech) if i.name.lower() not in removals]
                if extracted:
                    self._apply_item_updates(order, extracted)

                summary = order.get_order_summary(lang)
                if lang == "te":
                    resp_text = f"Mee list update chesanu, sir. {summary}"
                elif lang == "hi":
                    resp_text = f"Maine list update kar di hai, sir. {summary}"
                else:
                    resp_text = f"Certainly, sir. I've updated your order: {summary}"
                order.transcript.append({"role": "assistant", "text": resp_text})
                return ReceptionistResponse(
                    session_id=order.session_id,
                    state=ConversationState.AWAITING_CONFIRMATION,
                    ai_text=resp_text,
                    order=order,
                    should_hangup=False,
                    language_detected=lang
                )

        # 2. Handle Q&A or Inquiries first if asking about price, hours, delivery
        lower_speech = caller_speech.lower()
        if re.search(r'\b(price|rate|cost|how much|dhara|kithna)\b', lower_speech) and not re.search(r'\b(want|give|need|add|kavali|chahiye)\b', lower_speech):
            resp_text = "Prices are determined at billing based on today's best daily store rates, sir. What items can I note down for you?"
            order.transcript.append({"role": "assistant", "text": resp_text})
            return ReceptionistResponse(
                session_id=order.session_id,
                state=order.state,
                ai_text=resp_text,
                order=order,
                should_hangup=False,
                language_detected=lang
            )
        elif re.search(r'\b(hour|time|open|close)\b', lower_speech) and not re.search(r'\b(want|give|need|add)\b', lower_speech):
            resp_text = "FreshMart is open daily from 7 AM to 10 PM, sir. How may I assist with your grocery list?"
            order.transcript.append({"role": "assistant", "text": resp_text})
            return ReceptionistResponse(
                session_id=order.session_id,
                state=order.state,
                ai_text=resp_text,
                order=order,
                should_hangup=False,
                language_detected=lang
            )
        elif re.search(r'\b(deliver|delivery)\b', lower_speech) and not re.search(r'\b(want|give|need|add)\b', lower_speech):
            resp_text = "Yes sir, home delivery is available for all confirmed grocery orders. Which items would you like to add?"
            order.transcript.append({"role": "assistant", "text": resp_text})
            return ReceptionistResponse(
                session_id=order.session_id,
                state=order.state,
                ai_text=resp_text,
                order=order,
                should_hangup=False,
                language_detected=lang
            )

        # 3. General conversation / item addition / corrections
        removals = self._detect_removal(caller_speech)
        if removals:
            for r in removals:
                order.items = [i for i in order.items if i.name.lower() != r.lower()]

        extracted_items = [i for i in self.extract_items_from_text(caller_speech) if i.name.lower() not in removals]

        if extracted_items:
            self._apply_item_updates(order, extracted_items)
            order.state = ConversationState.COLLECTING_ITEMS

            # Check if caller signaled completion in same sentence ("and that's all", "that is it")
            if re.search(r'\b(that\'?s all|that is all|that\'?s it|done|chalu|intha varaku)\b', caller_speech.lower()):
                order.state = ConversationState.AWAITING_CONFIRMATION
                summary = order.get_order_summary(lang)
                if lang == "te":
                    resp_text = f"Tappakunda sir. {summary}"
                elif lang == "hi":
                    resp_text = f"Bilkul sir. {summary}"
                else:
                    resp_text = f"Certainly, sir. {summary}"
            else:
                # Ask if anything else or confirm
                order.state = ConversationState.AWAITING_CONFIRMATION
                summary = order.get_order_summary(lang)
                if lang == "te":
                    resp_text = f"Tappakunda sir. {summary}"
                elif lang == "hi":
                    resp_text = f"Bilkul sir. {summary}"
                else:
                    resp_text = f"Certainly, sir. {summary}"

            order.transcript.append({"role": "assistant", "text": resp_text})
            return ReceptionistResponse(
                session_id=order.session_id,
                state=order.state,
                ai_text=resp_text,
                order=order,
                should_hangup=False,
                language_detected=lang
            )

        # 3. Handle Q&A or Inquiries (prices, inventory, store hours)
        lower_speech = caller_speech.lower()
        if "price" in lower_speech or "rate" in lower_speech or "cost" in lower_speech or "dhara" in lower_speech or "kithna" in lower_speech:
            resp_text = "Prices are determined at billing based on today's best daily store rates, sir. What items can I note down for you?"
        elif "hour" in lower_speech or "time" in lower_speech or "open" in lower_speech or "close" in lower_speech:
            resp_text = "FreshMart is open daily from 7 AM to 10 PM, sir. How may I assist with your grocery list?"
        elif "deliver" in lower_speech or "delivery" in lower_speech:
            resp_text = "Yes sir, home delivery is available for all confirmed grocery orders. Which items would you like to add?"
        elif "organic" in lower_speech:
            resp_text = "We stock select organic staples, sir. Brand availability can be confirmed upon packing. How many kilos would you like to add?"
        elif re.search(r'\b(wait|think|one second|hold on|aagandi|ruko)\b', lower_speech):
            resp_text = "Take your time, sir. Please let me know whenever you're ready."
        else:
            # Clarification prompt
            if order.items:
                summary = order.get_order_summary(lang)
                resp_text = f"I have your list noted as: {summary}"
                order.state = ConversationState.AWAITING_CONFIRMATION
            else:
                resp_text = "I'm ready to note your grocery items, sir. Please tell me what you need, such as rice, milk, or bread."

        order.transcript.append({"role": "assistant", "text": resp_text})
        return ReceptionistResponse(
            session_id=order.session_id,
            state=order.state,
            ai_text=resp_text,
            order=order,
            should_hangup=False,
            language_detected=lang
        )

    def _apply_item_updates(self, order: SupermarketOrder, new_items: List[GroceryItem]):
        """Update existing items with new quantity or append new items."""
        for new_item in new_items:
            existing = next((i for i in order.items if i.name.lower() == new_item.name.lower()), None)
            if existing:
                # Update quantity and unit
                existing.quantity = new_item.quantity
                existing.unit = new_item.unit
                existing.notes = "Updated quantity"
            else:
                order.items.append(new_item)

    def _detect_removal(self, text: str) -> List[str]:
        removals = []
        text_lower = text.lower()
        if re.search(r'\b(remove|delete|cancel|no need|vaddu|hatao|mat lo)\b', text_lower):
            for prod in KNOWN_PRODUCTS:
                if re.search(r'\b' + prod + r'\b', text_lower):
                    removals.append(prod)
        return removals
