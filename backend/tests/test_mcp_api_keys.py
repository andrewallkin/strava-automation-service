from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from app.models import McpApiKey, User
from app.services.mcp_api_key_service import (
    create_mcp_api_key,
    hash_mcp_api_key,
    list_mcp_api_keys,
    revoke_mcp_api_key,
)


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


def test_list_mcp_api_keys_only_returns_active_keys() -> None:
    user = User(id=7, strava_athlete_id=14460791)
    db = MagicMock()
    result = MagicMock()
    result.all.return_value = []
    db.scalars.return_value = result

    assert list_mcp_api_keys(db, user) == []

    statement = db.scalars.call_args.args[0]
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "mcp_api_keys.user_id = 7" in compiled
    assert "mcp_api_keys.revoked_at IS NULL" in compiled


def test_revoke_mcp_api_key_is_idempotent_for_existing_revoked_key() -> None:
    user = User(id=7, strava_athlete_id=14460791)
    row = McpApiKey(user_id=user.id, key_hash="hash", key_prefix="prefix")
    row.revoked_at = datetime.now(UTC)
    db = MagicMock()
    db.scalar.return_value = row

    assert revoke_mcp_api_key(db, user, key_id=1) is True
    db.commit.assert_not_called()


def test_mcp_api_key_model_is_registered() -> None:
    columns = set(McpApiKey.__table__.c.keys())

    assert "key_hash" in columns
    assert "key_prefix" in columns
    assert "last_used_at" in columns
    assert "revoked_at" in columns
