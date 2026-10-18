"""
Audible AI — Supermarket Session Manager (Production Grade)
Thread-safe session manager with atomic command claiming, idempotency,
duplicate speech suppression, one-greeting enforcement, and stale-session pruning.
"""

import uuid
import threading
from typing import Dict, Optional, List, Set, Any
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger

from api.services.supermarket.models import SupermarketOrder, ConversationState, ConfirmationStatus


class CommandState(str, Enum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SupermarketSessionManager:
    _instance: Optional['SupermarketSessionManager'] = None
    _lock = threading.RLock()

    def __init__(self):
        self._sessions: Dict[str, SupermarketOrder] = {}
        self._session_created_at: Dict[str, datetime] = {}
        self._active_session_id: Optional[str] = None
        self._pending_commands: Dict[str, List[Dict[str, Any]]] = {}
        self._claimed_commands: Dict[str, Dict[str, Any]] = {}   # command_id -> cmd dict with claim metadata
        self._completed_commands: Dict[str, Dict[str, Any]] = {} # command_id -> cmd dict
        self._seq_counter: int = 0
        self._last_speech_texts: Dict[str, str] = {}             # session_id -> last queued text
        self._greeted_sessions: Set[str] = set()                # session_ids that have delivered greeting

    @classmethod
    def get_instance(cls) -> 'SupermarketSessionManager':
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def get_or_create_session(self, session_id: str, caller_id: str = "Unknown") -> SupermarketOrder:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SupermarketOrder(
                    session_id=session_id,
                    caller_id=caller_id,
                    state=ConversationState.ANSWERED,
                    confirmation_status=ConfirmationStatus.PENDING
                )
                self._session_created_at[session_id] = datetime.utcnow()
                self._active_session_id = session_id
                self._pending_commands[session_id] = []
                logger.info(f"[SessionManager] Created new session: {session_id} for caller {caller_id}")
            return self._sessions[session_id]

    def get_active_session(self) -> Optional[SupermarketOrder]:
        with self._lock:
            if self._active_session_id and self._active_session_id in self._sessions:
                return self._sessions[self._active_session_id]
            return None

    def should_greet(self, session_id: str) -> bool:
        """Enforces strictly one greeting per call session."""
        with self._lock:
            return session_id not in self._greeted_sessions

    def mark_greeted(self, session_id: str):
        """Marks session as having received its initial greeting."""
        with self._lock:
            self._greeted_sessions.add(session_id)
            logger.info(f"[SessionManager] Session {session_id} marked as greeted.")

    def reset_session(self, session_id: str):
        with self._lock:
            self.cancel_session_commands(session_id)
            if session_id in self._sessions:
                del self._sessions[session_id]
            if session_id in self._session_created_at:
                del self._session_created_at[session_id]
            if self._active_session_id == session_id:
                self._active_session_id = None
            if session_id in self._pending_commands:
                del self._pending_commands[session_id]
            if session_id in self._last_speech_texts:
                del self._last_speech_texts[session_id]
            if session_id in self._greeted_sessions:
                self._greeted_sessions.remove(session_id)

    def queue_command(self, session_id: str, action: str, data: Optional[dict] = None) -> str:
        """
        Thread-safe idempotent command queueing with unique UUID and duplicate suppression.
        Returns command_id.
        """
        with self._lock:
            if session_id not in self._pending_commands:
                self._pending_commands[session_id] = []

            # Duplicate speech suppression check
            if action == "SPEAK" and data and "text" in data:
                text_clean = data["text"].strip()
                last_text = self._last_speech_texts.get(session_id)
                if last_text == text_clean:
                    logger.debug(f"[SessionManager] Suppressed duplicate speech for {session_id}: '{last_text[:40]}...'")
                    return "duplicate_suppressed"
                self._last_speech_texts[session_id] = text_clean

            self._seq_counter += 1
            cmd_id = f"cmd_{uuid.uuid4().hex[:12]}"
            cmd = {
                "command_id": cmd_id,
                "session_id": session_id,
                "seq": self._seq_counter,
                "action": action,
                "status": CommandState.PENDING.value,
                "queued_at": datetime.utcnow().isoformat()
            }
            if data:
                cmd.update(data)

            self._pending_commands[session_id].append(cmd)
            logger.info(f"[SessionManager] Queued #{self._seq_counter} ({action}) id={cmd_id} for session {session_id}")
            return cmd_id

    def claim_commands(self, session_id: str, client_id: str = "companion", lease_seconds: int = 15) -> List[Dict[str, Any]]:
        """
        Atomically claims all pending commands for a session.
        Moves them from PENDING to CLAIMED with a lease expiration.
        """
        with self._lock:
            now = datetime.utcnow()
            claimed_list: List[Dict[str, Any]] = []

            # 1. Check for expired claimed commands that need retry
            for cid, cmd in list(self._claimed_commands.items()):
                if cmd.get("session_id") == session_id:
                    claimed_time = cmd.get("_claimed_at", now)
                    if (now - claimed_time).total_seconds() > lease_seconds:
                        logger.warning(f"[SessionManager] Command {cid} lease expired (>{lease_seconds}s). Re-claiming for retry.")
                        cmd["status"] = CommandState.CLAIMED.value
                        cmd["_claimed_at"] = now
                        cmd["_retry_count"] = cmd.get("_retry_count", 0) + 1
                        claimed_list.append(cmd)

            # 2. Claim pending commands
            if session_id in self._pending_commands:
                pending = self._pending_commands[session_id]
                self._pending_commands[session_id] = []

                for cmd in pending:
                    cmd["status"] = CommandState.CLAIMED.value
                    cmd["claimed_by"] = client_id
                    cmd["_claimed_at"] = now
                    cmd_id = cmd["command_id"]
                    self._claimed_commands[cmd_id] = cmd
                    claimed_list.append(cmd)

            # Clean internal metadata before delivering over REST
            export_list = []
            for cmd in claimed_list:
                cleaned = {k: v for k, v in cmd.items() if not k.startswith("_")}
                export_list.append(cleaned)

            return export_list

    def ack_command(self, command_id: str, status: str = "COMPLETED", error: Optional[str] = None) -> bool:
        """
        Atomically acknowledges completion of a command after client execution.
        """
        with self._lock:
            cmd = self._claimed_commands.pop(command_id, None)
            if not cmd:
                # Check if it was in pending
                for sid, plist in self._pending_commands.items():
                    for idx, c in enumerate(plist):
                        if c.get("command_id") == command_id:
                            cmd = plist.pop(idx)
                            break
                    if cmd:
                        break

            if cmd:
                cmd["status"] = status
                cmd["completed_at"] = datetime.utcnow().isoformat()
                if error:
                    cmd["error"] = error
                self._completed_commands[command_id] = cmd
                logger.info(f"[SessionManager] Command {command_id} acknowledged with status={status}")
                return True
            else:
                logger.debug(f"[SessionManager] Command {command_id} already acknowledged or unknown.")
                return False

    def cancel_session_commands(self, session_id: str) -> int:
        """Cancels all pending and in-flight commands for a session when call ends."""
        with self._lock:
            cancelled_count = 0
            if session_id in self._pending_commands:
                cancelled_count += len(self._pending_commands[session_id])
                self._pending_commands[session_id] = []

            for cid, cmd in list(self._claimed_commands.items()):
                if cmd.get("session_id") == session_id:
                    cmd["status"] = CommandState.CANCELLED.value
                    del self._claimed_commands[cid]
                    self._completed_commands[cid] = cmd
                    cancelled_count += 1

            logger.info(f"[SessionManager] Cancelled {cancelled_count} commands for session {session_id}")
            return cancelled_count

    def cleanup_stale_sessions(self, max_age_seconds: int = 1800) -> int:
        """Purge sessions older than max_age_seconds (default 30 mins)."""
        with self._lock:
            now = datetime.utcnow()
            stale_cutoff = now - timedelta(seconds=max_age_seconds)
            stale_ids = [
                sid for sid, created in self._session_created_at.items()
                if created < stale_cutoff
            ]

            for sid in stale_ids:
                logger.info(f"[SessionManager] Purging stale session {sid} (created > {max_age_seconds}s ago)")
                self.reset_session(sid)

            # Also prune completed command log to prevent memory leaks (keep last 500)
            if len(self._completed_commands) > 500:
                keys_to_remove = list(self._completed_commands.keys())[:-500]
                for k in keys_to_remove:
                    del self._completed_commands[k]

            return len(stale_ids)
