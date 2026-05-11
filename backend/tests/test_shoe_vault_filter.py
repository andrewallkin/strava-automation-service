"""Tests for Shoe Vault gear inclusion (running shoes only, not retired)."""

from app.services.activity_service import include_gear_in_shoe_vault


def test_include_active_shoe_without_frame_type() -> None:
    assert include_gear_in_shoe_vault({"id": "g1", "distance": 1000, "retired": False}) is True


def test_include_when_retired_missing_treated_as_active() -> None:
    assert include_gear_in_shoe_vault({"id": "g1", "distance": 500}) is True


def test_exclude_retired_shoe() -> None:
    assert include_gear_in_shoe_vault({"id": "g1", "retired": True, "distance": 999712}) is False


def test_exclude_bike_or_trainer_with_frame_type() -> None:
    assert include_gear_in_shoe_vault({"id": "b1", "frame_type": 3, "distance": 15000000}) is False
