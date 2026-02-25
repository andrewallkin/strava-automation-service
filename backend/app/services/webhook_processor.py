import time

from sqlalchemy import select

from app.db import SessionLocal
from app.models import User
from app.services.activity_service import log_event, set_pending_activity
from app.services.strava_service import StravaService
from app.services.telegram_service import TelegramService

MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5

RUN_TYPES = {"Run", "VirtualRun", "TrailRun", "TreadmillRun", "TrackRun"}


def process_activity(activity_id: int, owner_id: int | None = None, attempt: int = 0) -> None:
    strava = StravaService()
    telegram = TelegramService()

    with SessionLocal() as db:
        user = db.scalar(select(User).limit(1))
        if not user:
            log_event(
                db,
                event_type="webhook_process",
                status="error",
                message="No user found; complete Strava OAuth first",
                payload={"activity_id": activity_id},
            )
            return

        for attempt_num in range(attempt, MAX_ATTEMPTS):
            try:
                activity = strava.get_activity(db, activity_id=activity_id, user=user)
                activity_type = activity.get("type")

                if user.run_shoe_enabled and activity_type in RUN_TYPES:
                    shoes = strava.sync_gear_cache(db, user=user)
                    if not shoes:
                        raise RuntimeError("No shoes available in Strava athlete profile")
                    chat_id = user.telegram_user_id or telegram.settings.telegram_allowed_user_id
                    if not chat_id:
                        raise RuntimeError("TELEGRAM_ALLOWED_USER_ID not set; cannot send message")
                    message_id = telegram.send_gear_selection_message(
                        chat_id=chat_id,
                        activity_id=activity_id,
                        shoes=shoes,
                    )
                    set_pending_activity(db, activity_id=activity_id, telegram_message_id=message_id)
                    log_event(
                        db,
                        event_type="run_action",
                        status="ok",
                        message="Sent Telegram gear picker",
                        payload={"activity_id": activity_id, "message_id": message_id},
                    )
                    return

                if user.gym_hide_enabled and activity_type in {"WeightTraining", "Workout"}:
                    strava.update_activity(
                        db,
                        activity_id=activity_id,
                        payload={"hide_from_home": "true"},
                        user=user,
                    )
                    chat_id = user.telegram_user_id or telegram.settings.telegram_allowed_user_id
                    if chat_id:
                        telegram.send_message(chat_id, "Gym workout hidden from feed. Strong work.")
                    log_event(
                        db,
                        event_type="gym_action",
                        status="ok",
                        message="Updated activity hide_from_home=true",
                        payload={"activity_id": activity_id},
                    )
                    return

                log_event(
                    db,
                    event_type="activity_ignored",
                    status="ok",
                    message=f"Ignored activity type: {activity_type}",
                    payload={"activity_id": activity_id, "type": activity_type},
                )
                return

            except Exception as exc:
                if attempt_num + 1 < MAX_ATTEMPTS:
                    log_event(
                        db,
                        event_type="webhook_retry",
                        status="retry",
                        message=f"Retrying after error: {exc}",
                        payload={"activity_id": activity_id, "attempt": attempt_num + 1},
                        correlation_id=str(activity_id),
                    )
                    time.sleep(RETRY_DELAY_SECONDS)
                    continue

                log_event(
                    db,
                    event_type="webhook_failed",
                    status="error",
                    message=f"Activity processing failed: {exc}",
                    payload={"activity_id": activity_id, "attempt": attempt_num},
                    correlation_id=str(activity_id),
                )
                return
