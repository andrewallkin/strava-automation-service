from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from agents import Runner

from .planner_agents import (
    DEFAULT_MODEL,
    make_feasibility_agent,
    make_intake_agent,
    make_macrocycle_agent,
    make_mesocycle_agent,
    make_race_demands_agent,
    make_risk_audit_agent,
    make_strava_analysis_agent,
    make_structured_output_agent,
    make_weekly_plan_agent,
    make_workout_design_agent,
)
from .memory import (
    MEMORY_FILE,
    create_run,
    get_latest_resumable_run,
    get_run,
    new_id,
    remember_plan,
    remember_stage,
    save_run,
    utc_now,
)
from .settings import get_planner_settings
from .schemas import (
    DateContext,
    DesignedWeek,
    FeasibilityOutput,
    FinalTrainingPlan,
    GoalRace,
    HumanInputRequest,
    IntakeOutput,
    MacrocycleOutput,
    MesocycleOutput,
    PipelineStage,
    RaceDateContext,
    RaceDemandsOutput,
    RiskAuditOutput,
    RunState,
    StravaAnalysisOutput,
    ValidationWarning,
    WeeklyPlanOutput,
    WorkoutDesignOutput,
)


STAGE_ORDER: list[PipelineStage] = [
    "intake",
    "strava_analysis",
    "race_demands",
    "feasibility",
    "macrocycle",
    "mesocycles",
    "weekly_plan",
    "workout_design",
    "risk_audit",
    "structured_output",
]


def next_stage(stage: PipelineStage) -> PipelineStage:
    if stage == "complete":
        return "complete"
    idx = STAGE_ORDER.index(stage)
    if idx == len(STAGE_ORDER) - 1:
        return "complete"
    return STAGE_ORDER[idx + 1]


def configure_openai_api_key() -> None:
    settings = get_planner_settings()
    if os.environ.get("OPENAI_API_KEY"):
        return
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
        return
    raise RuntimeError("OPENAI_API_KEY is not set in the environment and openai_api_key is empty in .env.")


def local_today(timezone_name: str) -> date:
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")
    return datetime.now(tz).date()


def make_initial_date_context(build_date: str | None = None) -> DateContext:
    settings = get_planner_settings()
    timezone_name = settings.timezone or "UTC"
    today = local_today(timezone_name)
    plan_build_date = build_date or today.isoformat()
    return DateContext(
        plan_build_date=plan_build_date,
        current_date=today.isoformat(),
        timezone=timezone_name,
        planning_start_date=plan_build_date,
    )


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def update_date_context_from_races(date_context: DateContext, races: list[GoalRace]) -> DateContext:
    build_date = parse_iso_date(date_context.plan_build_date)
    race_contexts: list[RaceDateContext] = []
    parsed_race_dates: list[date] = []
    notes = list(date_context.notes)

    for race in races:
        parsed_race_date = parse_iso_date(race.race_date)
        days_until_race = None
        weeks_until_race = None
        if parsed_race_date and build_date:
            days_until_race = (parsed_race_date - build_date).days
            weeks_until_race = round(days_until_race / 7, 1)
            parsed_race_dates.append(parsed_race_date)
        else:
            notes.append(f"Could not parse race date for {race.race_name or race.race_distance}: {race.race_date}")

        race_contexts.append(
            RaceDateContext(
                race_name=race.race_name,
                race_distance=race.race_distance,
                race_date=race.race_date,
                priority=race.priority,
                days_until_race=days_until_race,
                weeks_until_race=weeks_until_race,
            )
        )

    planning_end_date = max(parsed_race_dates).isoformat() if parsed_race_dates else date_context.planning_end_date
    return date_context.model_copy(
        update={
            "races": race_contexts,
            "planning_end_date": planning_end_date,
            "notes": notes,
        }
    )


