"""Self-hosted Arize Phoenix tracing (OpenTelemetry), gated by env."""

from __future__ import annotations

import logging
import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)

_registered: bool = False


def is_phoenix_tracing_requested() -> bool:
    v = os.environ.get("AGENTLAB_PHOENIX_TRACING", "").strip().lower()
    return v in ("1", "true", "yes")


def ensure_phoenix_tracing() -> None:
    """Register Phoenix OTEL exporter and OpenInference auto-instrumentation once."""
    global _registered
    if _registered or not is_phoenix_tracing_requested():
        return
    try:
        from phoenix.otel import register

        project = os.environ.get("PHOENIX_PROJECT_NAME", "agentlab").strip() or "agentlab"
        register(project_name=project, auto_instrument=True)
        _registered = True
        logger.info("Phoenix tracing enabled (project=%s)", project)
    except ImportError:
        logger.warning(
            "AGENTLAB_PHOENIX_TRACING is set but Phoenix packages are missing. "
            "Install with: pip install -e '.[phoenix]'"
        )
    except Exception:
        logger.exception("Phoenix tracing registration failed")


def _clip(s: str, max_len: int = 8000) -> str:
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


@contextmanager
def agent_parent_span(
    span_name: str,
    *,
    input_value: str = "",
    attributes: dict[str, Any] | None = None,
) -> Generator[Any, None, None]:
    """OpenInference AGENT parent span; no-op if tracing is off or registration failed."""
    if not is_phoenix_tracing_requested():
        yield None
        return
    ensure_phoenix_tracing()
    if not _registered:
        yield None
        return

    from opentelemetry import trace
    from openinference.semconv.trace import SpanAttributes

    tracer = trace.get_tracer("agentlab")
    attrs: dict[str, Any] = {
        SpanAttributes.OPENINFERENCE_SPAN_KIND: "AGENT",
    }
    if input_value:
        attrs[SpanAttributes.INPUT_VALUE] = _clip(input_value)
    if attributes:
        for k, v in attributes.items():
            if v is not None:
                attrs[k] = v

    with tracer.start_as_current_span(span_name, attributes=attrs) as span:
        yield span


@contextmanager
def llm_invoke_span(
    span_name: str,
    *,
    input_value: str = "",
    attributes: dict[str, Any] | None = None,
) -> Generator[Any, None, None]:
    """OpenInference LLM child span under the current OpenTelemetry context."""
    if not is_phoenix_tracing_requested():
        yield None
        return
    ensure_phoenix_tracing()
    if not _registered:
        yield None
        return

    from opentelemetry import trace
    from openinference.semconv.trace import SpanAttributes

    tracer = trace.get_tracer("agentlab")
    attrs: dict[str, Any] = {
        SpanAttributes.OPENINFERENCE_SPAN_KIND: "LLM",
    }
    if input_value:
        attrs[SpanAttributes.INPUT_VALUE] = _clip(input_value)
    if attributes:
        for k, v in attributes.items():
            if v is not None:
                attrs[k] = v

    with tracer.start_as_current_span(span_name, attributes=attrs) as span:
        yield span


def set_span_ok(span: Any, output_value: str | None = None) -> None:
    if span is None:
        return
    from opentelemetry.trace import Status, StatusCode
    from openinference.semconv.trace import SpanAttributes

    if output_value:
        span.set_attribute(SpanAttributes.OUTPUT_VALUE, _clip(output_value))
    span.set_status(Status(StatusCode.OK))


def set_span_error(span: Any, exc: BaseException) -> None:
    if span is None:
        return
    from opentelemetry.trace import Status, StatusCode

    span.set_status(Status(StatusCode.ERROR, str(exc)))
    span.record_exception(exc)
