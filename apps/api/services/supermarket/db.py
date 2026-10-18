"""
Audible AI — FreshMart Supermarket Persistent Order Management
Thread-safe SQLite Database Layer for Production Order Tracking,
Revision History, and Two-Way SMS Integration.
"""

import os
import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from loguru import logger

from .models import GroceryItem, ConfirmationStatus

DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data"))
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "freshmart_orders.db")


class OrderRecord(BaseModel):
    order_id: str
    session_id: str
    caller_number: str
    status: str = "CONFIRMED"
    items: List[Dict[str, Any]] = Field(default_factory=list)
    total_items_count: int = 0
    summary_text: str = ""
    revision_number: int = 1
    sms_status: str = "NOT_SENT"
    sms_text: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class OrderDatabase:
    _instance = None

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    @classmethod
    def get_instance(cls) -> "OrderDatabase":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize database schema with orders and revisions tables."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Orders table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT UNIQUE NOT NULL,
                    session_id TEXT NOT NULL,
                    caller_number TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'CONFIRMED',
                    items_json TEXT NOT NULL,
                    total_items_count INTEGER NOT NULL DEFAULT 0,
                    summary_text TEXT NOT NULL,
                    revision_number INTEGER NOT NULL DEFAULT 1,
                    sms_status TEXT NOT NULL DEFAULT 'NOT_SENT',
                    sms_text TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Revision history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS order_revisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    revision_number INTEGER NOT NULL,
                    modification_source TEXT NOT NULL, -- 'VOICE_CALL', 'SMS_INBOUND', 'API'
                    previous_items_json TEXT,
                    updated_items_json TEXT NOT NULL,
                    change_notes TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES orders(order_id)
                )
            """)

            # SMS Inbound / Outbound log
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sms_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    direction TEXT NOT NULL, -- 'OUTBOUND', 'INBOUND'
                    phone_number TEXT NOT NULL,
                    order_id TEXT,
                    message_text TEXT NOT NULL,
                    status TEXT NOT NULL, -- 'QUEUED', 'SENT', 'RECEIVED', 'PROCESSED', 'FAILED'
                    timestamp TEXT NOT NULL
                )
            """)

            # Indexing for fast lookups
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_caller ON orders(caller_number)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders(order_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_revisions_order_id ON order_revisions(order_id)")
            conn.commit()
            logger.info(f"FreshMart Order Database initialized at: {self.db_path}")

    def generate_order_id(self) -> str:
        """Generate next formatted order ID like FM-1001, FM-1002."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(id) FROM orders")
            row = cursor.fetchone()
            next_num = 1001 if (row is None or row[0] is None) else (1001 + row[0])
            return f"FM-{next_num}"

    def save_order(
        self,
        session_id: str,
        caller_number: str,
        items: List[GroceryItem],
        status: str = "CONFIRMED",
        summary_text: Optional[str] = None
    ) -> OrderRecord:
        """Save a confirmed order to the database."""
        order_id = self.generate_order_id()
        items_dict = [item.model_dump() for item in items]
        items_json = json.dumps(items_dict)
        now = datetime.utcnow().isoformat()
        
        if not summary_text:
            item_names = [f"{item.quantity} {item.unit} {item.name}" for item in items]
            summary_text = ", ".join(item_names)

        # Build standard SMS confirmation text
        sms_text = self.format_sms_confirmation(order_id, items)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO orders (
                    order_id, session_id, caller_number, status, items_json,
                    total_items_count, summary_text, revision_number, sms_status,
                    sms_text, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 'QUEUED', ?, ?, ?)
            """, (
                order_id, session_id, caller_number, status, items_json,
                len(items), summary_text, sms_text, now, now
            ))

            # Initial revision record
            cursor.execute("""
                INSERT INTO order_revisions (
                    order_id, revision_number, modification_source,
                    previous_items_json, updated_items_json, change_notes, timestamp
                ) VALUES (?, 1, 'VOICE_CALL', NULL, ?, 'Initial call order placement', ?)
            """, (order_id, items_json, now))

            conn.commit()

        logger.info(f"FreshMart Order saved: {order_id} ({len(items)} items) for {caller_number}")
        return self.get_order(order_id)

    def get_order(self, order_id: str) -> Optional[OrderRecord]:
        """Fetch order by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id.upper(),))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_order(row)

    def get_recent_order_for_caller(self, caller_number: str) -> Optional[OrderRecord]:
        """Fetch the most recent order for this caller number."""
        if not caller_number or caller_number == "Unknown":
            return None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM orders 
                WHERE caller_number = ? 
                ORDER BY id DESC LIMIT 1
            """, (caller_number,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_order(row)

    def update_order_items(
        self,
        order_id: str,
        new_items: List[GroceryItem],
        source: str = "VOICE_CALL",
        change_notes: str = "Updated items"
    ) -> Optional[OrderRecord]:
        """Update items in an existing order and increment revision number."""
        existing = self.get_order(order_id)
        if not existing:
            return None

        new_rev = existing.revision_number + 1
        new_items_dict = [item.model_dump() for item in new_items]
        new_items_json = json.dumps(new_items_dict)
        prev_items_json = json.dumps(existing.items)
        now = datetime.utcnow().isoformat()

        item_names = [f"{item.quantity} {item.unit} {item.name}" for item in new_items]
        summary_text = ", ".join(item_names)
        sms_text = self.format_sms_update(order_id, new_items, new_rev)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE orders 
                SET items_json = ?,
                    total_items_count = ?,
                    summary_text = ?,
                    revision_number = ?,
                    sms_status = 'QUEUED',
                    sms_text = ?,
                    status = 'MODIFIED',
                    updated_at = ?
                WHERE order_id = ?
            """, (
                new_items_json, len(new_items), summary_text,
                new_rev, sms_text, now, order_id.upper()
            ))

            cursor.execute("""
                INSERT INTO order_revisions (
                    order_id, revision_number, modification_source,
                    previous_items_json, updated_items_json, change_notes, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (order_id.upper(), new_rev, source, prev_items_json, new_items_json, change_notes, now))

            conn.commit()

        logger.info(f"FreshMart Order {order_id} amended to Revision {new_rev} via {source}")
        return self.get_order(order_id)

    def cancel_order(self, order_id: str, source: str = "VOICE_CALL") -> Optional[OrderRecord]:
        """Cancel an existing order."""
        existing = self.get_order(order_id)
        if not existing:
            return None
        now = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE orders 
                SET status = 'CANCELLED', updated_at = ?
                WHERE order_id = ?
            """, (now, order_id.upper()))
            conn.commit()
        logger.info(f"FreshMart Order {order_id} CANCELLED via {source}")
        return self.get_order(order_id)

    def list_orders(self, limit: int = 50) -> List[OrderRecord]:
        """List recent orders."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [self._row_to_order(r) for r in rows]

    def log_sms(self, direction: str, phone_number: str, message_text: str, status: str, order_id: Optional[str] = None):
        """Log SMS transaction in database."""
        now = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sms_logs (direction, phone_number, order_id, message_text, status, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (direction, phone_number, order_id, message_text, status, now))
            conn.commit()

    def get_pending_sms(self) -> List[Dict[str, Any]]:
        """Get orders with queued SMS to send out."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT order_id, caller_number, sms_text 
                FROM orders 
                WHERE sms_status = 'QUEUED' AND sms_text IS NOT NULL
            """)
            rows = cursor.fetchall()
            return [
                {
                    "order_id": r["order_id"],
                    "phone_number": r["caller_number"],
                    "message": r["sms_text"]
                }
                for r in rows
            ]

    def mark_sms_sent(self, order_id: str, success: bool = True):
        """Update SMS status for an order."""
        status = "SENT" if success else "FAILED"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE orders SET sms_status = ? WHERE order_id = ?", (status, order_id))
            conn.commit()

    @staticmethod
    def format_sms_confirmation(order_id: str, items: List[GroceryItem]) -> str:
        """Standard human-friendly FreshMart confirmation SMS."""
        item_lines = [item.display_str() for item in items]
        joined = ", ".join(item_lines)
        return (
            f"FreshMart: Your order {order_id} is CONFIRMED! Items: {joined}. "
            f"Total items: {len(items)}. "
            f"To modify, reply: CHANGE {order_id} [changes]. Thank you for shopping with us!"
        )

    @staticmethod
    def format_sms_update(order_id: str, items: List[GroceryItem], rev: int) -> str:
        """Standard human-friendly FreshMart updated order SMS."""
        item_lines = [item.display_str() for item in items]
        joined = ", ".join(item_lines)
        return (
            f"FreshMart: Your order {order_id} has been UPDATED (Rev {rev})! "
            f"Current list: {joined}. Total items: {len(items)}. "
            f"Thank you!"
        )

    def _row_to_order(self, row: sqlite3.Row) -> OrderRecord:
        items = json.loads(row["items_json"]) if row["items_json"] else []
        return OrderRecord(
            order_id=row["order_id"],
            session_id=row["session_id"],
            caller_number=row["caller_number"],
            status=row["status"],
            items=items,
            total_items_count=row["total_items_count"],
            summary_text=row["summary_text"],
            revision_number=row["revision_number"],
            sms_status=row["sms_status"],
            sms_text=row["sms_text"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
