"""Agent runtime — loads config, resolves components, executes the loop."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import agentlab.components  # noqa: F401 — trigger auto-registration
from agentlab.core.component import RuntimeContext
from agentlab.core.registry import get_registry
from agentlab.models.schemas import (
    AgentConfig,
    Metrics,
    RunRecord,
    TraceEntry,
)
from agentlab.observability.phoenix_tracing import (
    agent_parent_span,
    set_span_error,
    set_span_ok,
)
from agentlab.storage.store import Store

logger = logging.getLogger(__name__)


class AgentRunner:
    """Orchestrates a single agent run.

    1. Resolves all components from the registry
    2. Initializes the sandbox
    3. Delegates to the loop controller
    4. Records trace + metrics
    5. Persists the RunRecord
    """

    def __init__(self, store: Store | None = None) -> None:
        self._store = store or Store()
        self._registry = get_registry()

    async def run(
        self,
        config: AgentConfig,
        task_prompt: str = "",
        task_id: str | None = None,
        **overrides: Any,
    ) -> RunRecord:
        run = RunRecord(
            agent_name=config.name,
            agent_config=config,
            task_id=task_id,
            status="running",
        )

        start = time.monotonic()

        # Resolve the sandbox working directory from the task's repo field so
        # the agent lands directly in the directory that contains the task files.
        sandbox_overrides = dict(overrides)
        if task_id and "workdir" not in sandbox_overrides:
            try:
                task_cfg = self._store.load_task(task_id)
                if task_cfg.repo:
                    task_dir = self._store.get_task_dir(task_id)
                    repo_path = (task_dir / task_cfg.repo).resolve()
                    if repo_path.is_dir():
                        sandbox_overrides["workdir"] = str(repo_path)
                        logger.info(
                            "Run %s: sandbox workdir set to %s",
                            run.id,
                            repo_path,
                        )
            except FileNotFoundError:
                pass

        llm = self._registry.create("llm", config.llm)
        loop = self._registry.create("loop", config.loop)
        context_mgr = self._registry.create("context", config.context)
        tools = [self._registry.create("tool", t) for t in config.tools]
        sandbox = self._registry.create("sandbox", config.sandbox, **sandbox_overrides)
        memory = (
            self._registry.create("memory", config.memory) if config.memory else None
        )

        ctx = RuntimeContext(
            llm=llm,
            context_manager=context_mgr,
            tools=tools,
            sandbox=sandbox,
            memory=memory,
            system_prompt=config.prompt,
            max_steps=config.max_steps,
            max_tokens=config.max_tokens,
        )

        prompt = task_prompt or config.prompt or "No task specified."
        span_attrs: dict[str, str] = {
            "agentlab.run_id": run.id,
            "agentlab.agent_name": config.name,
            "agentlab.loop": config.loop,
        }
        if task_id:
            span_attrs["agentlab.task_id"] = task_id

        with agent_parent_span(
            "agentlab.run",
            input_value=prompt,
            attributes=span_attrs,
        ) as otel_span:
            try:
                async with sandbox:
                    result = await loop.run(ctx, prompt)

                elapsed = time.monotonic() - start

                trace_entries = []
                for raw in result.trace:
                    if isinstance(raw, dict):
                        trace_entries.append(TraceEntry(**raw))
                    elif isinstance(raw, TraceEntry):
                        trace_entries.append(raw)

                run.status = "completed"
                run.trace = trace_entries
                run.metrics = Metrics(
                    success=result.success,
                    steps=result.steps,
                    tokens_used=result.total_input_tokens + result.total_output_tokens,
                    input_tokens=result.total_input_tokens,
                    output_tokens=result.total_output_tokens,
                    runtime_seconds=round(elapsed, 3),
                )
                run.completed_at = datetime.now(timezone.utc)

                out = ""
                if trace_entries:
                    last = trace_entries[-1]
                    out = (last.result or last.thought or "") or ""
                set_span_ok(otel_span, out)

            except Exception as exc:
                set_span_error(otel_span, exc)
                logger.exception("Agent run failed")
                run.status = "failed"
                run.error = str(exc)
                run.completed_at = datetime.now(timezone.utc)

        self._store.save_run(run)
        logger.info(
            "Run %s finished — status=%s steps=%s tokens=%s",
            run.id,
            run.status,
            run.metrics.steps,
            run.metrics.tokens_used,
        )
        return run
