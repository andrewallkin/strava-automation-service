# Multi-Agent Training Planner POC

This directory contains a script-based version of `training_plan_multi_agent.ipynb`, expanded from `multi_agent_training_planner.md`.

It is still a proof of concept. The system runs a dated, checkpointed multi-agent pipeline and stores all state in `training_plan_memory.json`.

## Run

Run inside Docker only:

```sh
docker compose run --rm -v "$PWD:/workspace" -w /workspace api python -m multi_agent_training_planner.run
```

Start a new run with an explicit build date:

```sh
docker compose run --rm -v "$PWD:/workspace" -w /workspace api python -m multi_agent_training_planner.run --new --build-date 2026-05-11
```

Provide the initial brief non-interactively:

```sh
docker compose run --rm -v "$PWD:/workspace" -w /workspace api python -m multi_agent_training_planner.run --new --brief "I am training for Cape Town Marathon on 2026-10-18..."
```

If a stage needs more human input, the script saves the run as paused. Run the same command again to resume the latest paused run, or pass `--run-id`.

## Strava MCP

The Strava analysis agent uses the same MCP configuration as `backend/app/services/coach_openai_service.py`:

- `server_label`: `Strava_MCP`
- `server_description`: `Strava MCP Server`
- `server_url`: `settings.mcp_server_url`
- bearer header from `settings.strava_mcp_bearer`
- the same `ALLOWED_MCP_TOOLS`
- `require_approval`: `never`

No file-search tool is created in this POC.

## Pipeline

The pipeline stages are:

1. Intake / conversation
2. Strava analysis
3. Race demands
4. Constraint and feasibility
5. Macrocycle
6. Mesocycles
7. Weekly plan
8. Workout design
9. Recovery and risk audit
10. Structured output

Every stage receives the same `DateContext`, including the original plan build date, current date, race dates, and computed time until each race. On resume, the original plan build date is preserved.

