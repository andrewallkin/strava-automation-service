"""Verify backfill ingestion batches static athlete and gear Strava reads."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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
