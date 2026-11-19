from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime

from mcp.server.auth.provider import AccessToken, AuthorizationCode, RefreshToken
from mcp.shared.auth import OAuthClientInformationFull
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import McpOAuthClient, McpOAuthGrant
from app.services.mcp_api_key_service import hash_mcp_api_key

CODE = "code"
ACCESS = "access"
REFRESH = "refresh"


@dataclass(frozen=True)
class StoredCode:
    code: AuthorizationCode
    user_id: int


@dataclass(frozen=True)
class StoredAccess:
    token: AccessToken
    user_id: int


@dataclass(frozen=True)
class StoredRefresh:
    token: RefreshToken
    user_id: int


def _expires_at(epoch: float | int | None) -> datetime | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(float(epoch), UTC)


def _epoch(value: datetime | None) -> float | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.timestamp()


def _expired(epoch: float | int | None) -> bool:
    return epoch is not None and float(epoch) < time.time()


class MemoryOAuthRepository:
    """Process-local OAuth store used by tests."""

    def __init__(self) -> None:
        self.clients: dict[str, OAuthClientInformationFull] = {}
        self.codes: dict[str, StoredCode] = {}
        self.access: dict[str, StoredAccess] = {}
        self.refresh: dict[str, StoredRefresh] = {}
        self.partners: dict[str, str] = {}

    def save_client(self, client: OAuthClientInformationFull) -> None:
        if client.client_id is None:
            raise ValueError("client_id is required")
        self.clients[client.client_id] = client

    def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self.clients.get(client_id)

    def save_code(self, code: AuthorizationCode, user_id: int) -> None:
        self.codes[code.code] = StoredCode(code=code, user_id=user_id)

    def get_code(self, raw_code: str, client_id: str) -> StoredCode | None:
        stored = self.codes.get(raw_code)
        if stored is None or stored.code.client_id != client_id or _expired(stored.code.expires_at):
            if stored is not None and _expired(stored.code.expires_at):
                self.codes.pop(raw_code, None)
            return None
        return stored

    def delete_code(self, raw_code: str) -> None:
        self.codes.pop(raw_code, None)

    def save_token_pair(
        self,
        access: AccessToken,
        refresh: RefreshToken,
        user_id: int,
    ) -> None:
        self.access[access.token] = StoredAccess(token=access, user_id=user_id)
        self.refresh[refresh.token] = StoredRefresh(token=refresh, user_id=user_id)
        self.partners[access.token] = refresh.token
        self.partners[refresh.token] = access.token

    def get_access(self, raw_token: str) -> StoredAccess | None:
        stored = self.access.get(raw_token)
        if stored is None:
            return None
        if _expired(stored.token.expires_at):
            self.revoke_access(raw_token)
            return None
        return stored

    def get_refresh(self, raw_token: str, client_id: str) -> StoredRefresh | None:
        stored = self.refresh.get(raw_token)
        if stored is None or stored.token.client_id != client_id:
            return None
        if _expired(stored.token.expires_at):
            self.revoke_refresh(raw_token)
            return None
        return stored

    def revoke_access(self, raw_token: str) -> None:
        self.access.pop(raw_token, None)
        partner = self.partners.pop(raw_token, None)
        if partner:
            self.refresh.pop(partner, None)
            self.partners.pop(partner, None)

    def revoke_refresh(self, raw_token: str) -> None:
        self.refresh.pop(raw_token, None)
        partner = self.partners.pop(raw_token, None)
        if partner:
            self.access.pop(partner, None)
            self.partners.pop(partner, None)

    def user_id_for_access_token(self, raw_token: str) -> int | None:
        stored = self.get_access(raw_token)
        if stored is None:
            return None
        return stored.user_id


