import logging
import time
from datetime import date, datetime, time as dt_time, timezone

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import (
    StravaActivity,
    StravaActivityBestEffort,
    StravaActivityLap,
    StravaActivityMetric,
    StravaActivitySplit,
    StravaActivityZoneBucket,
    StravaAthleteZone,
    StravaBackfillRun,
    StravaIngestionJob,
    User,
)
from app.services.strava_ingestion_service import ingest_activity_event
from app.services.strava_service import StravaRateLimitWait, StravaService, strava_rate_limit_wait_handler

log = logging.getLogger("ingestion")

BACKFILL_ACTIVITY_DELAY_SECONDS = 1


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _date_epoch(value: date) -> int:
    return int(datetime.combine(value, dt_time.min, tzinfo=timezone.utc).timestamp())


def _refresh_counters(db, run: StravaBackfillRun) -> None:
    jobs = db.scalars(select(StravaIngestionJob).where(StravaIngestionJob.backfill_run_id == run.id)).all()
    run.succeeded_count = sum(1 for job in jobs if job.status == "succeeded")
    run.failed_count = sum(1 for job in jobs if job.status == "failed")
    run.skipped_count = sum(1 for job in jobs if job.status == "skipped")
    run.queued_count = sum(1 for job in jobs if job.status in ("queued", "running"))
    run.updated_at = _now()


def _rate_limit_wait_handler(backfill_run_id: int):
    previous_status: str | None = None

    def handle(wait: StravaRateLimitWait | None) -> None:
        nonlocal previous_status
        with SessionLocal() as db:
            run = db.get(StravaBackfillRun, backfill_run_id)
            if not run or run.status in {"completed", "completed_with_errors", "failed", "cancelled"}:
                return
            if wait:
                if run.status != "rate_limited":
                    previous_status = run.status
                run.status = "rate_limited"
                run.rate_limit_wait_until = wait.wait_until
                run.rate_limit_wait_reason = wait.reason
            else:
                if run.status == "rate_limited":
                    run.status = previous_status or "running"
                run.rate_limit_wait_until = None
                run.rate_limit_wait_reason = None
                previous_status = None
            run.updated_at = _now()
            db.commit()

    return handle


def _select_backfill_ids(db, discovered: list[dict], force_refresh: bool) -> list[int]:
    ids = [int(activity["id"]) for activity in discovered if activity.get("id")]
    if force_refresh:
        return ids
    if not ids:
        return []
    existing_rows = db.scalars(select(StravaActivity).where(StravaActivity.activity_id.in_(ids))).all()
    complete_ids = {row.activity_id for row in existing_rows if row.deleted_at is None}
    return [activity_id for activity_id in ids if activity_id not in complete_ids]


def process_backfill_run(backfill_run_id: int) -> None:
    strava = StravaService()
    with SessionLocal() as db:
        run = db.get(StravaBackfillRun, backfill_run_id)
        if not run:
            log.error("Backfill run not found | id=%s", backfill_run_id)
            return
        user = db.get(User, run.user_id)
        if not user or not user.access_token:
            run.status = "failed"
            run.last_error = "No connected Strava user found for backfill"
            run.completed_at = _now()
            run.updated_at = _now()
            db.commit()
            return

        try:
            run.status = "discovering"
            run.rate_limit_wait_until = None
            run.rate_limit_wait_reason = None
            run.started_at = run.started_at or _now()
            run.updated_at = _now()
            db.commit()

            after_epoch = _date_epoch(run.start_date)
            before_epoch = _date_epoch(date.fromordinal(run.end_date.toordinal() + 1))
            with strava_rate_limit_wait_handler(_rate_limit_wait_handler(run.id)):
                discovered = strava.get_athlete_activities_between(
                    db,
                    user,
                    after_epoch=after_epoch,
                    before_epoch=before_epoch,
                )
            selected_ids = _select_backfill_ids(db, discovered, run.force_refresh)
            run.requested_count = len(discovered)
            run.missing_count = len(selected_ids)

            for activity_id in selected_ids:
                db.add(StravaIngestionJob(
                    activity_id=activity_id,
                    athlete_id=run.athlete_id,
                    trigger_type="backfill",
                    aspect_type="create",
                    status="queued",
                    backfill_run_id=run.id,
                ))
            run.status = "queued" if selected_ids else "completed"
            run.rate_limit_wait_until = None
            run.rate_limit_wait_reason = None
            if not selected_ids:
                run.completed_at = _now()
            run.updated_at = _now()
            db.flush()
            _refresh_counters(db, run)
            db.commit()

            if not selected_ids:
                return

            run.status = "running"
            run.rate_limit_wait_until = None
            run.rate_limit_wait_reason = None
            run.updated_at = _now()
            db.commit()

            jobs = db.scalars(
                select(StravaIngestionJob)
                .where(StravaIngestionJob.backfill_run_id == run.id)
                .where(StravaIngestionJob.status == "queued")
                .order_by(StravaIngestionJob.queued_at)
            ).all()
            for index, job in enumerate(jobs):
                db.commit()
                with strava_rate_limit_wait_handler(_rate_limit_wait_handler(run.id)):
                    ingest_activity_event(
                        activity_id=job.activity_id,
                        owner_id=run.athlete_id,
                        aspect_type="create",
                        trigger_type="backfill",
                        job_id=job.id,
                        backfill_run_id=run.id,
                    )
                db.expire_all()
                db.refresh(run)
                _refresh_counters(db, run)
                db.commit()
                if index + 1 < len(jobs):
                    time.sleep(BACKFILL_ACTIVITY_DELAY_SECONDS)

            db.refresh(run)
            _refresh_counters(db, run)
            run.status = "completed_with_errors" if run.failed_count else "completed"
            run.rate_limit_wait_until = None
            run.rate_limit_wait_reason = None
            run.completed_at = _now()
            run.updated_at = _now()
            db.commit()
        except Exception as exc:
            db.rollback()
            run = db.get(StravaBackfillRun, backfill_run_id)
            if run:
                _refresh_counters(db, run)
                run.status = "failed"
                run.last_error = str(exc)
                run.rate_limit_wait_until = None
                run.rate_limit_wait_reason = None
                run.completed_at = _now()
                run.updated_at = _now()
                db.commit()
            log.error("Backfill failed | id=%s error=%s", backfill_run_id, exc, exc_info=True)


