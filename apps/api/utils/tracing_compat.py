"""OpenTelemetry and Langfuse tracing compatibility layer for Audible AI."""

import asyncio
import functools
import json
import os
from typing import Any, Callable, Optional

from opentelemetry import trace
from opentelemetry.trace import StatusCode
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from pipecat.frames.frames import LLMTextFrame


_trace_public_resolver: Optional[Callable[[], bool]] = None


def set_trace_public_resolver(resolver: Callable[[], bool]) -> None:
    """Set the resolver function for determining if a trace should be public."""
    global _trace_public_resolver
    _trace_public_resolver = resolver


def traces_public_from_env() -> bool:
    """Check if traces should be public based on environment variable."""
    val = os.getenv("LANGFUSE_TRACES_PUBLIC", "false").strip().lower()
    return val in ("true", "1", "yes")


def mark_trace_public(span: Any) -> None:
    """Mark an OpenTelemetry span as publicly accessible in Langfuse."""
    if span and hasattr(span, "set_attribute"):
        try:
            span.set_attribute("langfuse.trace.public", True)
        except Exception:
            pass


def setup_tracing(service_name: str = "audible-pipeline", exporter: Any = None) -> TracerProvider:
    """Initialize OpenTelemetry tracer provider with optional exporter."""
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    if exporter:
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return provider


class TracingContext:
    """Context container carrying trace and span IDs across pipeline stages."""

    def __init__(
        self,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        parent_context: Any = None,
    ):
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_context = parent_context


def traced_llm(func: Callable) -> Callable:
    """Decorator to trace LLM calls, recording inputs, outputs, models, and cancellations."""
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not getattr(self, "_tracing_enabled", False):
            return await func(self, *args, **kwargs)

        tracer = trace.get_tracer("pipecat")
        span = tracer.start_span("llm_generate")

        model = (
            getattr(self, "_model_name", None)
            or getattr(self, "model_name", None)
            or getattr(self, "model", None)
        )
        if model:
            span.set_attribute("gen_ai.request.model", str(model))

        context = args[0] if args else kwargs.get("context")
        if context and hasattr(context, "tools") and context.tools:
            tools_list = []
            for t in getattr(context.tools, "standard_tools", []):
                tool_dict = {
                    "type": "function",
                    "function": {
                        "name": getattr(t, "name", ""),
                        "description": getattr(t, "description", ""),
                    },
                }
                tools_list.append(tool_dict)
            if tools_list:
                span.set_attribute("input", json.dumps({"tools": tools_list}))

        collected_output: list[str] = []
        original_push = getattr(self, "push_frame", None)

        if original_push:
            async def intercept_push(frame, *p_args, **p_kwargs):
                if isinstance(frame, LLMTextFrame) and getattr(frame, "text", None):
                    collected_output.append(frame.text)
                return await original_push(frame, *p_args, **p_kwargs)

            self.push_frame = intercept_push

        try:
            res = await func(self, *args, **kwargs)
            if collected_output:
                span.set_attribute("output", "".join(collected_output))
            return res
        except asyncio.CancelledError:
            span.set_attribute("langfuse.observation.status_message", "Cancelled")
            span.set_attribute("langfuse.observation.metadata.request_status", "cancelled")
            if collected_output:
                span.set_attribute("output", "".join(collected_output))
            raise
        except Exception as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            raise
        finally:
            if original_push:
                self.push_frame = original_push
            span.end()

    return wrapper


def traced_tts(func: Callable) -> Callable:
    """Decorator to trace TTS synthesis calls."""
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not getattr(self, "_tracing_enabled", False):
            return await func(self, *args, **kwargs)

        tracer = trace.get_tracer("pipecat")
        span = tracer.start_span("tts_synthesize")
        try:
            return await func(self, *args, **kwargs)
        except asyncio.CancelledError:
            span.set_attribute("langfuse.observation.status_message", "Cancelled")
            span.set_attribute("langfuse.observation.metadata.request_status", "cancelled")
            raise
        except Exception as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            raise
        finally:
            span.end()

    return wrapper


__all__ = [
    "set_trace_public_resolver",
    "traces_public_from_env",
    "setup_tracing",
    "TracingContext",
    "traced_llm",
    "traced_tts",
]
