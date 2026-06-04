from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


PlanStatus = Literal["active", "paused", "completed", "failed"]
PipelineStage = Literal[
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
    "complete",
]


class RaceDateContext(BaseModel):
    race_name: str | None = None
    race_distance: str
    race_date: str
    priority: Literal["A", "B", "C", "unknown"] = "unknown"
    days_until_race: int | None = None
    weeks_until_race: float | None = None


class DateContext(BaseModel):
    plan_build_date: str = Field(description="Date the plan is being built from, in ISO date format.")
    current_date: str = Field(description="Runtime current date in ISO date format.")
    timezone: str = "UTC"
    planning_start_date: str
    planning_end_date: str | None = None
    races: list[RaceDateContext] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class HumanInputRequest(BaseModel):
    required: bool = False
    reason: str = ""
    questions: list[str] = Field(default_factory=list)


class TrainingZone(BaseModel):
    name: str
    target: str
    notes: str | None = None


class GoalRace(BaseModel):
    race_name: str | None = None
    race_distance: str
    race_date: str
    goal_time: str | None = None
    terrain: str | None = None
    elevation_profile: str | None = None
    expected_conditions: str | None = None
    priority: Literal["A", "B", "C", "unknown"] = "unknown"
    goal: str | None = None


class AthleteProfile(BaseModel):
    athlete_name: str | None = None
    age: int | None = Field(default=None, ge=1, le=120)
    sex: str | None = None
    height: str | None = None
    weight: str | None = None
    experience_level: Literal["beginner", "returning", "recreational", "intermediate", "advanced", "unknown"] = (
        "unknown"
    )
    years_running_consistently: str | None = None
    current_training_consistency: str | None = None


class TrainingConstraints(BaseModel):
    runs_per_week: int | None = Field(default=None, ge=1, le=7)
    preferred_run_days: list[str] = Field(default_factory=list)
    preferred_workout_days: list[str] = Field(default_factory=list)
    preferred_rest_days: list[str] = Field(default_factory=list)
    unavailable_days: list[str] = Field(default_factory=list)
    non_negotiables: list[str] = Field(default_factory=list)
    preferred_long_run_day: str | None = None
    max_weekday_duration_minutes: int | None = Field(default=None, ge=0)
    max_weekend_duration_minutes: int | None = Field(default=None, ge=0)
    travel_or_life_constraints: list[str] = Field(default_factory=list)


class FitnessBackground(BaseModel):
    current_weekly_distance_km: float | None = Field(default=None, ge=0)
    typical_weekly_distance_km: float | None = Field(default=None, ge=0)
    recent_long_run_km: float | None = Field(default=None, ge=0)
    longest_recent_run_km: float | None = Field(default=None, ge=0)
    recent_race_results: list[str] = Field(default_factory=list)
    estimated_threshold_pace: str | None = None
    estimated_5k_pace: str | None = None
    estimated_marathon_pace: str | None = None
    easy_pace_or_hr: str | None = None


class HealthAndPreferences(BaseModel):
    current_injuries: list[str] = Field(default_factory=list)
    recent_injuries: list[str] = Field(default_factory=list)
    chronic_issues: list[str] = Field(default_factory=list)
    medical_limitations: list[str] = Field(default_factory=list)
    sleep_recovery_stress_notes: list[str] = Field(default_factory=list)
    training_preferences: list[str] = Field(default_factory=list)
    strength_training: list[str] = Field(default_factory=list)
    cross_training: list[str] = Field(default_factory=list)
    planning_philosophy: list[str] = Field(default_factory=list)


class IntakeOutput(BaseModel):
    athlete_profile: AthleteProfile
    goal_races: list[GoalRace] = Field(default_factory=list)
    constraints: TrainingConstraints
    fitness_background: FitnessBackground
    health_and_preferences: HealthAndPreferences
    date_notes: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    human_input: HumanInputRequest = Field(default_factory=HumanInputRequest)
    ready_for_analysis: bool


class StravaAnalysisOutput(BaseModel):
    analysis_summary: str
    data_window: str | None = None
    current_estimated_fitness: str | None = None
    sustainable_weekly_volume_km: float | None = Field(default=None, ge=0)
    recent_weekly_volume_km: float | None = Field(default=None, ge=0)
    weekly_volume_trend: str | None = None
    intensity_distribution: str | None = None
    long_run_history: str | None = None
    elevation_exposure: str | None = None
    training_zones: list[TrainingZone] = Field(default_factory=list)
    consistency_notes: list[str] = Field(default_factory=list)
    fatigue_or_recovery_notes: list[str] = Field(default_factory=list)
    risk_indicators: list[str] = Field(default_factory=list)
    recommended_starting_load: str | None = None
    tool_notes: list[str] = Field(default_factory=list)
    human_input: HumanInputRequest = Field(default_factory=HumanInputRequest)


class RaceDemand(BaseModel):
    race_name: str | None = None
    race_distance: str
    race_date: str
    days_until_race: int | None = None
    weeks_until_race: float | None = None
    energy_systems: list[str] = Field(default_factory=list)
    durability_needs: list[str] = Field(default_factory=list)
    specificity_needs: list[str] = Field(default_factory=list)
    peak_volume_range_km: str | None = None
    long_run_needs: str | None = None
    terrain_and_climate_notes: list[str] = Field(default_factory=list)


