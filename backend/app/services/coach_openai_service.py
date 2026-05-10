from __future__ import annotations

from typing import Any

from agents import Agent, FileSearchTool, HostedMCPTool, ModelSettings, Runner
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User, UserCoachSettings
from app.services.openai_credential_service import get_openai_api_key_for_user


def make_user_input_item(text: str) -> dict[str, Any]:
    return {
        "role": "user",
        "content": [{"type": "input_text", "text": text}],
    }


ALLOWED_MCP_TOOLS = [
    "get_athlete_profile",
    "get_heart_rate_zones",
    "search_activities",
    "list_recent_runs",
    "find_activity_by_date",
    "find_similar_runs",
    "get_activity_summary",
    "get_activity_full_details",
    "classify_workout_type",
    "get_activity_laps",
    "analyze_intervals",
    "compare_laps_within_activity",
    "get_warmup_cooldown_quality",
    "get_activity_splits",
    "analyze_pacing",
    "analyze_grade_adjusted_pace",
    "get_activity_hr_zone_distribution",
    "analyze_hr_decoupling",
    "get_period_hr_zone_distribution",
    "validate_hr_zones",
    "analyze_cadence",
    "get_cadence_trend",
    "get_elevation_profile_summary",
    "get_activity_best_efforts",
    "track_best_effort_progression",
    "find_pr_activities",
    "get_weekly_summary",
    "get_monthly_summary",
    "get_period_summary",
    "get_volume_trend",
    "get_intensity_distribution",
    "get_long_run_progression",
    "get_pace_at_distance_progression",
    "compare_activities",
    "compare_periods",
    "compare_to_similar_recent_runs",
    "get_recovery_status",
    "compute_acute_chronic_ratio",
    "detect_training_red_flags",
    "get_shoe_mileage",
    "get_athlete_stats",
    "check_data_availability",
]


def _json_safe(v: Any) -> Any:
    if isinstance(v, dict):
        return {str(k): _json_safe(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_json_safe(i) for i in v]
    if isinstance(v, tuple):
        return [_json_safe(i) for i in v]
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if hasattr(v, "model_dump"):
        return _json_safe(v.model_dump())
    return str(v)


def _prepare_history_for_request(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        role = item.get("role")
        if item_type == "mcp_list_tools":
            continue
        if role in {"user", "assistant", "system", "developer"}:
            prepared.append(item)
            continue
        if item_type == "message":
            prepared.append(item)
    return prepared


class CoachOpenAIService:
    async def run_turn(
        self,
        db: Session,
        user: User,
        coach_settings: UserCoachSettings,
        history: list[dict[str, Any]],
        user_message: str,
    ) -> tuple[str, list[dict[str, Any]]]:
        api_key = get_openai_api_key_for_user(db, user)
        if not api_key:
            raise ValueError("OpenAI API key is not configured")
        settings = get_settings()

        user_item = make_user_input_item(user_message)
        run_input = _prepare_history_for_request(history)
        run_input.append(user_item)

        base_instructions = coach_settings.agent_instructions.strip()
        if base_instructions:
            instructions = f"You are {coach_settings.agent_name.strip()}.\n\n{base_instructions}"
        else:
            instructions = f"You are {coach_settings.agent_name.strip()}."

        tools: list[Any] = []
        if coach_settings.vector_store_id:
            tools.append(FileSearchTool(vector_store_ids=[coach_settings.vector_store_id]))

        if settings.mcp_server_url and settings.strava_mcp_bearer:
            tools.append(
                HostedMCPTool(
                    tool_config={
                        "type": "mcp",
                        "server_label": "Strava_MCP",
                        "server_url": settings.mcp_server_url,
                        "server_description": "Strava MCP Server",
                        "headers": {"Authorization": f"Bearer {settings.strava_mcp_bearer}"},
                        "allowed_tools": ALLOWED_MCP_TOOLS,
                        "require_approval": "never",
                    }
                )
            )

        agent = Agent(
            name=coach_settings.agent_name.strip() or "Coach",
            instructions=instructions,
            model=coach_settings.openai_model,
            tools=tools,
            model_settings=ModelSettings(parallel_tool_calls=False, tool_choice="auto"),
        )

        result = await Runner.run(agent, input=run_input)
        output_items = [_json_safe(item.to_input_item()) for item in result.new_items]
        response_text = result.final_output_as(str).strip()
        if not response_text:
            response_text = "I couldn't generate a response just now. Please try again."
        return response_text, [user_item, *output_items]
