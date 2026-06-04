from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow `uv run python run.py` from this directory: package imports need the repo root on sys.path.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from multi_agent_training_planner.planner_agents import DEFAULT_MODEL
from multi_agent_training_planner.memory import MEMORY_FILE
from multi_agent_training_planner.orchestrator import (
    append_human_response,
    load_or_create_run,
    run_pipeline_until_pause_or_complete,
    summarize_run,
)


def read_multiline(prompt: str) -> str:
    print(prompt)
    print("Finish with an empty line.")
    lines: list[str] = []
    while True:
        try:
            line = input("> ")
        except EOFError:
            break
        if not line:
            break
        lines.append(line)
    return "\n".join(lines).strip()


def prompt_default(label: str, default: str) -> str:
    raw = input(f"{label} [{default}]: ").strip()
    return raw or default


def prompt_choice(label: str, options: list[tuple[str, str]]) -> str:
    print(label)
    for key, desc in options:
        print(f"  [{key}] {desc}")
    while True:
        choice = input("Enter choice: ").strip().lower()
        valid = {k for k, _ in options}
        if choice in valid:
            return choice
        print(f"Please enter one of: {', '.join(sorted(valid))}")


async def async_main() -> None:
    print("Multi-agent training planner (interactive)")
    mem_default = str(MEMORY_FILE)
    mem_raw = prompt_default("Memory JSON file", mem_default)
    memory_file = Path(mem_raw).expanduser()

    mode = prompt_choice(
        "How do you want to start?",
        [
            ("1", "Resume latest active/paused run"),
            ("2", "Start a new run"),
            ("3", "Resume a specific run id"),
        ],
    )

    run_id: str | None = None
    start_new = False
    build_date: str | None = None

    if mode == "1":
        pass
    elif mode == "2":
        start_new = True
        build_raw = input("Plan build date YYYY-MM-DD (blank = today in your timezone): ").strip()
        build_date = build_raw or None
    else:
        rid = input("Run id: ").strip()
        if not rid:
            print("Run id is required.")
            return
        run_id = rid

    model_default = DEFAULT_MODEL
    model = prompt_default("OpenAI model", model_default)

    initial_text = ""

    run = load_or_create_run(
        run_id=run_id,
        start_new=start_new,
        build_date=build_date,
        initial_user_input=initial_text,
        memory_file=memory_file,
    )

    if run.status == "paused":
        print(summarize_run(run))
        follow_up = read_multiline("\nAnswer the questions above so the same stage can continue:")
        append_human_response(run, follow_up, memory_file)
    elif not run.accumulated_user_input:
        first_brief = read_multiline(
            "Paste the athlete/race/training brief. Leave blank to let the intake agent ask for what it needs:"
        )
        append_human_response(run, first_brief, memory_file)

    try:
        run = await run_pipeline_until_pause_or_complete(run, model=model, memory_file=memory_file)
    except RuntimeError as exc:
        print(f"\nPlanner stopped: {exc}")
        print("Fix the configuration, then run again to resume from the same stage.")
        return

    print()
    print(summarize_run(run))
    print(f"Memory file: {memory_file}")


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
