from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.models import Gear, StravaActivity, User
from app.services.telegram_queries import recent_text, shoes_text, streak_text, week_text


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):  # noqa: ARG001
    return "JSON"


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    User.__table__.create(engine)
    Gear.__table__.create(engine)
    StravaActivity.__table__.create(engine)
    session = sessionmaker(bind=engine)()
    session.add(User(id=1, strava_athlete_id=7))
    session.commit()
    yield session
    session.close()


def _user(db) -> User:
    return db.get(User, 1)


def _add(db, **kwargs) -> None:
    defaults = dict(
        athlete_id=7,
        sport_type="Run",
        distance_m=5000,
        moving_time_seconds=1800,
        deleted_at=None,
    )
    defaults.update(kwargs)
    db.add(StravaActivity(**defaults))
    db.commit()


def test_week_text_lists_run_and_gym_on_monday(db) -> None:
    _add(
        db,
        activity_id=1,
        name="Morning Run",
        sport_type="Run",
        local_date=date(2026, 11, 9),
        start_date_local=datetime(2026, 11, 9, 6, 0),
        distance_m=8200,
        moving_time_seconds=2530,
    )
    _add(
        db,
        activity_id=2,
        name="Gym",
        sport_type="WeightTraining",
        local_date=date(2026, 11, 9),
        start_date_local=datetime(2026, 11, 9, 18, 0),
        distance_m=0,
        moving_time_seconds=2880,
    )
    text = week_text(db, _user(db), date(2026, 11, 11))
    assert "Mon\n🏃 Morning Run\n8.2 km · 5:08/km" in text
    assert "🏋️ Gym\n0h 48m 0s" in text


def test_recent_text_returns_five_newest(db) -> None:
    for index in range(6):
        _add(
            db,
            activity_id=index + 1,
            name=f"Activity {index}",
            start_date_local=datetime(2026, 11, 1, index, tzinfo=timezone.utc),
            local_date=date(2026, 11, 1),
        )
    text = recent_text(db, _user(db))
    assert text.startswith("🏃 Activity 5\n")
    assert text.count("🏃 Activity") == 5
    assert "Activity 0" not in text


def test_streak_includes_today_and_yesterday(db) -> None:
    today = date(2026, 11, 17)
    _add(db, activity_id=1, local_date=today, distance_m=2000, sport_type="Run")
    _add(db, activity_id=2, local_date=date(2026, 11, 16), distance_m=2000, sport_type="Run")
    assert streak_text(db, _user(db), today) == "2-day run streak"


def test_streak_counts_yesterday_when_today_is_empty(db) -> None:
    _add(db, activity_id=1, local_date=date(2026, 11, 16), distance_m=2000, sport_type="Run")
    assert streak_text(db, _user(db), date(2026, 11, 17)) == "1-day run streak"


def test_shoes_text_skips_retired_bikes_and_flags_mileage(db) -> None:
    db.add(Gear(strava_gear_id="old", name="Retired", retired=True, distance_m=900_000))
    db.add(Gear(strava_gear_id="g1", name="Pegasus", nickname="Daily", retired=False, distance_m=612_400))
    db.add(
        Gear(
            strava_gear_id="b1",
            name="Scott Addict RC15",
            retired=False,
            distance_m=9_043_200,
            raw_data={"frame_type": 3},
        )
    )
    db.add(Gear(strava_gear_id="b2", name="Kickr", retired=False, distance_m=15_197_500))
    db.commit()
    text = shoes_text(db)
    assert "Retired" not in text
    assert "Scott" not in text
    assert "Kickr" not in text
    assert "👟 Shoes\n\n⚠️ Daily\n612.4 km · consider replacing" in text