class RaceDemandsOutput(BaseModel):
    demands: list[RaceDemand]
    priority_notes: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class FeasibilityOutput(BaseModel):
    feasible: bool
    summary: str
    goal_adjustment_recommendations: list[str] = Field(default_factory=list)
    schedule_conflicts: list[str] = Field(default_factory=list)
    load_risks: list[str] = Field(default_factory=list)
    required_human_decisions: list[str] = Field(default_factory=list)
    human_input: HumanInputRequest = Field(default_factory=HumanInputRequest)


class MacrocycleWeek(BaseModel):
    week_number: int = Field(ge=1)
    start_date: str
    end_date: str
    phase: str
    focus: str
    target_volume_km: float | None = Field(default=None, ge=0)
    long_run_target_km: float | None = Field(default=None, ge=0)
    quality_focus: list[str] = Field(default_factory=list)
    is_cutback_week: bool = False
    is_taper_week: bool = False


class MacrocycleOutput(BaseModel):
    plan_start_date: str
    plan_end_date: str | None = None
    total_weeks: int = Field(ge=1)
    phases: list[str] = Field(default_factory=list)
    weeks: list[MacrocycleWeek]
    assumptions: list[str] = Field(default_factory=list)


class MesocycleBlock(BaseModel):
    block_number: int = Field(ge=1)
    start_week: int = Field(ge=1)
    end_week: int = Field(ge=1)
    start_date: str
    end_date: str
    focus: str
    progression_strategy: str
    workout_density: str
    recovery_strategy: str


class MesocycleOutput(BaseModel):
    blocks: list[MesocycleBlock]
    notes: list[str] = Field(default_factory=list)


class PlannedDay(BaseModel):
    date: str
    day_of_week: str
    session_type: Literal[
        "rest",
        "easy",
        "recovery",
        "steady",
        "tempo",
        "threshold",
        "intervals",
        "long_run",
        "race",
        "strength",
        "mobility",
        "cross_training",
    ]
    distance_km: float | None = Field(default=None, ge=0)
    duration_minutes: int | None = Field(default=None, ge=0)
    intensity: str
    purpose: str
    constraints_notes: list[str] = Field(default_factory=list)


class PlannedWeek(BaseModel):
    week_number: int = Field(ge=1)
    start_date: str
    end_date: str
    focus: str
    target_volume_km: float | None = Field(default=None, ge=0)
    days: list[PlannedDay]
    coach_notes: list[str] = Field(default_factory=list)


class WeeklyPlanOutput(BaseModel):
    weeks: list[PlannedWeek]
    schedule_notes: list[str] = Field(default_factory=list)


class WorkoutStep(BaseModel):
    label: str
    duration_minutes: int | None = Field(default=None, ge=0)
    distance_km: float | None = Field(default=None, ge=0)
    target: str | None = None
    notes: str | None = None


class DesignedSession(PlannedDay):
    warmup: list[WorkoutStep] = Field(default_factory=list)
    main_set: list[WorkoutStep] = Field(default_factory=list)
    cooldown: list[WorkoutStep] = Field(default_factory=list)
    pace_target: str | None = None
    heart_rate_target: str | None = None
    execution_notes: list[str] = Field(default_factory=list)


class DesignedWeek(BaseModel):
    week_number: int = Field(ge=1)
    start_date: str
    end_date: str
    focus: str
    target_volume_km: float | None = Field(default=None, ge=0)
    sessions: list[DesignedSession]
    coach_notes: list[str] = Field(default_factory=list)


class WorkoutDesignOutput(BaseModel):
    weeks: list[DesignedWeek]
    prescription_notes: list[str] = Field(default_factory=list)


class ValidationWarning(BaseModel):
    code: str
    severity: Literal["info", "warning", "error"] = "warning"
    message: str
    week_number: int | None = None
    date: str | None = None


class RiskAuditOutput(BaseModel):
    approved: bool
    summary: str
    risk_flags: list[str] = Field(default_factory=list)
    recommended_changes: list[str] = Field(default_factory=list)
    validation_warnings: list[ValidationWarning] = Field(default_factory=list)
    human_input: HumanInputRequest = Field(default_factory=HumanInputRequest)


class FinalTrainingPlan(BaseModel):
    plan_id: str
    run_id: str
    created_at: str
    date_context: DateContext
    athlete_profile: AthleteProfile
    race_targets: list[GoalRace]
    training_zones: list[TrainingZone] = Field(default_factory=list)
    goal_summary: str
    plan_weeks: int = Field(ge=1)
    weeks: list[DesignedWeek]
    assumptions: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    validation_warnings: list[ValidationWarning] = Field(default_factory=list)
    next_review_prompt: str


class StageRecord(BaseModel):
    id: str
    run_id: str
    stage: PipelineStage
    created_at: str
    source: dict
    data: dict


class RunState(BaseModel):
    run_id: str
    created_at: str
    updated_at: str
    status: PlanStatus
    current_stage: PipelineStage
    date_context: DateContext
    accumulated_user_input: str = ""
    pending_questions: list[str] = Field(default_factory=list)
    stage_outputs: dict[str, dict] = Field(default_factory=dict)
    records: list[str] = Field(default_factory=list)
    final_plan_id: str | None = None

