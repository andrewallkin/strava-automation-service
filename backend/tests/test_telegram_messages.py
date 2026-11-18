from datetime import date, datetime

from app.services.telegram_messages import (
    WeekActivity,
    format_activity_receipt,
    format_help,
    format_recent_line,
    format_run_card,
    format_shoe_line,
    format_streak,
    format_week,
)


def test_run_card_field_order() -> None:
    text = format_run_card({
        "name": "Morning Run",
        "distance": 8200,
        "moving_time": 2530,
        "average_heartrate": 148,
        "max_heartrate": 172,
        "average_cadence": 86,
        "total_elevation_gain": 72,
    })
    assert text.splitlines() == [
        "📝 Morning Run",
        "📏 8.20 km",
        "⏱ 0h 42m 10s",
        "🏃 5:08/km",
        "❤️ 148 avg / 172 max",
        "🦶 172 spm",
        "⛰️ 72 m",
        "",
        "Which shoes did you wear? 👟",
    ]


def test_run_card_omits_heart_rate_when_missing() -> None:
    text = format_run_card({
        "name": "Easy",
        "distance": 5000,
        "moving_time": 1800,
        "average_heartrate": 140,
    })
    assert not any("❤️" in line for line in text.splitlines())


def test_week_stacks_gym_under_the_run() -> None:
    monday = date(2026, 11, 9)
    text = format_week(
        monday,
        [
            WeekActivity("Morning Run", "Run", datetime(2026, 11, 9, 6, 0), 8200, 2530),
            WeekActivity("Gym", "WeightTraining", datetime(2026, 11, 9, 18, 0), 0, 2880),
        ],
        previous_km=0,
    )
    assert "Mon\n🏃 Morning Run\n8.2 km · 5:08/km" in text
    assert "🏋️ Gym\n0h 48m 0s" in text
    assert "Tue–Sun —" in text
    assert text.startswith("📅 9–15 Nov")
    assert "This week\n8.2 km · 1h 30m 10s" in text
    assert "📈 8.2 km more than last week" in text


def test_week_orders_the_day_by_start_time() -> None:
    monday = date(2026, 11, 9)
    text = format_week(
        monday,
        [
            WeekActivity("Evening Run", "Run", datetime(2026, 11, 9, 18, 0), 5000, 1800),
            WeekActivity("Morning Gym", "WeightTraining", datetime(2026, 11, 9, 6, 0), 0, 3600),
        ],
        previous_km=0,
    )
    assert text.index("Morning Gym") < text.index("Evening Run")


def test_week_collapses_empty_days_around_a_session() -> None:
    text = format_week(
        date(2026, 11, 9),
        [WeekActivity("Easy", "Run", datetime(2026, 11, 11, 7, 0), 5000, 1800)],
        previous_km=0,
    )
    assert "Mon–Tue —" in text
    assert "Wed\n🏃 Easy\n5.0 km · 6:00/km" in text
    assert "Thu–Sun —" in text


def test_receipt_includes_duration() -> None:
    text = format_activity_receipt({
        "type": "WeightTraining",
        "name": "Gym",
        "distance": 0,
        "moving_time": 2880,
    })
    assert text == "WeightTraining\nGym\n0h 48m 0s"


def test_week_same_distance() -> None:
    text = format_week(date(2026, 11, 9), [], previous_km=0)
    assert "Same distance as last week" in text


def test_shoe_line_flags_at_six_hundred_and_eight_hundred_km() -> None:
    assert format_shoe_line("Pegasus", 600_000, None) == "⚠️ Pegasus\n600.0 km · consider replacing"
    assert format_shoe_line("Pegasus", 800_000, None) == "⚠️ Pegasus\n800.0 km · time to replace"
    assert format_shoe_line("Pegasus", 100_000, None) == "Pegasus\n100.0 km"


def test_shoe_line_uses_notification_distance() -> None:
    assert format_shoe_line("Pegasus", 500_000, 500_000) == "⚠️ Pegasus\n500.0 km · time to replace"


def test_shoe_line_ignores_unset_notification_distance() -> None:
    assert format_shoe_line("Boston", 7300, 0) == "Boston\n7.3 km"


def test_recent_run_line() -> None:
    assert format_recent_line("Run", "Morning Run", 8200, 2530) == "🏃 Morning Run\n8.2 km · 5:08/km"


def test_recent_gym_line_drops_the_sport_prefix() -> None:
    assert format_recent_line("WeightTraining", "Afternoon Weight Training", 0, 4031) == (
        "🏋️ Afternoon Weight Training\n1h 7m 11s"
    )


def test_streak_messages() -> None:
    assert format_streak(0) == "No current run streak."
    assert format_streak(3) == "3-day run streak"


def test_help_lists_commands() -> None:
    text = format_help()
    for command in ("/shoes", "/week", "/recent", "/streak", "/help", "/cancel"):
        assert command in text