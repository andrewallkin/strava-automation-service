from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_jwt_user
from app.models import StravaActivity, StravaBackfillRun, StravaIngestionJob, User
from app.services.strava_backfill_service import (
    cancel_backfill_run,
    cleanup_ingestion_tables,
    process_backfill_run,
    retry_failed_backfill_jobs,
)

router = APIRouter(prefix="/api/ui", tags=["ui-ingestion"])


class BackfillCreate(BaseModel):
    start_date: date
    end_date: date
    force_refresh: bool = False


def _dt(value) -> str | None:
    return value.isoformat() if value else None


def _activity_row(row: StravaActivity) -> dict:
    return {
        "activity_id": row.activity_id,
        "name": row.name,
        "description": row.description,
        "activity_type": row.activity_type,
        "sport_type": row.sport_type,
        "start_date": _dt(row.start_date),
        "start_date_local": _dt(row.start_date_local),
        "distance": row.distance_m,
        "moving_time": row.moving_time_seconds,
        "elapsed_time": row.elapsed_time_seconds,
        "total_elevation_gain": row.total_elevation_gain_m,
        "average_heartrate": row.average_heartrate_bpm,
        "average_watts": row.average_watts,
        "weighted_average_watts": row.weighted_average_watts,
        "gear_id": row.gear_id,
        "trainer": row.trainer,
        "commute": row.commute,
        "has_laps": row.has_laps,
        "has_splits": row.has_splits,
        "has_best_efforts": row.has_best_efforts,
        "has_zones": row.has_zones,
        "has_gap": row.has_gap,
        "last_ingested_at": _dt(row.last_ingested_at),
        "deleted_at": _dt(row.deleted_at),
    }


def _backfill_row(row: StravaBackfillRun) -> dict:
    return {
        "id": row.id,
        "athlete_id": row.athlete_id,
        "start_date": row.start_date.isoformat(),
        "end_date": row.end_date.isoformat(),
        "force_refresh": row.force_refresh,
        "status": row.status,
        "requested_count": row.requested_count,
        "missing_count": row.missing_count,
        "queued_count": row.queued_count,
        "succeeded_count": row.succeeded_count,
        "failed_count": row.failed_count,
        "skipped_count": row.skipped_count,
        "last_error": row.last_error,
        "rate_limit_wait_until": _dt(row.rate_limit_wait_until),
        "rate_limit_wait_reason": row.rate_limit_wait_reason,
        "created_at": _dt(row.created_at),
        "started_at": _dt(row.started_at),
        "completed_at": _dt(row.completed_at),
        "updated_at": _dt(row.updated_at),
    }


def _job_row(row: StravaIngestionJob) -> dict:
    return {
        "id": row.id,
        "activity_id": row.activity_id,
        "athlete_id": row.athlete_id,
        "trigger_type": row.trigger_type,
        "aspect_type": row.aspect_type,
        "status": row.status,
        "attempt_count": row.attempt_count,
        "last_error": row.last_error,
        "queued_at": _dt(row.queued_at),
        "started_at": _dt(row.started_at),
        "completed_at": _dt(row.completed_at),
        "updated_at": _dt(row.updated_at),
    }


@router.get("/ingested-activities")
def ingested_activities(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=25, ge=1, le=100),
    sport_type: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(require_jwt_user),
) -> dict:
    filters = []
    if not include_deleted:
        filters.append(StravaActivity.deleted_at.is_(None))
    if sport_type:
        filters.append(StravaActivity.sport_type == sport_type)
    if start_date:
        filters.append(func.date(StravaActivity.start_date_local) >= start_date)
    if end_date:
        filters.append(func.date(StravaActivity.start_date_local) <= end_date)

    stmt = select(StravaActivity)
    count_stmt = select(func.count(StravaActivity.activity_id))
    for condition in filters:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(StravaActivity.start_date_local.desc().nullslast())
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).all()
    return {
        "items": [_activity_row(row) for row in rows],
        "page": page,
        "per_page": per_page,
        "total": total,
    }


@router.post("/backfill")
def create_backfill(
    body: BackfillCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_jwt_user),
) -> dict:
    if not user.access_token or not user.strava_athlete_id:
        raise HTTPException(status_code=404, detail="No connected Strava user")
    if body.end_date < body.start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")

    run = StravaBackfillRun(
        athlete_id=user.strava_athlete_id,
        user_id=user.id,
        start_date=body.start_date,
        end_date=body.end_date,
        force_refresh=body.force_refresh,
        status="created",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    background_tasks.add_task(process_backfill_run, run.id)
    return _backfill_row(run)


@router.get("/backfill/latest")
def get_latest_backfill(
    db: Session = Depends(get_db),
    user: User = Depends(require_jwt_user),
) -> dict | None:
    active_statuses = {"created", "discovering", "queued", "running", "rate_limited"}
    active_run = db.scalars(
        select(StravaBackfillRun)
        .where(StravaBackfillRun.user_id == user.id)
        .where(StravaBackfillRun.status.in_(active_statuses))
        .order_by(StravaBackfillRun.updated_at.desc())
        .limit(1)
    ).first()
    if active_run:
        return _backfill_row(active_run)

    latest_run = db.scalars(
        select(StravaBackfillRun)
        .where(StravaBackfillRun.user_id == user.id)
        .order_by(StravaBackfillRun.updated_at.desc())
        .limit(1)
    ).first()
    return _backfill_row(latest_run) if latest_run else None


@router.get("/backfill/history")
def get_backfill_history(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(require_jwt_user),
) -> list[dict]:
    rows = db.scalars(
        select(StravaBackfillRun)
        .where(StravaBackfillRun.user_id == user.id)
        .order_by(StravaBackfillRun.updated_at.desc())
        .limit(limit)
    ).all()
    return [_backfill_row(row) for row in rows]


@router.get("/backfill/{backfill_run_id}")
def get_backfill(
    backfill_run_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_jwt_user),
) -> dict:
    run = db.get(StravaBackfillRun, backfill_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Backfill run not found")
    return _backfill_row(run)


@router.get("/backfill/{backfill_run_id}/jobs")
def get_backfill_jobs(
    backfill_run_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_jwt_user),
) -> list[dict]:
    run = db.get(StravaBackfillRun, backfill_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Backfill run not found")
    rows = db.scalars(
        select(StravaIngestionJob)
        .where(StravaIngestionJob.backfill_run_id == backfill_run_id)
        .order_by(StravaIngestionJob.queued_at.desc())
    ).all()
    return [_job_row(row) for row in rows]


@router.post("/backfill/{backfill_run_id}/retry-failed")
def retry_failed_backfill(
    backfill_run_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(require_jwt_user),
) -> dict:
    if not db.get(StravaBackfillRun, backfill_run_id):
        raise HTTPException(status_code=404, detail="Backfill run not found")
    background_tasks.add_task(retry_failed_backfill_jobs, backfill_run_id)
    return {"status": "queued", "backfill_run_id": backfill_run_id}


@router.post("/backfill/{backfill_run_id}/cancel")
def cancel_backfill(
    backfill_run_id: int,
    _: User = Depends(require_jwt_user),
) -> dict:
    if not cancel_backfill_run(backfill_run_id):
        raise HTTPException(status_code=404, detail="Backfill run not found")
    return {"status": "cancelled", "backfill_run_id": backfill_run_id}


@router.delete("/ingested-activities/dev-cleanup")
def cleanup_ingested_activities(
    _: User = Depends(require_jwt_user),
) -> dict:
    cleanup_ingestion_tables()
    return {"status": "deleted"}
