import pytest

from app.time_formatting import format_moving_time_s


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "0s"),
        (59, "59s"),
        (60, "1m"),
        (90, "1m 30s"),
        (3600, "1h"),
        (3661, "1h 1m 1s"),
        (4894, "1h 21m 34s"),
        (5074, "1h 24m 34s"),
    ],
)
def test_format_moving_time_s(seconds: int, expected: str) -> None:
    assert format_moving_time_s(seconds) == expected


def test_format_moving_time_s_accepts_float() -> None:
    assert format_moving_time_s(3661.7) == "1h 1m 1s"
