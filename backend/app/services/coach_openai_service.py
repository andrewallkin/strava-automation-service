from __future__ import annotations

import logging
import os
from time import perf_counter
from typing import Any

from agents import Agent, FileSearchTool, HostedMCPTool, ModelSettings, Runner
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User, UserCoachSettings
from app.services.coach_conversation_store import should_store_history_item
from app.services.openai_credential_service import get_openai_api_key_for_user

log = logging.getLogger("coach.agent")


TELEGRAM_MARKDOWN_V2_OUTPUT = """
Output format (Telegram-safe plain text)

Your replies are sent to Telegram by the application. The application handles MarkdownV2 escaping.

Write normal plain text. Do not include MarkdownV2 backslash escapes such as \\., \\!, \\(, or \\-.
Do not use Markdown formatting markers for bold, italics, links, code blocks, or tables.

Lists: prefer numbered lists (1. item) or the UTF-8 bullet character • for bullets.
""".strip()


def make_user_input_item(text: str) -> dict[str, Any]:
    return {
        "role": "user",
        "content": [{"type": "input_text", "text": text}],
    }


ALLOWED_MCP_TOOLS = [
    "get_athlete_profile",
    "get_heart_rate_zones",
    "get_current_date",
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
        if item_type == "mcp_list_tools":
            continue
        if should_store_history_item(item):
            prepared.append(item)
            continue
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
        log.info("Coach agent turn started for user_id=%s", user.id)
        api_key = get_openai_api_key_for_user(db, user)
        if not api_key:
            log.warning("Coach agent run aborted: missing OpenAI API key for user_id=%s", user.id)
            raise ValueError("OpenAI API key is not configured")
        settings = get_settings()

        user_item = make_user_input_item(user_message)
        run_input = _prepare_history_for_request(history)
        run_input.append(user_item)
        log.info(
            "Prepared conversation payload for user_id=%s history_items=%s request_items=%s",
            user.id,
            len(history),
            len(run_input),
        )

        base_instructions = coach_settings.agent_instructions.strip()
        if base_instructions:
            instructions = (
                f"You are {coach_settings.agent_name.strip()}.\n\n"
                f"{base_instructions}\n\n"
                f"{TELEGRAM_MARKDOWN_V2_OUTPUT}"
            )
        else:
            instructions = (
                f"You are {coach_settings.agent_name.strip()}.\n\n"
                f"{TELEGRAM_MARKDOWN_V2_OUTPUT}"
            )

        tools: list[Any] = []
        if coach_settings.vector_store_id:
            log.info(
                "Loading FileSearch tool for user_id=%s vector_store_id=%s",
                user.id,
                coach_settings.vector_store_id,
            )
            tools.append(FileSearchTool(vector_store_ids=[coach_settings.vector_store_id]))
        else:
            log.info("FileSearch tool disabled for user_id=%s (no vector store configured)", user.id)

        if settings.mcp_server_url and settings.strava_mcp_bearer:
            log.info("Loading MCP tool for user_id=%s server_url=%s", user.id, settings.mcp_server_url)
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
        else:
            log.info("MCP tool disabled for user_id=%s (missing MCP configuration)", user.id)

        agent = Agent(
            name=coach_settings.agent_name.strip() or "Coach",
            instructions=instructions,
            model=coach_settings.openai_model,
            tools=tools,
            model_settings=ModelSettings(parallel_tool_calls=False, tool_choice="auto"),
        )

        previous_api_key = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = api_key
        started_at = perf_counter()
        try:
            log.info(
                "Invoking OpenAI agent for user_id=%s model=%s tool_count=%s",
                user.id,
                coach_settings.openai_model,
                len(tools),
            )
            result = await Runner.run(agent, input=run_input)
            elapsed_ms = int((perf_counter() - started_at) * 1000)
            log.info("OpenAI agent response received for user_id=%s duration_ms=%s", user.id, elapsed_ms)
        except Exception:
            elapsed_ms = int((perf_counter() - started_at) * 1000)
            log.exception("OpenAI agent invocation failed for user_id=%s duration_ms=%s", user.id, elapsed_ms)
            raise
        finally:
            if previous_api_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = previous_api_key
        output_items = [_json_safe(item.to_input_item()) for item in result.new_items]
        response_text = result.final_output_as(str).strip()
        if not response_text:
            response_text = "I couldn't generate a response just now. Please try again."
        log.info(
            "Coach agent turn completed for user_id=%s output_items=%s response_length=%s",
            user.id,
            len(output_items),
            len(response_text),
        )
        return response_text, [user_item, *output_items]
