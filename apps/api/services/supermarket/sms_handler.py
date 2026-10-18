"""
Audible AI — FreshMart Two-Way SMS Processor
Parses customer SMS replies (e.g. 'CHANGE FM-1042: add 1L milk, remove onions', 'CANCEL FM-1042'),
updates the persistent SQLite order database, generates revised order summaries,
and returns automated confirmation SMS replies.
"""

import re
from typing import Dict, Any, Optional, List
from loguru import logger

from .db import OrderDatabase, OrderRecord
from .models import GroceryItem
from .engine import SupermarketEngine


class SMSProcessor:
    def __init__(self, db: Optional[OrderDatabase] = None, engine: Optional[SupermarketEngine] = None):
        self.db = db or OrderDatabase.get_instance()
        self.engine = engine or SupermarketEngine()

    def process_inbound_sms(self, sender_number: str, text: str) -> Dict[str, Any]:
        """
        Process an inbound SMS message from a customer.
        Returns a dict with action taken and response SMS text to send back.
        """
        raw_text = text.strip()
        logger.info(f"[SMS Processor] Inbound from {sender_number}: '{raw_text}'")

        # 1. Log inbound message
        self.db.log_sms(
            direction="INBOUND",
            phone_number=sender_number,
            message_text=raw_text,
            status="RECEIVED"
        )

        # 2. Extract potential Order ID (format: FM-XXXX or FMXXXX)
        order_id_match = re.search(r'\b(FM[-_]?\d{4,})\b', raw_text, re.IGNORECASE)
        order_id = None
        if order_id_match:
            raw_id = order_id_match.group(1).upper()
            if "-" not in raw_id:
                raw_id = f"FM-{raw_id[2:]}"
            order_id = raw_id

        # If no order ID mentioned, look up the caller's most recent order
        if not order_id:
            recent_order = self.db.get_recent_order_for_caller(sender_number)
            if recent_order:
                order_id = recent_order.order_id

        if not order_id:
            reply_text = (
                "FreshMart: We could not find an active order for your number. "
                "To place a new grocery order, please call us or include your Order ID (e.g. CHANGE FM-1001)."
            )
            self._log_outbound(sender_number, reply_text, "FAILED_NO_ORDER")
            return {
                "success": False,
                "action": "UNKNOWN_ORDER",
                "reply_sms": reply_text
            }

        order = self.db.get_order(order_id)
        if not order:
            reply_text = f"FreshMart: Order {order_id} was not found. Please verify your order number and try again."
            self._log_outbound(sender_number, reply_text, "FAILED_NOT_FOUND", order_id)
            return {
                "success": False,
                "action": "ORDER_NOT_FOUND",
                "order_id": order_id,
                "reply_sms": reply_text
            }

        # 3. Check for CANCEL command
        if re.search(r'\b(CANCEL|DELETE|STOP)\b', raw_text, re.IGNORECASE):
            self.db.cancel_order(order_id, source="SMS_INBOUND")
            reply_text = f"FreshMart: Your order {order_id} has been CANCELLED as requested. Thank you."
            self._log_outbound(sender_number, reply_text, "SENT", order_id)
            return {
                "success": True,
                "action": "ORDER_CANCELLED",
                "order_id": order_id,
                "reply_sms": reply_text
            }

        # 4. Check for STATUS command
        if re.search(r'\b(STATUS|CHECK|DETAILS)\b', raw_text, re.IGNORECASE):
            reply_text = (
                f"FreshMart Order {order_id} (Rev {order.revision_number}): Status is {order.status}. "
                f"Items: {order.summary_text}."
            )
            self._log_outbound(sender_number, reply_text, "SENT", order_id)
            return {
                "success": True,
                "action": "ORDER_STATUS",
                "order_id": order_id,
                "reply_sms": reply_text
            }

        # 5. Process CHANGE / Modification
        # Strip out command prefix and order ID to leave the change description
        change_text = re.sub(r'^(CHANGE|MODIFY|UPDATE)?\s*' + re.escape(order_id) + r'[:\s-]*', '', raw_text, flags=re.IGNORECASE).strip()
        if not change_text:
            change_text = raw_text

        # Reconstruct existing items as GroceryItem models
        existing_items = [
            GroceryItem(
                name=it.get("name", "item"),
                quantity=float(it.get("quantity", 1)),
                unit=it.get("unit", "piece"),
                notes=it.get("notes")
            )
            for it in order.items
        ]

        # Use our NLP extraction logic to parse adds and removals
        updated_items = self._apply_modifications(existing_items, change_text)

        # Update order in DB
        amended = self.db.update_order_items(
            order_id=order_id,
            new_items=updated_items,
            source="SMS_INBOUND",
            change_notes=f"Customer SMS: '{raw_text}'"
        )

        reply_text = self.db.format_sms_update(order_id, updated_items, amended.revision_number)
        self._log_outbound(sender_number, reply_text, "SENT", order_id)

        return {
            "success": True,
            "action": "ORDER_MODIFIED",
            "order_id": order_id,
            "revision_number": amended.revision_number,
            "new_summary": amended.summary_text,
            "reply_sms": reply_text
        }

    def _apply_modifications(self, current_items: List[GroceryItem], modification_text: str) -> List[GroceryItem]:
        """Apply added/removed items to the current items list."""
        text_lower = modification_text.lower()
        
        # Check removals: "remove onions", "cancel milk", "delete eggs", "without tomatoes"
        removal_patterns = [
            r'(?:remove|cancel|delete|drop|no|without)\s+([a-zA-Z\s]+?)(?:,|and|$)',
        ]
        items_to_remove = []
        for pat in removal_patterns:
            matches = re.finditer(pat, text_lower)
            for m in matches:
                item_name = m.group(1).strip()
                # clean words
                for w in item_name.split():
                    if len(w) > 2:
                        items_to_remove.append(w)

        # Filter out removed items
        filtered = []
        for item in current_items:
            should_remove = False
            for rm in items_to_remove:
                if rm in item.name.lower():
                    should_remove = True
                    break
            if not should_remove:
                filtered.append(item)

        # Strip removal clauses before extracting added items
        clean_add_text = re.sub(r'(?:remove|cancel|delete|drop|no|without)\s+[a-zA-Z\s]+?(?:,|$)', '', text_lower)
        added_items = self.engine.extract_items_from_text(clean_add_text)
        # Ensure no removed item is inadvertently added back
        added_items = [
            a for a in added_items 
            if not any(rm in a.name.lower() or a.name.lower() in rm for rm in items_to_remove)
        ]
        
        # Merge added items
        for added in added_items:
            # Check if item already exists
            match_found = False
            for existing in filtered:
                if added.name.lower() in existing.name.lower() or existing.name.lower() in added.name.lower():
                    # Update quantity
                    existing.quantity += added.quantity
                    match_found = True
                    break
            if not match_found:
                filtered.append(added)

        return filtered

    def _log_outbound(self, phone_number: str, message_text: str, status: str, order_id: Optional[str] = None):
        self.db.log_sms(
            direction="OUTBOUND",
            phone_number=phone_number,
            order_id=order_id,
            message_text=message_text,
            status=status
        )