def json_for_prompt(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def model_dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    raise TypeError(f"Cannot dump value of type {type(value)}")


def human_input_from_output(output: Any) -> HumanInputRequest:
    request = getattr(output, "human_input", None)
    if isinstance(request, HumanInputRequest):
        return request
    return HumanInputRequest(required=False)


def _text_suggests_weekly_volume_km(text: str) -> bool:
    return bool(re.search(r"\d+\s*(?:-\s*\d+)?\s*km\b|\bkm\b.*\d|weekly.*\d|\d+.*weekly", text, re.I))


def _text_suggests_run_schedule(text: str) -> bool:
    return bool(
        re.search(
            r"\b[1-7]\s*(?:-\s*[1-7])?\s*days?\b|\bruns?\s+per\s+week\b|\bdays?\s+(?:a\s+)?week\b|"
            r"\bmonday|tuesday|wednesday|thursday|friday|saturday|sunday\b",
            text,
            re.I,
        )
    )


def _text_suggests_no_injuries(text: str) -> bool:
    return bool(re.search(r"no\s+injur|without\s+injur|injur(y|ies)[:\s]+none|\bnone\b.*limitation", text, re.I))


def intake_should_proceed_without_followup(intake: IntakeOutput, accumulated_user_input: str) -> bool:
    """True when essentials are present in structured output and/or the user's free-text brief."""
    if not intake.goal_races:
        return False
    text = accumulated_user_input or ""
    fb = intake.fitness_background
    has_volume = (
        fb.current_weekly_distance_km is not None
        or fb.typical_weekly_distance_km is not None
        or _text_suggests_weekly_volume_km(text)
    )
    c = intake.constraints
    has_schedule = (
        c.runs_per_week is not None
        or bool(c.preferred_run_days)
        or bool(c.unavailable_days)
        or bool(c.non_negotiables)
        or bool(c.preferred_workout_days)
        or _text_suggests_run_schedule(text)
    )
    hp = intake.health_and_preferences
    injuries_addressed = (
        not hp.current_injuries and not hp.recent_injuries and not hp.medical_limitations
    ) or _text_suggests_no_injuries(text)
    return bool(has_volume and has_schedule and injuries_addressed)


def coerce_intake_when_complete_enough(intake: IntakeOutput, accumulated_user_input: str) -> IntakeOutput:
    if intake.ready_for_analysis or not intake_should_proceed_without_followup(intake, accumulated_user_input):
        return intake
    assumptions = list(intake.assumptions)
    note = "Intake essentials were inferred from structured fields and/or accumulated user text; continuing the pipeline."
    if note not in assumptions:
        assumptions.append(note)
    return intake.model_copy(
        update={
            "ready_for_analysis": True,
            "missing_information": [],
            "human_input": HumanInputRequest(required=False, reason="", questions=[]),
            "assumptions": assumptions,
        }
    )


def pause_for_human(run: RunState, stage: PipelineStage, request: HumanInputRequest, memory_file: Path) -> None:
    run.status = "paused"
    run.current_stage = stage
    run.pending_questions = request.questions
    save_run(run, memory_file)


def mark_stage_complete(run: RunState, stage: PipelineStage, memory_file: Path) -> None:
    run.status = "active"
    run.current_stage = next_stage(stage)
    run.pending_questions = []
    save_run(run, memory_file)


def hard_session(session_type: str) -> bool:
    return session_type in {"steady", "tempo", "threshold", "intervals", "long_run", "race"}


def deterministic_validation(workout_design: WorkoutDesignOutput, intake: IntakeOutput | None) -> list[ValidationWarning]:
    warnings: list[ValidationWarning] = []
    unavailable_days = {day.lower() for day in (intake.constraints.unavailable_days if intake else [])}
    previous_volume: float | None = None
    previous_hard_date: date | None = None

    for week in workout_design.weeks:
        volume = week.target_volume_km
        if volume is not None and previous_volume and previous_volume > 0:
            jump = (volume - previous_volume) / previous_volume
            if jump > 0.15:
                warnings.append(
                    ValidationWarning(
                        code="volume_jump",
                        message=f"Week {week.week_number} volume increases by {jump:.0%}, above the 15% POC threshold.",
                        week_number=week.week_number,
                    )
                )
        if volume is not None:
            previous_volume = volume

        for session in week.sessions:
            session_date = parse_iso_date(session.date)
            if session.day_of_week.lower() in unavailable_days and session.session_type != "rest":
                warnings.append(
                    ValidationWarning(
                        code="unavailable_day",
                        message=f"Session scheduled on unavailable day {session.day_of_week}.",
                        week_number=week.week_number,
                        date=session.date,
                    )
                )
            if hard_session(session.session_type) and session_date:
                if previous_hard_date and session_date - previous_hard_date <= timedelta(days=1):
                    warnings.append(
                        ValidationWarning(
                            code="consecutive_hard_days",
                            message="Hard sessions appear on consecutive days.",
                            week_number=week.week_number,
                            date=session.date,
                        )
                    )
                previous_hard_date = session_date

    if len(workout_design.weeks) >= 8:
        final_weeks = workout_design.weeks[-2:]
        earlier = [week.target_volume_km for week in workout_design.weeks[:-2] if week.target_volume_km is not None]
        final = [week.target_volume_km for week in final_weeks if week.target_volume_km is not None]
        if earlier and final and max(final) >= max(earlier):
            warnings.append(
                ValidationWarning(
                    code="missing_taper",
                    message="Final two weeks do not show a clear volume reduction versus earlier peak volume.",
                    week_number=final_weeks[0].week_number,
                )
            )

    return warnings


def base_payload(run: RunState, exclude_stage: PipelineStage | None = None) -> dict[str, Any]:
    stage_outputs = dict(run.stage_outputs)
    if exclude_stage:
        stage_outputs.pop(exclude_stage, None)
    return {
        "run_id": run.run_id,
        "date_context": run.date_context.model_dump(mode="json"),
        "accumulated_user_input": run.accumulated_user_input,
        "stage_outputs": stage_outputs,
        "pending_questions": run.pending_questions,
    }


async def execute_stage(run: RunState, stage: PipelineStage, model: str) -> Any:
    payload = base_payload(run, exclude_stage=stage)

    if stage == "intake":
        agent = make_intake_agent(model)
        result = await Runner.run(agent, input=json_for_prompt(payload))
        return result.final_output_as(IntakeOutput)

    if stage == "strava_analysis":
        agent = make_strava_analysis_agent(model)
        result = await Runner.run(agent, input=json_for_prompt(payload))
        return result.final_output_as(StravaAnalysisOutput)

    if stage == "race_demands":
        agent = make_race_demands_agent(model)
        result = await Runner.run(agent, input=json_for_prompt(payload))
        return result.final_output_as(RaceDemandsOutput)

    if stage == "feasibility":
        agent = make_feasibility_agent(model)
        result = await Runner.run(agent, input=json_for_prompt(payload))
        return result.final_output_as(FeasibilityOutput)

    if stage == "macrocycle":
        agent = make_macrocycle_agent(model)
        result = await Runner.run(agent, input=json_for_prompt(payload))
        return result.final_output_as(MacrocycleOutput)

    if stage == "mesocycles":
        agent = make_mesocycle_agent(model)
        result = await Runner.run(agent, input=json_for_prompt(payload))
        return result.final_output_as(MesocycleOutput)

    if stage == "weekly_plan":
        agent = make_weekly_plan_agent(model)
        result = await Runner.run(agent, input=json_for_prompt(payload))
        return result.final_output_as(WeeklyPlanOutput)

    if stage == "workout_design":
        agent = make_workout_design_agent(model)
        result = await Runner.run(agent, input=json_for_prompt(payload))
        return result.final_output_as(WorkoutDesignOutput)

    if stage == "risk_audit":
        agent = make_risk_audit_agent(model)
        result = await Runner.run(agent, input=json_for_prompt(payload))
        return result.final_output_as(RiskAuditOutput)

    if stage == "structured_output":
        agent = make_structured_output_agent(model)
        payload["plan_id"] = new_id("plan")
        payload["created_at"] = utc_now()
        result = await Runner.run(agent, input=json_for_prompt(payload))
        return result.final_output_as(FinalTrainingPlan)

    raise ValueError(f"Unsupported pipeline stage: {stage}")


def get_intake(run: RunState) -> IntakeOutput | None:
    data = run.stage_outputs.get("intake")
    return IntakeOutput.model_validate(data) if data else None


def merge_validation_warnings(
    final_plan: FinalTrainingPlan,
    risk_audit: RiskAuditOutput | None,
    workout_design_data: dict[str, Any] | None,
) -> FinalTrainingPlan:
    existing = {(warning.code, warning.week_number, warning.date, warning.message) for warning in final_plan.validation_warnings}
    merged = list(final_plan.validation_warnings)
    if workout_design_data:
        for warning_data in workout_design_data.get("validation_warnings", []):
            warning = ValidationWarning.model_validate(warning_data)
            key = (warning.code, warning.week_number, warning.date, warning.message)
            if key not in existing:
                merged.append(warning)
                existing.add(key)
    if risk_audit:
        for warning in risk_audit.validation_warnings:
            key = (warning.code, warning.week_number, warning.date, warning.message)
            if key not in existing:
                merged.append(warning)
                existing.add(key)
    return final_plan.model_copy(update={"validation_warnings": merged})


async def run_pipeline_until_pause_or_complete(
    run: RunState,
    model: str = DEFAULT_MODEL,
    memory_file: Path = MEMORY_FILE,
) -> RunState:
    configure_openai_api_key()

    while run.current_stage != "complete":
        stage = run.current_stage
        output = await execute_stage(run, stage, model)
        output_data = model_dump(output)

        if stage == "intake":
            intake = IntakeOutput.model_validate(output_data)
            run.date_context = update_date_context_from_races(run.date_context, intake.goal_races)
            intake = coerce_intake_when_complete_enough(intake, run.accumulated_user_input)
            output_data = intake.model_dump(mode="json")

        if stage == "workout_design":
            intake = get_intake(run)
            workout_design = WorkoutDesignOutput.model_validate(output_data)
            warnings = deterministic_validation(workout_design, intake)
            output_data["validation_warnings"] = [warning.model_dump(mode="json") for warning in warnings]

        remember_stage(run, stage, base_payload(run, exclude_stage=stage), output_data, memory_file)

        if stage == "intake":
            intake_final = IntakeOutput.model_validate(output_data)
            request = human_input_from_output(intake_final)
        else:
            request = human_input_from_output(output)

        if stage == "intake" and not intake_final.ready_for_analysis:
            request.required = True
            if not request.questions:
                request.questions = list(intake_final.missing_information)
            request.reason = request.reason or "The intake profile is incomplete."

        if request.required:
            pause_for_human(run, stage, request, memory_file)
            return run

        if stage == "structured_output":
            risk_data = run.stage_outputs.get("risk_audit")
            risk_audit = RiskAuditOutput.model_validate(risk_data) if risk_data else None
            final_plan = merge_validation_warnings(
                FinalTrainingPlan.model_validate(output_data),
                risk_audit,
                run.stage_outputs.get("workout_design"),
            )
            remember_plan(run, final_plan.model_dump(mode="json"), memory_file)
            return run

        if stage == "workout_design":
            run.stage_outputs[stage] = output_data

        mark_stage_complete(run, stage, memory_file)

    return run


def load_or_create_run(
    *,
    run_id: str | None = None,
    start_new: bool = False,
    build_date: str | None = None,
    initial_user_input: str = "",
    memory_file: Path = MEMORY_FILE,
) -> RunState:
    if run_id:
        run = get_run(run_id, memory_file)
        if not run:
            raise RuntimeError(f"No run found with id {run_id}")
        return run

    if not start_new:
        existing = get_latest_resumable_run(memory_file)
        if existing:
            return existing

    return create_run(make_initial_date_context(build_date), initial_user_input, memory_file)


def append_human_response(run: RunState, response: str, memory_file: Path = MEMORY_FILE) -> None:
    if response.strip():
        separator = "\n\n" if run.accumulated_user_input else ""
        run.accumulated_user_input = f"{run.accumulated_user_input}{separator}{response.strip()}"
    run.status = "active"
    run.pending_questions = []
    save_run(run, memory_file)


def summarize_run(run: RunState) -> str:
    if run.status == "paused":
        questions = "\n".join(f"- {question}" for question in run.pending_questions)
        return f"Run {run.run_id} paused at {run.current_stage}.\n\nQuestions:\n{questions}"
    if run.status == "completed":
        return f"Run {run.run_id} completed. Final plan: {run.final_plan_id}"
    return f"Run {run.run_id} status: {run.status}, stage: {run.current_stage}"

