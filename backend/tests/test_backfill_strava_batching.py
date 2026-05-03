"""Verify backfill ingestion batches static athlete and gear Strava reads."""

from __future__ import annotations

import random
from unittest.mock import MagicMock, patch

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import (
    Gear,
    StravaActivity,
    StravaActivityBestEffort,
    StravaActivityLap,
    StravaActivityMetric,
    StravaActivitySplit,
    StravaActivityZoneBucket,
    StravaIngestionJob,
    User,
)
from app.services import strava_ingestion_service as ingestion


def test_prefetch_static_athlete_calls_zones_endpoint() -> None:
    db = MagicMock()
    user = MagicMock()
    strava = MagicMock()
    strava.get_athlete_zones.return_value = {"heartrate": {"zones": [{"min": 0, "max": 180}]}}

    with (
        patch.object(ingestion, "sync_athlete_profile") as mock_prof,
        patch.object(ingestion, "sync_athlete_stats") as mock_stats,
        patch.object(ingestion, "_store_athlete_zones", return_value=True) as mock_store,
    ):
        ok, had_snap = ingestion.prefetch_static_athlete_for_ingestion(db, user, strava, athlete_id=42)

    assert ok is True
    assert had_snap is True
    mock_prof.assert_called_once_with(db, user, strava)
    mock_stats.assert_called_once_with(db, user, strava)
    strava.get_athlete_zones.assert_called_once_with(db, user=user)
    mock_store.assert_called_once()
    db.commit.assert_called_once()


def test_prefetch_static_athlete_rollbacks_when_profile_raises() -> None:
    db = MagicMock()

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("profile down")

    with (
        patch.object(ingestion, "sync_athlete_profile", side_effect=boom),
        patch.object(ingestion, "sync_athlete_stats") as mock_stats,
        patch.object(ingestion, "_store_athlete_zones") as mock_store,
    ):
        ok, had_snap = ingestion.prefetch_static_athlete_for_ingestion(db, MagicMock(), MagicMock(), 1)

    assert ok is False
    assert had_snap is False
    mock_stats.assert_not_called()
    mock_store.assert_not_called()
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_sync_gear_detail_for_activity_ids_batches_distinct() -> None:
    db = MagicMock()
    sr = MagicMock()
    sr.all.return_value = ["g1", "g2"]
    db.scalars.return_value = sr
    sync_calls: list[str] = []

    def capture_sync(database, user: object, gid: str, srv: object) -> None:
        sync_calls.append(gid)

    with patch.object(ingestion, "sync_gear_detail", side_effect=capture_sync):
        ingestion.sync_gear_detail_for_activity_ids(db, MagicMock(), MagicMock(), [101, 102])

    assert sync_calls == ["g1", "g2"]
    db.scalars.assert_called_once()
    db.commit.assert_called_once()