class SqlOAuthRepository:
    """Hashed OAuth grants in Postgres. Raw tokens are not stored."""

    def save_client(self, client: OAuthClientInformationFull) -> None:
        if client.client_id is None:
            raise ValueError("client_id is required")
        payload = client.model_dump(mode="json")
        with SessionLocal() as db:
            row = db.get(McpOAuthClient, client.client_id)
            if row is None:
                db.add(McpOAuthClient(client_id=client.client_id, payload=payload))
            else:
                row.payload = payload
            db.commit()

    def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        with SessionLocal() as db:
            row = db.get(McpOAuthClient, client_id)
            if row is None:
                return None
            return OAuthClientInformationFull.model_validate(row.payload)

    def save_code(self, code: AuthorizationCode, user_id: int) -> None:
        payload = code.model_dump(mode="json")
        payload.pop("code", None)
        payload["user_id"] = user_id
        with SessionLocal() as db:
            db.merge(
                McpOAuthGrant(
                    token_hash=hash_mcp_api_key(code.code),
                    kind=CODE,
                    client_id=code.client_id,
                    user_id=user_id,
                    payload=payload,
                    expires_at=_expires_at(code.expires_at),
                )
            )
            db.commit()

    def get_code(self, raw_code: str, client_id: str) -> StoredCode | None:
        with SessionLocal() as db:
            row = self._row(db, raw_code, CODE)
            if row is None or row.client_id != client_id:
                return None
            if row.expires_at is not None and _expired(_epoch(row.expires_at)):
                db.delete(row)
                db.commit()
                return None
            payload = dict(row.payload)
            user_id = int(payload.pop("user_id"))
            payload["code"] = raw_code
            return StoredCode(code=AuthorizationCode.model_validate(payload), user_id=user_id)

    def delete_code(self, raw_code: str) -> None:
        with SessionLocal() as db:
            row = self._row(db, raw_code, CODE)
            if row is not None:
                db.delete(row)
                db.commit()

    def save_token_pair(self, access: AccessToken, refresh: RefreshToken, user_id: int) -> None:
        access_hash = hash_mcp_api_key(access.token)
        refresh_hash = hash_mcp_api_key(refresh.token)
        with SessionLocal() as db:
            db.merge(
                McpOAuthGrant(
                    token_hash=access_hash,
                    kind=ACCESS,
                    client_id=access.client_id,
                    user_id=user_id,
                    partner_hash=refresh_hash,
                    payload=_token_payload(access),
                    expires_at=_expires_at(access.expires_at),
                )
            )
            db.merge(
                McpOAuthGrant(
                    token_hash=refresh_hash,
                    kind=REFRESH,
                    client_id=refresh.client_id,
                    user_id=user_id,
                    partner_hash=access_hash,
                    payload=_token_payload(refresh),
                    expires_at=_expires_at(refresh.expires_at),
                )
            )
            db.commit()

    def get_access(self, raw_token: str) -> StoredAccess | None:
        with SessionLocal() as db:
            row = self._row(db, raw_token, ACCESS)
            if row is None:
                return None
            if row.expires_at is not None and _expired(_epoch(row.expires_at)):
                self._delete_pair(db, row)
                db.commit()
                return None
            payload = dict(row.payload)
            payload["token"] = raw_token
            return StoredAccess(token=AccessToken.model_validate(payload), user_id=row.user_id)

    def get_refresh(self, raw_token: str, client_id: str) -> StoredRefresh | None:
        with SessionLocal() as db:
            row = self._row(db, raw_token, REFRESH)
            if row is None or row.client_id != client_id:
                return None
            if row.expires_at is not None and _expired(_epoch(row.expires_at)):
                self._delete_pair(db, row)
                db.commit()
                return None
            payload = dict(row.payload)
            payload["token"] = raw_token
            return StoredRefresh(token=RefreshToken.model_validate(payload), user_id=row.user_id)

    def revoke_access(self, raw_token: str) -> None:
        with SessionLocal() as db:
            row = self._row(db, raw_token, ACCESS)
            if row is not None:
                self._delete_pair(db, row)
                db.commit()

    def revoke_refresh(self, raw_token: str) -> None:
        with SessionLocal() as db:
            row = self._row(db, raw_token, REFRESH)
            if row is not None:
                self._delete_pair(db, row)
                db.commit()

    def user_id_for_access_token(self, raw_token: str) -> int | None:
        stored = self.get_access(raw_token)
        if stored is None:
            return None
        return stored.user_id

    def _row(self, db: Session, raw_token: str, kind: str) -> McpOAuthGrant | None:
        return db.scalar(
            select(McpOAuthGrant).where(
                McpOAuthGrant.token_hash == hash_mcp_api_key(raw_token),
                McpOAuthGrant.kind == kind,
            )
        )

    def _delete_pair(self, db: Session, row: McpOAuthGrant) -> None:
        if row.partner_hash:
            partner = db.get(McpOAuthGrant, row.partner_hash)
            if partner is not None:
                db.delete(partner)
        db.delete(row)


def _token_payload(token: AccessToken | RefreshToken) -> dict:
    payload = token.model_dump(mode="json")
    payload.pop("token", None)
    return payload
