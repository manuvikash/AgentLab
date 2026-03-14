"""Dynamic component registry with decorator-based registration."""

from __future__ import annotations

from typing import Any, Callable, TypeVar

from agentlab.core.component import (
    BaseContextManager,
    BaseLLM,
    BaseLoop,
    BaseMemory,
    BaseSandbox,
    BaseTool,
)

T = TypeVar("T")

_COMPONENT_TYPE_MAP: dict[str, type] = {
    "llm": BaseLLM,
    "loop": BaseLoop,
    "context": BaseContextManager,
    "tool": BaseTool,
    "sandbox": BaseSandbox,
    "memory": BaseMemory,
}


class ComponentRegistry:
    """Singleton registry mapping (component_type, name) -> class."""

    _instance: ComponentRegistry | None = None
    _entries: dict[tuple[str, str], type]

    def __new__(cls) -> ComponentRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._entries = {}
        return cls._instance

    def register(self, component_type: str, name: str, cls_ref: type) -> None:
        base = _COMPONENT_TYPE_MAP.get(component_type)
        if base is None:
            raise ValueError(
                f"Unknown component type '{component_type}'. "
                f"Valid types: {list(_COMPONENT_TYPE_MAP)}"
            )
        if not issubclass(cls_ref, base):
            raise TypeError(
                f"{cls_ref.__name__} must be a subclass of {base.__name__} "
                f"for component type '{component_type}'"
            )
        self._entries[(component_type, name)] = cls_ref

    def get(self, component_type: str, name: str) -> type:
        key = (component_type, name)
        if key not in self._entries:
            available = [n for (t, n) in self._entries if t == component_type]
            raise KeyError(
                f"No '{component_type}' component named '{name}'. "
                f"Available: {available}"
            )
        return self._entries[key]

    def create(self, component_type: str, name: str, **kwargs: Any) -> Any:
        cls_ref = self.get(component_type, name)
        return cls_ref(**kwargs)

    def list_components(self, component_type: str | None = None) -> list[dict[str, str]]:
        items = []
        for (ctype, cname), cls_ref in sorted(self._entries.items()):
            if component_type and ctype != component_type:
                continue
            items.append({
                "type": ctype,
                "name": cname,
                "class": f"{cls_ref.__module__}.{cls_ref.__qualname__}",
            })
        return items

    def clear(self) -> None:
        self._entries.clear()

    @classmethod
    def reset(cls) -> None:
        """Destroy the singleton (for testing)."""
        if cls._instance is not None:
            cls._instance._entries.clear()
            cls._instance = None


def register(component_type: str, name: str) -> Callable[[type[T]], type[T]]:
    """Class decorator that registers a component implementation.

    Usage::

        @register("llm", "openai")
        class OpenAILLM(BaseLLM): ...
    """

    def decorator(cls: type[T]) -> type[T]:
        ComponentRegistry().register(component_type, name, cls)
        return cls

    return decorator


def get_registry() -> ComponentRegistry:
    return ComponentRegistry()
