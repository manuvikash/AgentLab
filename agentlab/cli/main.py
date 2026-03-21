"""AgentLab CLI — the ``lab`` command."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

import agentlab.components  # noqa: F401 — trigger auto-registration
from agentlab.core.registry import get_registry
from agentlab.observability.phoenix_tracing import ensure_phoenix_tracing
from agentlab.storage.store import Store

console = Console()


def _load_env() -> None:
    """Load environment variables from .env/example.env if present.

    Priority:
    1. Existing process env vars (never overridden)
    2. .env (if present)
    3. example.env (if present)
    """

    cwd = Path.cwd()
    dotenv_path = cwd / ".env"
    example_path = cwd / "example.env"

    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path, override=False)
    if example_path.exists():
        load_dotenv(dotenv_path=example_path, override=False)


def _get_store() -> Store:
    _load_env()
    return Store(root=Path.cwd())


def _run_async(coro):
    return asyncio.run(coro)


# ======================================================================
# Root group
# ======================================================================


@click.group()
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase verbosity (-v for INFO, -vv for DEBUG).",
)
@click.version_option(package_name="agentlab")
@click.pass_context
def cli(ctx: click.Context, verbose: int) -> None:
    """AgentLab — modular AI agent platform."""
    # Configure logging based on verbosity level
    if verbose <= 0:
        level = logging.WARNING
    elif verbose == 1:
        level = logging.INFO
    else:
        level = logging.DEBUG

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


# ======================================================================
# lab run
# ======================================================================


@cli.command("run")
@click.argument("agent_name")
@click.option("--task", default=None, help="Task ID to run against.")
@click.option("--prompt", default=None, help="Ad-hoc task prompt (overrides task file).")
@click.option("--workdir", default=None, help="Sandbox working directory.")
def run_agent(agent_name: str, task: str | None, prompt: str | None, workdir: str | None) -> None:
    """Run an agent."""
    from agentlab.runtime.runner import AgentRunner

    store = _get_store()
    ensure_phoenix_tracing()

    try:
        config = store.load_agent(agent_name)
    except FileNotFoundError:
        console.print(f"[red]Agent '{agent_name}' not found in agents/[/red]")
        sys.exit(1)

    task_prompt = prompt or ""
    task_id = task

    if task and not prompt:
        try:
            task_cfg = store.load_task(task)
            task_prompt = task_cfg.prompt
            task_id = task_cfg.id
        except FileNotFoundError:
            console.print(f"[red]Task '{task}' not found in tasks/[/red]")
            sys.exit(1)

    runner = AgentRunner(store=store)
    overrides = {}
    if workdir:
        overrides["workdir"] = workdir

    console.print(f"[bold]Running agent:[/bold] {agent_name}")
    if task_id:
        console.print(f"[bold]Task:[/bold] {task_id}")

    run_record = _run_async(runner.run(config, task_prompt=task_prompt, task_id=task_id, **overrides))

    _print_run_summary(run_record)


# ======================================================================
# lab agents
# ======================================================================


@cli.group("agents")
def agents_group() -> None:
    """Manage agents."""


@agents_group.command("list")
def agents_list() -> None:
    """List available agents."""
    store = _get_store()
    agents = store.list_agents()

    if not agents:
        console.print("[dim]No agents found in agents/[/dim]")
        return

    table = Table(title="Agents")
    table.add_column("Name", style="bold")
    table.add_column("LLM")
    table.add_column("Loop")
    table.add_column("Context")
    table.add_column("Tools")
    table.add_column("Sandbox")

    for a in agents:
        table.add_row(a.name, a.llm, a.loop, a.context, ", ".join(a.tools), a.sandbox)

    console.print(table)


@agents_group.command("show")
@click.argument("name")
def agents_show(name: str) -> None:
    """Show details for an agent."""
    import yaml

    store = _get_store()
    try:
        config = store.load_agent(name)
    except FileNotFoundError:
        console.print(f"[red]Agent '{name}' not found[/red]")
        sys.exit(1)

    console.print(yaml.dump(config.model_dump(), sort_keys=False))


# ======================================================================
# lab components
# ======================================================================


@cli.group("components")
def components_group() -> None:
    """Manage components."""


@components_group.command("list")
@click.option("--type", "component_type", default=None, help="Filter by component type.")
def components_list(component_type: str | None) -> None:
    """List registered components."""
    registry = get_registry()
    items = registry.list_components(component_type)

    if not items:
        console.print("[dim]No components registered[/dim]")
        return

    table = Table(title="Components")
    table.add_column("Type", style="bold")
    table.add_column("Name")
    table.add_column("Class")

    for item in items:
        table.add_row(item["type"], item["name"], item["class"])

    console.print(table)


# ======================================================================
# lab replay
# ======================================================================


@cli.command("replay")
@click.argument("run_id")
def replay(run_id: str) -> None:
    """Replay the trace of a past run."""
    store = _get_store()

    try:
        run = store.load_run(run_id)
    except FileNotFoundError:
        console.print(f"[red]Run '{run_id}' not found[/red]")
        sys.exit(1)

    console.print(f"[bold]Run:[/bold] {run.id}  [bold]Agent:[/bold] {run.agent_name}")
    console.print(f"[bold]Status:[/bold] {run.status}  [bold]Steps:[/bold] {run.metrics.steps}")
    console.print()

    for entry in run.trace:
        console.rule(f"Step {entry.step}")
        if entry.thought:
            console.print(f"[cyan]Thought:[/cyan] {entry.thought}")
        if entry.action:
            console.print(f"[yellow]Action:[/yellow] {entry.action}")
        if entry.tool_call:
            console.print(
                f"[green]Tool:[/green] {entry.tool_call.tool}"
                f"({json.dumps(entry.tool_call.args, default=str)})"
            )
            if entry.tool_call.result:
                console.print(f"[blue]Result:[/blue] {entry.tool_call.result[:500]}")
        elif entry.result:
            console.print(f"[blue]Result:[/blue] {entry.result[:500]}")
        console.print()


# ======================================================================
# lab runs (list past runs)
# ======================================================================


@cli.group("runs")
def runs_group() -> None:
    """Manage runs."""


@runs_group.command("list")
def runs_list() -> None:
    """List past runs."""
    store = _get_store()
    runs = store.list_runs()

    if not runs:
        console.print("[dim]No runs found[/dim]")
        return

    table = Table(title="Runs")
    table.add_column("ID", style="bold")
    table.add_column("Agent")
    table.add_column("Task")
    table.add_column("Status")
    table.add_column("Steps")
    table.add_column("Tokens")
    table.add_column("Runtime (s)")
    table.add_column("Created")

    for r in runs:
        table.add_row(
            r.id,
            r.agent_name,
            r.task_id or "-",
            r.status,
            str(r.metrics.steps),
            str(r.metrics.tokens_used),
            f"{r.metrics.runtime_seconds:.1f}",
            r.created_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


# ======================================================================
# lab experiment
# ======================================================================


@cli.group("experiment")
def experiment_group() -> None:
    """Manage experiments."""


@experiment_group.command("run")
@click.argument("config_path", type=click.Path(exists=True))
def experiment_run(config_path: str) -> None:
    """Run an experiment from a YAML config."""
    import yaml

    from agentlab.experiment.engine import ExperimentEngine
    from agentlab.models.schemas import ExperimentConfig

    store = _get_store()
    ensure_phoenix_tracing()

    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    exp_config = ExperimentConfig(**raw)
    engine = ExperimentEngine(store=store)

    console.print(f"[bold]Running experiment:[/bold] {exp_config.name}")
    configs = engine.generate_configs(exp_config)
    console.print(f"  Configurations: {len(configs)}")

    record = _run_async(engine.run(exp_config))

    console.print()
    if record.status == "completed":
        console.print(f"[green bold]Experiment completed[/green bold] — {record.id}")
    else:
        console.print(f"[red bold]Experiment failed[/red bold] — {record.id}")
    console.print(f"  Runs: {len(record.run_ids)}")


@experiment_group.command("results")
@click.argument("experiment_id")
def experiment_results(experiment_id: str) -> None:
    """Show results for an experiment."""
    from agentlab.experiment.comparison import experiment_summary

    store = _get_store()

    try:
        rows = experiment_summary(experiment_id, store)
    except FileNotFoundError:
        console.print(f"[red]Experiment '{experiment_id}' not found[/red]")
        sys.exit(1)

    if not rows:
        console.print("[dim]No runs found for this experiment[/dim]")
        return

    table = Table(title=f"Experiment {experiment_id}")
    table.add_column("Run ID", style="bold")
    table.add_column("Agent")
    table.add_column("Task")
    table.add_column("Status")
    table.add_column("Success")
    table.add_column("Steps")
    table.add_column("Tokens")
    table.add_column("Runtime (s)")

    for row in rows:
        table.add_row(
            str(row["run_id"]),
            str(row["agent"]),
            str(row["task"]),
            str(row["status"]),
            str(row.get("success", "-")),
            str(row["steps"]),
            str(row["tokens"]),
            f"{row['runtime_s']:.1f}",
        )

    console.print(table)


@experiment_group.command("list")
def experiment_list() -> None:
    """List past experiments."""
    store = _get_store()
    experiments = store.list_experiments()

    if not experiments:
        console.print("[dim]No experiments found[/dim]")
        return

    table = Table(title="Experiments")
    table.add_column("ID", style="bold")
    table.add_column("Name")
    table.add_column("Runs")
    table.add_column("Status")
    table.add_column("Created")

    for exp in experiments:
        table.add_row(
            exp.id,
            exp.name,
            str(len(exp.run_ids)),
            exp.status,
            exp.created_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


# ======================================================================
# lab eval
# ======================================================================


@cli.command("eval")
@click.argument("agent_name")
@click.option("--task", required=True, help="Task ID to evaluate against.")
def eval_agent(agent_name: str, task: str) -> None:
    """Evaluate an agent against a task with validation."""
    from agentlab.evaluation.harness import EvalHarness

    store = _get_store()
    ensure_phoenix_tracing()

    try:
        config = store.load_agent(agent_name)
    except FileNotFoundError:
        console.print(f"[red]Agent '{agent_name}' not found[/red]")
        sys.exit(1)

    try:
        task_cfg = store.load_task(task)
    except FileNotFoundError:
        console.print(f"[red]Task '{task}' not found[/red]")
        sys.exit(1)

    harness = EvalHarness(store=store)
    console.print(f"[bold]Evaluating:[/bold] {agent_name} on {task}")

    run = _run_async(harness.evaluate(config, task_cfg))

    _print_run_summary(run)
    if run.metrics.success is not None:
        status = "[green]PASS[/green]" if run.metrics.success else "[red]FAIL[/red]"
        console.print(f"  Validation: {status}")
    if run.metrics.patch_size is not None:
        console.print(f"  Patch size: {run.metrics.patch_size} lines")


# ======================================================================
# lab compare
# ======================================================================


@cli.command("compare")
@click.argument("run_id_a")
@click.argument("run_id_b")
def compare(run_id_a: str, run_id_b: str) -> None:
    """Compare two runs side-by-side."""
    from agentlab.experiment.comparison import compare_runs

    store = _get_store()

    try:
        run_a = store.load_run(run_id_a)
        run_b = store.load_run(run_id_b)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    diff = compare_runs(run_a, run_b)

    table = Table(title=f"Comparison: {run_id_a} vs {run_id_b}")
    table.add_column("Metric", style="bold")
    table.add_column(f"Run A ({run_id_a[:8]})")
    table.add_column(f"Run B ({run_id_b[:8]})")
    table.add_column("Diff")
    table.add_column("% Change")

    for metric, values in diff.items():
        table.add_row(
            metric,
            str(values["run_a"]),
            str(values["run_b"]),
            str(values.get("diff", "-")),
            f"{values['pct_change']}%" if "pct_change" in values else "-",
        )

    console.print(table)


# ======================================================================
# lab ui
# ======================================================================


@cli.command("ui")
@click.option("--host", default="127.0.0.1", help="Host to bind to.")
@click.option("--port", default=8000, type=int, help="Port to bind to.")
def ui(host: str, port: int) -> None:
    """Launch the AgentLab web UI."""
    import uvicorn

    from agentlab.api.app import create_app

    store = _get_store()
    app = create_app(store=store)
    console.print(f"[bold]AgentLab UI[/bold] running at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


# ======================================================================
# Helpers
# ======================================================================


def _print_run_summary(run) -> None:
    console.print()
    if run.status == "completed":
        console.print(f"[green bold]Run completed[/green bold] — {run.id}")
    else:
        console.print(f"[red bold]Run failed[/red bold] — {run.id}")
        if run.error:
            console.print(f"[red]{run.error}[/red]")

    console.print(f"  Steps:   {run.metrics.steps}")
    console.print(f"  Tokens:  {run.metrics.tokens_used}")
    console.print(f"  Runtime: {run.metrics.runtime_seconds:.1f}s")
    if run.trace:
        last = run.trace[-1]
        output = last.result or last.thought or ""
        if output:
            console.print(f"  Output:  {output[:200]}")
