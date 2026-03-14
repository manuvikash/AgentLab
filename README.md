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