def retry_failed_backfill_jobs(backfill_run_id: int) -> None:
    with SessionLocal() as db:
        run = db.get(StravaBackfillRun, backfill_run_id)
        if not run:
            return
        jobs = db.scalars(
            select(StravaIngestionJob)
            .where(StravaIngestionJob.backfill_run_id == backfill_run_id)
            .where(StravaIngestionJob.status == "failed")
            .order_by(StravaIngestionJob.queued_at)
        ).all()
        run.status = "running"
        run.rate_limit_wait_until = None
        run.rate_limit_wait_reason = None
        run.completed_at = None
        run.updated_at = _now()
        db.commit()

        for index, job in enumerate(jobs):
            job.status = "queued"
            job.last_error = None
            job.completed_at = None
            job.updated_at = _now()
            db.commit()
            with strava_rate_limit_wait_handler(_rate_limit_wait_handler(run.id)):
                ingest_activity_event(
                    activity_id=job.activity_id,
                    owner_id=run.athlete_id,
                    aspect_type=job.aspect_type,
                    trigger_type="manual_retry",
                    job_id=job.id,
                    backfill_run_id=run.id,
                )
            db.expire_all()
            db.refresh(run)
            _refresh_counters(db, run)
            db.commit()
            if index + 1 < len(jobs):
                time.sleep(BACKFILL_ACTIVITY_DELAY_SECONDS)

        db.refresh(run)
        _refresh_counters(db, run)
        run.status = "completed_with_errors" if run.failed_count else "completed"
        run.rate_limit_wait_until = None
        run.rate_limit_wait_reason = None
        run.completed_at = _now()
        run.updated_at = _now()
        db.commit()


def cancel_backfill_run(backfill_run_id: int) -> bool:
    with SessionLocal() as db:
        run = db.get(StravaBackfillRun, backfill_run_id)
        if not run:
            return False
        queued_jobs = db.scalars(
            select(StravaIngestionJob)
            .where(StravaIngestionJob.backfill_run_id == backfill_run_id)
            .where(StravaIngestionJob.status == "queued")
        ).all()
        for job in queued_jobs:
            job.status = "skipped"
            job.last_error = "Backfill cancelled"
            job.updated_at = _now()
        run.status = "cancelled"
        run.rate_limit_wait_until = None
        run.rate_limit_wait_reason = None
        run.completed_at = _now()
        run.updated_at = _now()
        _refresh_counters(db, run)
        db.commit()
        return True


def cleanup_ingestion_tables() -> None:
    with SessionLocal() as db:
        for model in (
            StravaActivityMetric,
            StravaAthleteZone,
            StravaActivityZoneBucket,
            StravaActivityBestEffort,
            StravaActivitySplit,
            StravaActivityLap,
            StravaIngestionJob,
            StravaBackfillRun,
            StravaActivity,
        ):
            db.execute(delete(model))
        db.commit()
