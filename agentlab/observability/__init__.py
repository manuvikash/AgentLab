"""Optional observability integrations (Phoenix / OpenTelemetry)."""

from agentlab.observability.phoenix_tracing import (
    agent_parent_span,
    ensure_phoenix_tracing,
    is_phoenix_tracing_requested,
)

__all__ = [
    "agent_parent_span",
    "ensure_phoenix_tracing",
    "is_phoenix_tracing_requested",
]
