from unittest.mock import MagicMock

from app.db import Base
from app.models import (
    StravaActivity,
    StravaActivityLap,
    StravaActivityMetric,
    StravaActivitySplit,
    StravaActivityZoneBucket,
    StravaAthleteZone,
)
from app.services import strava_ingestion_service as ingestion
from app.services.webhook_processor import RUN_TYPES, process_activity


def test_schema_excludes_stream_storage() -> None:
    table_names = set(Base.metadata.tables)

    assert "strava_activity_streams" not in table_names
    assert "strava_activity_segment_efforts" not in table_names
    assert "strava_activity_zones" not in table_names
    assert "strava_activity_metrics" in table_names
    assert "strava_activity_zone_buckets" in table_names
    assert "strava_athlete_zones" in table_names


def test_activity_model_promotes_mcp_ready_columns() -> None:
    columns = set(StravaActivity.__table__.c.keys())

    assert "distance_m" in columns
    assert "moving_time_seconds" in columns
    assert "average_grade_adjusted_speed_mps" in columns
    assert "average_cadence_spm" in columns
    assert "has_streams" not in columns
    assert "summary_polyline" not in columns


def test_child_and_rollup_models_have_query_ready_gap_and_zone_columns() -> None:
    assert "average_grade_adjusted_speed_mps" in set(StravaActivityLap.__table__.c.keys())
    assert "average_grade_adjusted_speed_mps" in set(StravaActivitySplit.__table__.c.keys())
    assert "gap_seconds_per_km" in set(StravaActivityMetric.__table__.c.keys())
    assert "hr_zone_5_seconds" in set(StravaActivityMetric.__table__.c.keys())
    assert "time_seconds" in set(StravaActivityZoneBucket.__table__.c.keys())
    assert "bucket_index" in set(StravaAthleteZone.__table__.c.keys())


def test_replace_child_rows_promotes_strava_gap_without_computing() -> None:
    db = MagicMock()
    detail = {
        "splits_metric": [
            {
                "split": 1,
                "distance": 1000.0,
                "moving_time": 300,
                "average_speed": 3.33,
                "average_grade_adjusted_speed": 3.5,
                "average_heartrate": 150,
            }
        ],
        "splits_standard": [],
        "best_efforts": [],
    }
    laps = [
        {
            "id": 1,
            "distance": 1000.0,
            "moving_time": 300,
            "average_speed": 3.33,
            "average_grade_adjusted_speed": 3.45,
            "average_cadence": 82.5,
        },
        {
            "id": 2,
            "distance": 1000.0,
            "moving_time": 320,
            "average_speed": 3.125,
        },
    ]
    zones = [
        {
            "type": "heartrate",
            "sensor_based": True,
            "custom_zones": False,
            "score": 10,
            "distribution_buckets": [{"min": 0, "max": 120, "time": 60}],
        }
    ]

    ingestion._replace_child_rows(db, 123, 456, detail, laps, zones)

    added = [call.args[0] for call in db.add.call_args_list]
    lap_rows = [row for row in added if isinstance(row, StravaActivityLap)]
    split_rows = [row for row in added if isinstance(row, StravaActivitySplit)]
    zone_rows = [row for row in added if isinstance(row, StravaActivityZoneBucket)]

    assert lap_rows[0].average_grade_adjusted_speed_mps == 3.45
    assert lap_rows[0].gap_source == "strava"
    assert lap_rows[0].average_cadence_spm == 165.0
    assert lap_rows[1].average_grade_adjusted_speed_mps is None
    assert lap_rows[1].gap_source == "unavailable"
    assert split_rows[0].average_grade_adjusted_speed_mps == 3.5
    assert split_rows[0].gap_source == "strava"
    assert zone_rows[0].zone_type == "heartrate"
    assert zone_rows[0].time_seconds == 60


def test_store_athlete_zones_flattens_zone_snapshot() -> None:
    db = MagicMock()

    created = ingestion._store_athlete_zones(
        db,
        456,
        {"heart_rate": {"custom_zones": False, "zones": [{"min": 0, "max": 127}]}},
    )

    added = [call.args[0] for call in db.add.call_args_list]
    assert created is True
    assert len(added) == 1
    assert isinstance(added[0], StravaAthleteZone)
    assert added[0].athlete_id == 456
    assert added[0].zone_type == "heart_rate"
    assert added[0].bucket_index == 1
    assert added[0].min_value == 0
    assert added[0].max_value == 127


def test_webhook_shoe_and_gym_automation_remains_available() -> None:
    assert "Run" in RUN_TYPES
    assert callable(process_activity)
