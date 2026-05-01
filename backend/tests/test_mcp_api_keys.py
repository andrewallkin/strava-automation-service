from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from app.models import McpApiKey, User
from app.services.mcp_api_key_service import create_mcp_api_key, hash_mcp_api_key


def test_create_mcp_api_key_stores_hash_only() -> None:
    user = User(id=7, strava_athlete_id=14460791)
    db = MagicMock()
    stored: list[McpApiKey] = []

    def capture(row):
        row.id = 1
        row.created_at = datetime.now(UTC)
        stored.append(row)

    db.add.side_effect = capture

    with patch("app.services.mcp_api_key_service.secrets.token_urlsafe", return_value="raw-secret"):
        created = create_mcp_api_key(db, user, name="Claude")

    assert created.raw_key == "sva_mcp_raw-secret"
    assert stored[0].name == "Claude"
    assert stored[0].key_hash == hash_mcp_api_key(created.raw_key)
    assert stored[0].key_hash != created.raw_key
    assert stored[0].key_prefix == "sva_mcp_raw-sec"
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(stored[0])


def test_mcp_api_key_model_is_registered() -> None:
    columns = set(McpApiKey.__table__.c.keys())

    assert "key_hash" in columns
    assert "key_prefix" in columns
    assert "last_used_at" in columns
    assert "revoked_at" in columns
