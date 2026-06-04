from __future__ import annotations

from agents import Agent, ModelSettings

from .schemas import (
    FeasibilityOutput,
    FinalTrainingPlan,
    IntakeOutput,
    MacrocycleOutput,
    MesocycleOutput,
    RaceDemandsOutput,
    RiskAuditOutput,
    StravaAnalysisOutput,
    WeeklyPlanOutput,
    WorkoutDesignOutput,
)
from .strava_mcp import make_strava_mcp_tool


DEFAULT_MODEL = "gpt-4o-mini"

DATE_AWARENESS = """
Date awareness is mandatory.

Every output must reason from the supplied date_context:
- plan_build_date is the date the training plan is built from.
- race dates determine the available timeline and taper.
- never assume the plan starts on a different date unless the input explicitly says so.
- preserve explicit calendar dates in your structured output whenever the schema allows.
""".strip()


def _settings(temperature: float = 0.1) -> ModelSettings:
    return ModelSettings(temperature=temperature)


def make_intake_agent(model: str) -> Agent:
    return Agent(
        name="Training Intake Conversation Agent",
        model=model,
        model_settings=_settings(0.1),
        output_type=IntakeOutput,
        instructions=(
            f"{DATE_AWARENESS}\n\n"
            "You gather requirements for a running training plan. Extract athlete profile, races, "
            "availability, constraints, current fitness, injuries, preferences, strength work, and "
            "planning philosophy from the user's accumulated brief (including follow-up answers). "
            "Do not build a plan.\n\n"
            "Populate structured fields even when values are approximate: e.g. '45-60 km/week' -> set "
            "current_weekly_distance_km or typical_weekly_distance_km to a single plausible number "
            "(midpoint is fine) and add an assumption; '4-5 days/week' -> set runs_per_week and note the "
            "range in assumptions; standing commitments (e.g. Tuesday hill group) -> non_negotiables.\n\n"
            "If critical information is missing from the entire accumulated_user_input, set "
            "ready_for_analysis=false and use human_input with concise questions (or missing_information). "
            "Critical information: at least one race/goal with date or timeline, training load signal, "
            "schedule/availability signal, and injury/limitation status.\n\n"
            "Do NOT re-ask the same topic in new wording if accumulated_user_input already answers it "
            "(including prior turns). Prefer assumptions over follow-up questions.\n\n"
            "When those essentials are present anywhere in accumulated_user_input or in structured fields, "
            "set ready_for_analysis=true, human_input.required=false, missing_information=[], and move on.\n\n"
            "Treat as sufficient: weekly distance ranges, approximate days/week, 'no injuries' / none, "
            "and non-negotiable sessions as schedule constraints. If the build date is ambiguous, assume "
            "date_context.plan_build_date and note that in assumptions."
        ),
    )


def make_strava_analysis_agent(model: str) -> Agent:
    return Agent(
        name="Strava Training History Analysis Agent",
        model=model,
        model_settings=ModelSettings(temperature=0.1, parallel_tool_calls=False, tool_choice="auto"),
        tools=[make_strava_mcp_tool()],
        output_type=StravaAnalysisOutput,
        instructions=(
            f"{DATE_AWARENESS}\n\n"
            "Use the Strava MCP tools to analyze the athlete's real training history. Focus on current "
            "fitness, recent and sustainable volume, consistency, long runs, intensity distribution, "
            "training zones, recovery status, and red flags. Prefer compact structured insight over raw "
            "activity dumps. Relate recency windows to date_context.plan_build_date. If the MCP data "
            "does not contain enough information, explain what is missing in tool_notes and request "
            "human input only if planning cannot safely continue."
        ),
    )


def make_race_demands_agent(model: str) -> Agent:
    return Agent(
        name="Race Demands Agent",
        model=model,
        model_settings=_settings(0.1),
        output_type=RaceDemandsOutput,
        instructions=(
            f"{DATE_AWARENESS}\n\n"
            "Translate each race target into physiological and practical demands. Consider race distance, "
            "terrain, priority, goal time, climate, elevation, and the number of days and weeks until race "
            "day. Do not create a training plan; produce the requirements the plan must satisfy."
        ),
    )


