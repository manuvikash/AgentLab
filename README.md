# AgentLab

A modular platform for building, experimenting with, evaluating, and deploying AI agents — especially software engineering agents.

## Overview

AgentLab provides interchangeable components (LLMs, context managers, loops, tools, sandboxes, prompts) that compose into agents. Run experiments across architectures, evaluate on SWE benchmarks, and compare performance across runs.

## Installation

```bash
pip install -e ".[dev]"
```

## Quick Start

### Define an agent

Create a YAML config in `agents/`:

```yaml
name: coding_agent
llm: openai
loop: react
context: sliding
tools:
  - filesystem
  - shell
sandbox: local
```

### Run an agent

```bash
lab run coding_agent
lab run coding_agent --task bug_fix_1
```

### Run an experiment

```bash
lab experiment run experiment.yaml
lab experiment results <experiment_id>
```

### Evaluate an agent

```bash
lab eval coding_agent --task bug_fix_1
```

### Compare runs

```bash
lab compare <run_id_1> <run_id_2>
```

### Inspect traces

```bash
lab replay <run_id>
```

## Observability (Phoenix)

To trace LLM calls and group each agent run under an OpenInference **AGENT** span in [Arize Phoenix](https://arize.com/docs/phoenix), use a **self-hosted** Phoenix instance ([self-hosting guide](https://arize.com/docs/phoenix/self-hosting)), then:

1. Install the optional extra: `pip install -e ".[phoenix]"`
2. Set environment variables (see `example.env`):
   - `AGENTLAB_PHOENIX_TRACING=1`
   - `PHOENIX_COLLECTOR_ENDPOINT` — your Phoenix OTLP endpoint (often `http://localhost:6006` for local Phoenix)
3. For self hosted, use `phoenix serve` to start the phoenix server

Tracing is initialized when you run `lab ui`, or when you run `lab run`, `lab experiment run`, or `lab eval` from the CLI. Open the Phoenix UI to browse traces.

## Web UI

AgentLab includes a full web UI for browsing agents, runs, tasks, experiments, and comparisons.

### Start the UI (server mode)

From the project root (with your virtualenv activated):

```bash
lab ui
```

Then open `http://127.0.0.1:8000` in your browser.  
FastAPI serves both the JSON API under `/api/*` and, if built, the static UI at `/`.

### Develop the UI (hot reload)

In one terminal, start the API server:

```bash
lab ui
```

In another terminal, run the Vite dev server from the `ui/` directory:

```bash
cd ui
npm install        # first time
npm run dev
```

Visit `http://127.0.0.1:5173`. The dev server proxies `/api/*` requests to `http://127.0.0.1:8000`.

### Build the UI for production

To build the React app into static assets:

```bash
cd ui
npm run build
```

This outputs to `ui/dist/`. On the next `lab ui` run, FastAPI will automatically serve `ui/dist/` at `/`.

## Architecture

```
Agent = LLM + Loop Controller + Context Manager + Tools + Sandbox + Prompts
```

Components are swappable modules registered in a global registry. Agents are defined as YAML configs that reference component names.

## Project Structure

```
agentlab/
  cli/          CLI entry points
  core/         Agent, Component interfaces, Registry
  components/   Built-in component implementations
  runtime/      Agent runner + trace recorder
  experiment/   Experiment engine + comparisons
  evaluation/   SWE harness, metrics, validators
  storage/      File-based run/experiment store
  models/       Pydantic data models
```

## License

MIT
