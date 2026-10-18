"""Pipecat services and compatibility bridges for Audible AI."""
import inspect as _inspect
from pipecat.processors.aggregators.llm_response_universal import (
    LLMAssistantAggregatorParams,
    LLMUserAggregatorParams,
    LLMUserAggregator,
)
from pipecat.pipeline.worker import PipelineWorker
from pipecat.pipeline.task import PipelineTask
import pipecat.frames.frames as _frames
if hasattr(_frames, "SpeechBoundaryFrame"):
    SpeechBoundaryFrame = _frames.SpeechBoundaryFrame
else:
    from pipecat.frames.frames import Frame as _Frame
    class SpeechBoundaryFrame(_Frame):
        def __init__(self, speech_id: str = "", beginning: bool = True, *args, **kwargs):
            super().__init__()
            self.speech_id = speech_id
            self.beginning = beginning
    _frames.SpeechBoundaryFrame = SpeechBoundaryFrame

from pipecat.frames.frames import TTSSpeakFrame
from pipecat.services.llm_service import LLMService


def _make_tolerant_params(cls):
    orig_init = cls.__init__
    valid = set(_inspect.signature(orig_init).parameters.keys())

    def new_init(self, *args, **kwargs):
        filtered = {k: v for k, v in kwargs.items() if k in valid}
        return orig_init(self, *args, **filtered)

    cls.__init__ = new_init


_make_tolerant_params(LLMAssistantAggregatorParams)
_make_tolerant_params(LLMUserAggregatorParams)
_make_tolerant_params(PipelineWorker)
_make_tolerant_params(PipelineTask)
_make_tolerant_params(TTSSpeakFrame)
_make_tolerant_params(SpeechBoundaryFrame)

if not hasattr(LLMUserAggregator, "user_turn_controller"):
    LLMUserAggregator.user_turn_controller = property(
        lambda self: getattr(self, "_user_turn_controller", None)
    )
if not hasattr(LLMUserAggregator, "user_idle_controller"):
    LLMUserAggregator.user_idle_controller = property(
        lambda self: getattr(self, "_user_idle_controller", None)
    )
if not hasattr(LLMUserAggregator, "vad_controller"):
    LLMUserAggregator.vad_controller = property(
        lambda self: getattr(self, "_vad_controller", None)
    )

try:
    from pipecat.turns.user_turn_controller import UserTurnController
    if not hasattr(UserTurnController, "has_active_user_turn"):
        UserTurnController.has_active_user_turn = property(
            lambda self: getattr(self, "_user_turn_active", False)
        )
except Exception:
    pass

if not hasattr(PipelineWorker, "user_bot_latency_observer"):
    PipelineWorker.user_bot_latency_observer = None
if not hasattr(PipelineTask, "user_bot_latency_observer"):
    PipelineTask.user_bot_latency_observer = None

if not hasattr(PipelineWorker, "turn_trace_observer"):
    PipelineWorker.turn_trace_observer = None
if not hasattr(PipelineTask, "turn_trace_observer"):
    PipelineTask.turn_trace_observer = None


async def _noop_wait_for_observers(self):
    pass


if not hasattr(PipelineWorker, "wait_for_observers"):
    PipelineWorker.wait_for_observers = _noop_wait_for_observers
if not hasattr(PipelineTask, "wait_for_observers"):
    PipelineTask.wait_for_observers = _noop_wait_for_observers

_orig_register = LLMService.register_function


def _tolerant_register_function(self, function_name, handler, *args, **kwargs):
    valid = {"cancel_on_interruption", "timeout_secs", "cancellable_by_llm"}
    filtered = {k: v for k, v in kwargs.items() if k in valid}
    if "is_node_transition" in kwargs and hasattr(handler, "__dict__"):
        handler.__dict__["is_node_transition"] = kwargs["is_node_transition"]
    return _orig_register(self, function_name, handler, *args, **filtered)


LLMService.register_function = _tolerant_register_function

from pipecat.processors.aggregators.llm_context import LLMContext

if not hasattr(LLMContext, "set_otel_span_name"):
    LLMContext.set_otel_span_name = lambda self, name: None