def make_feasibility_agent(model: str) -> Agent:
    return Agent(
        name="Constraint And Feasibility Agent",
        model=model,
        model_settings=_settings(0.1),
        output_type=FeasibilityOutput,
        instructions=(
            f"{DATE_AWARENESS}\n\n"
            "Assess whether the user's goals, race timeline, current load, Strava-derived fitness, injury "
            "history, and availability can fit together safely. Be conservative. If the plan can proceed "
            "with assumptions, list them in recommendations. If a human decision is required before "
            "planning, set human_input.required=true with specific questions."
        ),
    )


def make_macrocycle_agent(model: str) -> Agent:
    return Agent(
        name="Macrocycle Planning Agent",
        model=model,
        model_settings=_settings(0.15),
        output_type=MacrocycleOutput,
        instructions=(
            f"{DATE_AWARENESS}\n\n"
            "Create dated week-level training phases from planning_start_date to the primary race or "
            "planning_end_date. Include base, build, specific preparation, cutback weeks, and taper as "
            "appropriate. Avoid aggressive volume jumps and keep week dates aligned to the supplied "
            "calendar."
        ),
    )


def make_mesocycle_agent(model: str) -> Agent:
    return Agent(
        name="Mesocycle Agent",
        model=model,
        model_settings=_settings(0.15),
        output_type=MesocycleOutput,
        instructions=(
            f"{DATE_AWARENESS}\n\n"
            "Group macrocycle weeks into dated 2-6 week blocks. Each block should have a clear focus, "
            "progression strategy, workout density, and recovery strategy. Do not redesign the macrocycle; "
            "organize it into coherent blocks."
        ),
    )


def make_weekly_plan_agent(model: str) -> Agent:
    return Agent(
        name="Weekly Planning Agent",
        model=model,
        model_settings=_settings(0.15),
        output_type=WeeklyPlanOutput,
        instructions=(
            f"{DATE_AWARENESS}\n\n"
            "Lay out every week as dated daily sessions. Respect unavailable days, preferred rest days, "
            "preferred long-run day, workout spacing, recovery after hard sessions, and race dates. Keep "
            "this as a weekly schedule with session types and targets; detailed workout steps come later."
        ),
    )


def make_workout_design_agent(model: str) -> Agent:
    return Agent(
        name="Workout Design Agent",
        model=model,
        model_settings=_settings(0.2),
        output_type=WorkoutDesignOutput,
        instructions=(
            f"{DATE_AWARENESS}\n\n"
            "Convert the weekly plan into detailed dated sessions. For workouts, include warmup, main set, "
            "cooldown, purpose, pace or HR targets when available, and execution notes. Keep easy and rest "
            "days simple. Do not change the calendar structure unless required for safety; note any changes."
        ),
    )


def make_risk_audit_agent(model: str) -> Agent:
    return Agent(
        name="Recovery And Risk Agent",
        model=model,
        model_settings=_settings(0.1),
        output_type=RiskAuditOutput,
        instructions=(
            f"{DATE_AWARENESS}\n\n"
            "Audit the drafted plan for overload, excessive intensity, poor recovery spacing, unsafe ramp "
            "rates, taper issues, schedule conflicts, and date-related mistakes. Be willing to approve with "
            "warnings for a POC, but flag anything that needs correction or human decision."
        ),
    )


def make_structured_output_agent(model: str) -> Agent:
    return Agent(
        name="Structured Output Agent",
        model=model,
        model_settings=_settings(0.05),
        output_type=FinalTrainingPlan,
        instructions=(
            f"{DATE_AWARENESS}\n\n"
            "Produce the final strict training plan JSON. Preserve the provided plan_id and run_id. Use the "
            "audited workout design as the source of truth. Include explicit metadata, date_context, athlete "
            "profile, race targets, weeks, sessions, assumptions, risk flags, validation warnings, and a next "
            "review prompt."
        ),
    )
