"""Core abstractions for AgentLab."""

from agentlab.core.component import (
    BaseContextManager,
    BaseLLM,
    BaseLoop,
    BaseMemory,
    BaseSandbox,
    BaseTool,
    ExecutionResult,
    LoopResult,
    RuntimeContext,
    ToolResult,
)
from agentlab.core.registry import ComponentRegistry, get_registry, register

__all__ = [
    "BaseContextManager",
    "BaseLLM",
    "BaseLoop",
    "BaseMemory",
    "BaseSandbox",
    "BaseTool",
    "ComponentRegistry",
    "ExecutionResult",
    "LoopResult",
    "RuntimeContext",
    "ToolResult",
    "get_registry",
    "register",
]