def test_ingest_with_batch_static_skips_athlete_strava_and_gear_sync() -> None:
    athlete_db_id = random.randint(8_000_000_000, 9_000_000_999)

    minimal_detail_base = {
        "id": 50_001,
        "athlete": {"id": athlete_db_id},
        "name": "Run",
        "type": "Run",
        "distance": 1000.0,
        "moving_time": 600,
        "elapsed_time": 600,
        "start_date_local": "2025-01-01T10:00:00Z",
        "start_date": "2025-01-01T10:00:00Z",
    }

    gear_sync_calls = 0
    profile_calls = 0

    def count_gear(*_a: object, **_k: object) -> None:
        nonlocal gear_sync_calls
        gear_sync_calls += 1

    def count_profile(*_a: object, **_k: object) -> None:
        nonlocal profile_calls
        profile_calls += 1

    strava_inst = MagicMock()
    strava_inst.get_activity_detail.side_effect = [
        dict(minimal_detail_base, id=50_001, gear_id="shoe_dup"),
        dict(minimal_detail_base, id=50_002, gear_id="shoe_dup"),
    ]
    strava_inst.get_activity_laps.return_value = []
    strava_inst.get_activity_zones.return_value = []
    strava_inst.get_athlete_zones.side_effect = AssertionError(
        "get_athlete_zones must not run when batch_static_athlete_prefetched",
    )

    with (
        patch("app.services.strava_ingestion_service.StravaService", return_value=strava_inst),
        patch.object(ingestion, "sync_athlete_profile", side_effect=count_profile),
        patch.object(ingestion, "sync_athlete_stats") as stats_mock,
        patch.object(ingestion, "sync_gear_detail", side_effect=count_gear),
        SessionHelper(athlete_db_id) as sess,
    ):
        job_row1 = sess.add_job(activity_id=50_001)
        job_row2 = sess.add_job(activity_id=50_002)
        for job in (job_row1, job_row2):
            ingestion.ingest_activity_event(
                job.activity_id,
                owner_id=athlete_db_id,
                aspect_type="create",
                trigger_type="backfill",
                job_id=job.id,
                batch_static_athlete_prefetched=True,
                prefetch_athlete_zones_snapshot=True,
                defer_gear_detail=True,
            )

        assert strava_inst.get_activity_detail.call_count == 2
        strava_inst.get_athlete_zones.assert_not_called()
        assert profile_calls == 0
        stats_mock.assert_not_called()
        assert gear_sync_calls == 0

        strava_inst.get_gear_detail = MagicMock(
            return_value={
                "id": "shoe_dup",
                "name": "Shoe",
                "distance": 1.0,
                "brand_name": "b",
                "model_name": "m",
                "nickname": "",
                "description": "",
                "retired": False,
                "primary": False,
                "notification_distance": None,
            }
        )
        ingestion.sync_gear_detail_for_activity_ids(sess.db, sess.user, strava_inst, [50_001, 50_002])
        assert strava_inst.get_gear_detail.call_count == 1


class SessionHelper:
    """Minimal DB lifecycle for ingestion tests against the configured Postgres URL."""

    def __init__(self, strava_athlete_db_id: int) -> None:
        self.strava_athlete_id = strava_athlete_db_id
        self._models_children = (
            StravaActivityMetric,
            StravaActivityZoneBucket,
            StravaActivityLap,
            StravaActivitySplit,
            StravaActivityBestEffort,
        )

    def __enter__(self) -> SessionHelper:
        self.db = SessionLocal()
        self.user = User(
            strava_athlete_id=self.strava_athlete_id,
            access_token="batch-test-token",
            refresh_token=None,
            expires_at=None,
            run_shoe_enabled=False,
            gym_hide_enabled=False,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)
        self._jobs: list[int] = []
        self._activities: list[int] = []
        return self

    def add_job(self, activity_id: int) -> StravaIngestionJob:
        row = StravaIngestionJob(
            activity_id=activity_id,
            athlete_id=self.user.strava_athlete_id,
            trigger_type="backfill",
            aspect_type="create",
            status="queued",
            backfill_run_id=None,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        self._jobs.append(int(row.id))
        self._activities.append(activity_id)
        return row

    def __exit__(self, *exc: object) -> None:
        if not hasattr(self, "db"):
            return
        ids = getattr(self, "_activities", [])
        jids = getattr(self, "_jobs", [])
        if ids:
            gear_links = self.db.scalars(
                select(StravaActivity.gear_id).where(StravaActivity.activity_id.in_(ids)).distinct()
            ).all()
            gear_ids_to_clear = [g for g in gear_links if g]
            for model in self._models_children:
                self.db.execute(delete(model).where(model.activity_id.in_(ids)))
            self.db.execute(delete(StravaActivity).where(StravaActivity.activity_id.in_(ids)))
            for gid in gear_ids_to_clear:
                self.db.execute(delete(Gear).where(Gear.strava_gear_id == gid))
        if jids:
            self.db.execute(delete(StravaIngestionJob).where(StravaIngestionJob.id.in_(jids)))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()
