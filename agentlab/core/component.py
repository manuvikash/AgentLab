"""Abstract base classes for all AgentLab component types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from agentlab.models.schemas import (
    LLMResponse,
    Message,
    ToolSpec,
)

if TYPE_CHECKING:
    from agentlab.storage.store import Store


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------


class BaseLLM(ABC):
    """Interface for language model providers."""

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion from the model."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the underlying model identifier."""


# ---------------------------------------------------------------------------
# Loop Controller
# ---------------------------------------------------------------------------


class RuntimeContext:
    """Bag of resolved components passed into a loop controller."""

    def __init__(
        self,
        *,
        llm: BaseLLM,
        context_manager: BaseContextManager,
        tools: list[BaseTool],
        sandbox: BaseSandbox,
        memory: BaseMemory | None = None,
        system_prompt: str | None = None,
        max_steps: int = 30,
        max_tokens: int = 4096,
        store: "Store | None" = None,
    ) -> None:
        self.llm = llm
        self.context_manager = context_manager
        self.tools = {t.name: t for t in tools}
        self.sandbox = sandbox
        self.memory = memory
        self.system_prompt = system_prompt
        self.max_steps = max_steps
        self.max_tokens = max_tokens
        self.store = store


class BaseLoop(ABC):
    """Interface for agent loop controllers (e.g. ReAct)."""

    @abstractmethod
    async def run(self, ctx: RuntimeContext, task_prompt: str) -> LoopResult:
        """Execute the agent loop and return results."""


class LoopResult:
    """Outcome of a loop execution."""

    def __init__(
        self,
        *,
        success: bool | None = None,
        output: str | None = None,
        trace: list[Any] | None = None,
        steps: int = 0,
        total_input_tokens: int = 0,
        total_output_tokens: int = 0,
    ) -> None:
        self.success = success
        self.output = output
        self.trace = trace or []
        self.steps = steps
        self.total_input_tokens = total_input_tokens
        self.total_output_tokens = total_output_tokens


# ---------------------------------------------------------------------------
# Context Manager
# ---------------------------------------------------------------------------


class BaseContextManager(ABC):
    """Interface for managing the LLM conversation context window."""

    @abstractmethod
    def add(self, message: Message) -> None:
        """Add a message to the context."""

    @abstractmethod
    def get_messages(self, max_tokens: int | None = None) -> list[Message]:
        """Return the current context as a list of messages."""

    @abstractmethod
    def reset(self) -> None:
        """Clear all stored context."""


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


class ToolResult:
    """Outcome of executing a tool."""

    def __init__(self, output: str, success: bool = True) -> None:
        self.output = output
        self.success = success


class BaseTool(ABC):
    """Interface for agent tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable tool description."""

    @property
    @abstractmethod
    def parameters_schema(self) -> dict[str, Any]:
        """JSON-Schema dict describing the tool's parameters."""

    @abstractmethod
    async def execute(self, sandbox: BaseSandbox | None = None, **kwargs: Any) -> ToolResult:
        """Execute the tool and return a result."""

    def to_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters=self.parameters_schema,
        )


# ---------------------------------------------------------------------------
# Sandbox
# ---------------------------------------------------------------------------


class ExecutionResult:
    """Outcome of running a command in a sandbox."""

    def __init__(self, exit_code: int, stdout: str, stderr: str) -> None:
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    @property
    def output(self) -> str:
        return self.stdout if self.success else f"{self.stdout}\n{self.stderr}".strip()


class BaseSandbox(ABC):
    """Interface for isolated execution environments."""

    @abstractmethod
    async def start(self) -> None:
        """Initialize the sandbox."""

    @abstractmethod
    async def stop(self) -> None:
        """Tear down the sandbox."""

    @abstractmethod
    async def execute(self, command: str, timeout: int | None = None) -> ExecutionResult:
        """Run a shell command inside the sandbox."""

    @abstractmethod
    async def read_file(self, path: str) -> str:
        """Read a file from the sandbox filesystem."""

    @abstractmethod
    async def write_file(self, path: str, content: str) -> None:
        """Write a file to the sandbox filesystem."""

    @abstractmethod
    async def list_files(self, path: str = ".") -> list[str]:
        """List files under a path in the sandbox."""

    async def __aenter__(self) -> BaseSandbox:
        await self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.stop()


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


class BaseMemory(ABC):
    """Interface for persistent agent memory."""

    @abstractmethod
    def store(self, key: str, value: Any) -> None:
        """Store a value under a key."""

    @abstractmethod
    def retrieve(self, key: str) -> Any | None:
        """Retrieve a value by key."""

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[tuple[str, Any]]:
        """Search memory by query string."""

    @abstractmethod
    def clear(self) -> None:
        """Clear all stored memory."""
