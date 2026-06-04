from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schemas import DateContext, PipelineStage, RunState, StageRecord


MEMORY_FILE = Path(__file__).with_name("training_plan_memory.json")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def empty_memory() -> dict[str, Any]:
    return {"runs": [], "records": [], "plans": []}


def _coerce_memory(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return empty_memory()
    data.setdefault("runs", [])
    data.setdefault("records", [])
    data.setdefault("plans", [])
    return data


def load_memory(memory_file: Path = MEMORY_FILE) -> dict[str, Any]:
    if not memory_file.exists():
        return empty_memory()
    with memory_file.open("r", encoding="utf-8") as f:
        return _coerce_memory(json.load(f))


def save_memory(memory: dict[str, Any], memory_file: Path = MEMORY_FILE) -> None:
    memory_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = memory_file.with_suffix(".tmp")
    with tmp_file.open("w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp_file.replace(memory_file)


def create_run(date_context: DateContext, initial_user_input: str = "", memory_file: Path = MEMORY_FILE) -> RunState:
    now = utc_now()
    run = RunState(
        run_id=new_id("run"),
        created_at=now,
        updated_at=now,
        status="active",
        current_stage="intake",
        date_context=date_context,
        accumulated_user_input=initial_user_input,
    )
    memory = load_memory(memory_file)
    memory["runs"].append(run.model_dump(mode="json"))
    save_memory(memory, memory_file)
    return run


def save_run(run: RunState, memory_file: Path = MEMORY_FILE) -> None:
    run.updated_at = utc_now()
    memory = load_memory(memory_file)
    run_data = run.model_dump(mode="json")
    for idx, existing in enumerate(memory["runs"]):
        if existing.get("run_id") == run.run_id:
            memory["runs"][idx] = run_data
            break
    else:
        memory["runs"].append(run_data)
    save_memory(memory, memory_file)


def get_run(run_id: str, memory_file: Path = MEMORY_FILE) -> RunState | None:
    memory = load_memory(memory_file)
    for run in memory["runs"]:
        if run.get("run_id") == run_id:
            return RunState.model_validate(run)
    return None


def get_latest_resumable_run(memory_file: Path = MEMORY_FILE) -> RunState | None:
    memory = load_memory(memory_file)
    candidates = [
        RunState.model_validate(run)
        for run in memory["runs"]
        if run.get("status") in {"active", "paused"}
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda run: run.updated_at, reverse=True)[0]


def remember_stage(
    run: RunState,
    stage: PipelineStage,
    source: dict[str, Any],
    data: dict[str, Any],
    memory_file: Path = MEMORY_FILE,
) -> StageRecord:
    record = StageRecord(
        id=new_id(stage),
        run_id=run.run_id,
        stage=stage,
        created_at=utc_now(),
        source=source,
        data=data,
    )
    memory = load_memory(memory_file)
    memory["records"].append(record.model_dump(mode="json"))
    run.stage_outputs[stage] = data
    run.records.append(record.id)
    run.updated_at = utc_now()
    run_data = run.model_dump(mode="json")
    for idx, existing in enumerate(memory["runs"]):
        if existing.get("run_id") == run.run_id:
            memory["runs"][idx] = run_data
            break
    else:
        memory["runs"].append(run_data)
    save_memory(memory, memory_file)
    return record


def remember_plan(run: RunState, plan: dict[str, Any], memory_file: Path = MEMORY_FILE) -> None:
    memory = load_memory(memory_file)
    plan_id = str(plan.get("plan_id") or new_id("plan"))
    memory["plans"].append(
        {
            "id": plan_id,
            "run_id": run.run_id,
            "created_at": utc_now(),
            "data": plan,
        }
    )
    run.final_plan_id = plan_id
    run.status = "completed"
    run.current_stage = "complete"
    run.updated_at = utc_now()
    run_data = run.model_dump(mode="json")
    for idx, existing in enumerate(memory["runs"]):
        if existing.get("run_id") == run.run_id:
            memory["runs"][idx] = run_data
            break
    else:
        memory["runs"].append(run_data)
    save_memory(memory, memory_file)

