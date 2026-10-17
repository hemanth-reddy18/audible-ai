"""Audible AI run context variables."""

from contextvars import ContextVar
from typing import Optional

org_id_var: ContextVar[Optional[int]] = ContextVar("org_id", default=None)
run_id_var: ContextVar[Optional[int]] = ContextVar("run_id", default=None)
turn_var: ContextVar[Optional[int]] = ContextVar("turn", default=None)


def set_current_turn(turn: Optional[int]) -> None:
    turn_var.set(turn)


def get_current_turn() -> Optional[int]:
    return turn_var.get()


def set_current_org_id(org_id: Optional[int]) -> None:
    org_id_var.set(org_id)


def get_current_org_id() -> Optional[int]:
    return org_id_var.get()


def set_current_run_id(run_id: Optional[int]) -> None:
    run_id_var.set(run_id)


def get_current_run_id() -> Optional[int]:
    return run_id_var.get()


# Register in sys.modules under pipecat.utils.run_context for compatibility
import sys

try:
    import pipecat.utils
    pipecat.utils.run_context = sys.modules[__name__]
    sys.modules["pipecat.utils.run_context"] = sys.modules[__name__]
except Exception:
    pass
