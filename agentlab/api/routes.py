"""API routes for AgentLab."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

import agentlab.components  # noqa: F401
from agentlab.core.registry import get_registry
from agentlab.experiment.comparison import compare_runs
from agentlab.experiment.engine import ExperimentEngine
from agentlab.models.schemas import (
    AgentConfig,
    ExperimentConfig,
    ExperimentRecord,
    TaskConfig,
)
from agentlab.storage.store import Store

router = APIRouter(prefix="/api")

_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store(root=Path.cwd())
    return _store


def set_store(store: Store) -> None:
    global _store
    _store = store


# ---- Agents ----


@router.get("/agents")
def list_agents():
    return [a.model_dump() for a in get_store().list_agents()]


@router.get("/agents/{name}")
def get_agent(name: str):
    try:
        return get_store().load_agent(name).model_dump()
    except FileNotFoundError:
        raise HTTPException(404, f"Agent '{name}' not found")


@router.post("/agents", status_code=201)
def create_agent(config: AgentConfig):
    get_store().save_agent(config)
    return config.model_dump()


@router.put("/agents/{name}")
def update_agent(name: str, config: AgentConfig):
    store = get_store()
    if name != config.name:
        store.delete_agent(name)
    store.save_agent(config)
    return config.model_dump()


@router.delete("/agents/{name}", status_code=204)
def delete_agent(name: str):
    get_store().delete_agent(name)


# ---- Runs ----


@router.get("/runs")
def list_runs():
    runs = get_store().list_runs()
    return [r.model_dump(exclude={"trace"}) for r in runs]


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    try:
        return get_store().load_run(run_id).model_dump()
    except FileNotFoundError:
        raise HTTPException(404, f"Run '{run_id}' not found")


@router.get("/runs/{run_id}/trace")
def get_run_trace(run_id: str):
    try:
        run = get_store().load_run(run_id)
        return [e.model_dump() for e in run.trace]
    except FileNotFoundError:
        raise HTTPException(404, f"Run '{run_id}' not found")


@router.get("/runs/{run_id}/metrics")
def get_run_metrics(run_id: str):
    try:
        run = get_store().load_run(run_id)
        return run.metrics.model_dump()
    except FileNotFoundError:
        raise HTTPException(404, f"Run '{run_id}' not found")


@router.delete("/runs/{run_id}", status_code=204)
def delete_run(run_id: str):
    get_store().delete_run(run_id)


# ---- Experiments ----


@router.get("/experiments")
def list_experiments():
    return [e.model_dump() for e in get_store().list_experiments()]


@router.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: str):
    try:
        exp = get_store().load_experiment(experiment_id)
        result = exp.model_dump()
        runs = []
        for rid in exp.run_ids:
            try:
                r = get_store().load_run(rid)
                runs.append(r.model_dump(exclude={"trace"}))
            except FileNotFoundError:
                pass
        result["runs"] = runs
        return result
    except FileNotFoundError:
        raise HTTPException(404, f"Experiment '{experiment_id}' not found")


@router.post("/experiments", status_code=201)
def create_experiment(config: ExperimentConfig):
    record = ExperimentRecord(name=config.name, config=config)
    get_store().save_experiment(record)
    return record.model_dump()


@router.post("/experiments/{experiment_id}/run", status_code=202)
async def run_experiment(experiment_id: str):
    """Trigger execution of a saved experiment in the background."""
    store = get_store()
    try:
        exp = store.load_experiment(experiment_id)
    except FileNotFoundError:
        raise HTTPException(404, f"Experiment '{experiment_id}' not found")

    if exp.status == "running":
        raise HTTPException(409, "Experiment is already running")

    if not exp.config:
        raise HTTPException(400, "Experiment has no configuration stored")

    async def _bg():
        engine = ExperimentEngine(store=store)
        try:
            await engine.run_by_id(experiment_id)
        except Exception:
            logger.exception("Background experiment run failed: %s", experiment_id)

    asyncio.create_task(_bg())
    return {"id": experiment_id, "status": "running"}


@router.delete("/experiments/{experiment_id}", status_code=204)
def delete_experiment(experiment_id: str):
    get_store().delete_experiment(experiment_id)


# ---- Tasks ----


@router.get("/tasks")
def list_tasks():
    return [t.model_dump() for t in get_store().list_tasks()]


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    try:
        return get_store().load_task(task_id).model_dump()
    except FileNotFoundError:
        raise HTTPException(404, f"Task '{task_id}' not found")


@router.post("/tasks", status_code=201)
def create_task(task: TaskConfig):
    get_store().save_task(task)
    return task.model_dump()


@router.put("/tasks/{task_id}")
def update_task(task_id: str, task: TaskConfig):
    store = get_store()
    if task_id != task.id:
        store.delete_task(task_id)
    store.save_task(task)
    return task.model_dump()


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: str):
    get_store().delete_task(task_id)


# ---- Components ----


@router.get("/components")
def list_components():
    return get_registry().list_components()


@router.get("/components/{component_type}")
def list_components_by_type(component_type: str):
    return get_registry().list_components(component_type)


# ---- Compare ----


@router.get("/compare/{run_a}/{run_b}")
def compare(run_a: str, run_b: str):
    store = get_store()
    try:
        a = store.load_run(run_a)
        b = store.load_run(run_b)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    return compare_runs(a, b)
