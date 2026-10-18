"""
Audible AI — Supermarket Session Manager
Thread-safe in-memory session manager for real-time supermarket phone calls.
Includes command UUID generation, sequence tracking, deduplication, and acknowledgment.
"""

import uuid
from typing import Dict, Optional, List, Set, Any
from datetime import datetime
from loguru import logger

from api.services.supermarket.models import SupermarketOrder, ConversationState, ConfirmationStatus


class SupermarketSessionManager:
    _instance: Optional['SupermarketSessionManager'] = None

    def __init__(self):
        self._sessions: Dict[str, SupermarketOrder] = {}
        self._active_session_id: Optional[str] = None
        self._pending_commands: Dict[str, List[Dict[str, Any]]] = {}
        self._delivered_commands: Dict[str, Dict[str, Any]] = {}  # command_id -> command
        self._acked_command_ids: Set[str] = set()
        self._seq_counter: int = 0
        self._last_speech_texts: Dict[str, str] = {}  # session_id -> last queued text

    @classmethod
    def get_instance(cls) -> 'SupermarketSessionManager':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_or_create_session(self, session_id: str, caller_id: str = "Unknown") -> SupermarketOrder:
        if session_id not in self._sessions:
            self._sessions[session_id] = SupermarketOrder(
                session_id=session_id,
                caller_id=caller_id,
                state=ConversationState.ANSWERED,
                confirmation_status=ConfirmationStatus.PENDING
            )
            self._active_session_id = session_id
            self._pending_commands[session_id] = []
        return self._sessions[session_id]

    def get_active_session(self) -> Optional[SupermarketOrder]:
        if self._active_session_id and self._active_session_id in self._sessions:
            return self._sessions[self._active_session_id]
        return None

    def reset_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]
        if self._active_session_id == session_id:
            self._active_session_id = None
        if session_id in self._pending_commands:
            del self._pending_commands[session_id]
        if session_id in self._last_speech_texts:
            del self._last_speech_texts[session_id]

    def queue_command(self, session_id: str, action: str, data: Optional[dict] = None) -> str:
        """
        Queue an idempotent command with unique UUID, sequence number, and deduplication.
        Returns command_id.
        """
        if session_id not in self._pending_commands:
            self._pending_commands[session_id] = []

        # Deduplication check for SPEAK action
        if action == "SPEAK" and data and "text" in data:
            last_text = self._last_speech_texts.get(session_id)
            if last_text == data["text"].strip():
                logger.debug(f"[SessionManager] Suppressed duplicate speech for session {session_id}: '{last_text[:30]}...'")
                return "duplicate_suppressed"
            self._last_speech_texts[session_id] = data["text"].strip()

        self._seq_counter += 1
        cmd_id = str(uuid.uuid4())
        cmd = {
            "command_id": cmd_id,
            "seq": self._seq_counter,
            "action": action,
            "timestamp": datetime.utcnow().isoformat()
        }
        if data:
            cmd.update(data)

        self._pending_commands[session_id].append(cmd)
        self._delivered_commands[cmd_id] = cmd
        logger.debug(f"[SessionManager] Queued command #{self._seq_counter} ({action}) id={cmd_id} for session {session_id}")
        return cmd_id

    def pop_commands(self, session_id: str) -> List[Dict[str, Any]]:
        """Pop all unpolled commands for this session."""
        if session_id in self._pending_commands:
            cmds = self._pending_commands[session_id]
            self._pending_commands[session_id] = []
            return cmds
        return []

    def ack_command(self, command_id: str) -> bool:
        """Acknowledge successful execution of a command on the client."""
        self._acked_command_ids.add(command_id)
        if command_id in self._delivered_commands:
            del self._delivered_commands[command_id]
        return True
