import pytest

from app.routers.telegram_webhook import _parse_callback_data


def test_parse_callback_data() -> None:
    activity_id, gear_id = _parse_callback_data("a:123:g:g456")
    assert activity_id == 123
    assert gear_id == "g456"


def test_parse_callback_data_invalid() -> None:
    with pytest.raises(ValueError):
        _parse_callback_data("bad")
