from __future__ import annotations

import html
import secrets
import time
from collections.abc import Callable
from urllib.parse import urlencode

from mcp.server.auth.handlers.authorize import AuthorizationRequest
from mcp.server.auth.handlers.metadata import MetadataHandler
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    TokenError,
    construct_redirect_uri,
)
from mcp.server.auth.routes import build_metadata, cors_middleware
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
from mcp.shared.auth import InvalidRedirectUriError, InvalidScopeError, OAuthClientInformationFull, OAuthToken
from pydantic import AnyHttpUrl, ValidationError
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.routing import Route

from fastmcp.server.auth.auth import OAuthProvider

from app.db import SessionLocal
from app.mcp.oauth_store import MemoryOAuthRepository, SqlOAuthRepository
from app.models import User
from app.services.jwt_service import AUTH_COOKIE_NAME, JwtService

SCOPE = "activities:read"
ACCESS_TTL = 60 * 60
REFRESH_TTL = 30 * 24 * 60 * 60
CODE_TTL = 5 * 60

OwnerLookup = Callable[[Request], int | None]


def database_owner_id(request: Request) -> int | None:
    """Return the signed-in dashboard user, who is the only person who may approve ChatGPT."""
    raw = request.cookies.get(AUTH_COOKIE_NAME)
    if not raw:
        return None
    try:
        payload = JwtService().decode_token(raw)
        user_id = int(payload["sub"])
    except Exception:
        return None
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None or user.strava_athlete_id is None:
            return None
        return user.id


class OwnerOAuthProvider(OAuthProvider):
    """OAuth 2.1 authorization server for the single signed-in owner.

    ChatGPT can register a public PKCE client. The authorize page issues a code
    only after that owner approves. API-key clients keep using bearer tokens
    verified separately.
    """

    def __init__(
        self,
        base_url: str,
        *,
        repository: MemoryOAuthRepository | SqlOAuthRepository | None = None,
        owner_lookup: OwnerLookup | None = None,
        service_documentation_url: str | None = None,
    ) -> None:
        registration = ClientRegistrationOptions(
            enabled=True,
            valid_scopes=[SCOPE],
            default_scopes=[SCOPE],
        )
        super().__init__(
            base_url=base_url,
            issuer_url=base_url,
            client_registration_options=registration,
            revocation_options=RevocationOptions(enabled=True),
            required_scopes=[SCOPE],
            service_documentation_url=service_documentation_url,
        )
        self.repository = repository if repository is not None else SqlOAuthRepository()
        self.owner_lookup = owner_lookup or database_owner_id

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self.repository.get_client(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        if client_info.client_id is None:
            raise ValueError("client_id is required")
        if client_info.scope and self.client_registration_options and self.client_registration_options.valid_scopes:
            requested = set(client_info.scope.split())
            invalid = requested - set(self.client_registration_options.valid_scopes)
            if invalid:
                raise ValueError(f"Requested scopes are not valid: {', '.join(sorted(invalid))}")
        self.repository.save_client(client_info)

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        raise AuthorizeError(
            "access_denied",
            "Approve access from the signed-in owner page before a code can be issued.",
        )

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        if client.client_id is None:
            return None
        stored = self.repository.get_code(authorization_code, client.client_id)
        if stored is None:
            return None
        return stored.code

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        if client.client_id is None:
            raise TokenError("invalid_client", "Client ID is required")
        stored = self.repository.get_code(authorization_code.code, client.client_id)
        if stored is None:
            raise TokenError("invalid_grant", "Authorization code not found or already used.")
        self.repository.delete_code(authorization_code.code)
        return self._issue_pair(client.client_id, list(authorization_code.scopes), stored.user_id, authorization_code.resource)

    async def load_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str) -> RefreshToken | None:
        if client.client_id is None:
            return None
        stored = self.repository.get_refresh(refresh_token, client.client_id)
        if stored is None:
            return None
        return stored.token

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        if client.client_id is None:
            raise TokenError("invalid_client", "Client ID is required")
        stored = self.repository.get_refresh(refresh_token.token, client.client_id)
        if stored is None:
            raise TokenError("invalid_grant", "Refresh token not found.")
        if not set(scopes).issubset(set(refresh_token.scopes)):
            raise TokenError("invalid_scope", "Requested scopes exceed those authorized by the refresh token.")
        self.repository.revoke_refresh(refresh_token.token)
        return self._issue_pair(client.client_id, scopes, stored.user_id, None)

    async def load_access_token(self, token: str) -> AccessToken | None:
        stored = self.repository.get_access(token)
        if stored is None:
            return None
        return stored.token

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        if isinstance(token, AccessToken):
            self.repository.revoke_access(token.token)
        else:
            self.repository.revoke_refresh(token.token)

    def get_routes(self, mcp_path: str | None = None) -> list[Route]:
        routes = super().get_routes(mcp_path)
        metadata = build_metadata(
            self.base_url,
            self.service_documentation_url,
            self.client_registration_options,
            self.revocation_options,
        )
        metadata.token_endpoint_auth_methods_supported = ["none", "client_secret_post", "client_secret_basic"]
        metadata_route = Route(
            "/.well-known/oauth-authorization-server",
            endpoint=cors_middleware(MetadataHandler(metadata).handle, ["GET", "OPTIONS"]),
            methods=["GET", "OPTIONS"],
        )
        replaced: list[Route] = []
        protected_endpoint = None
        for route in routes:
            if isinstance(route, Route) and route.path == "/authorize":
                replaced.append(Route("/authorize", endpoint=self._authorize_http, methods=["GET", "POST"]))
            elif isinstance(route, Route) and route.path == "/.well-known/oauth-authorization-server":
                replaced.append(metadata_route)
            else:
                if isinstance(route, Route) and route.path.startswith("/.well-known/oauth-protected-resource"):
                    protected_endpoint = route.endpoint
                replaced.append(route)
        if protected_endpoint is not None:
            replaced.append(
                Route(
                    "/.well-known/oauth-protected-resource",
                    endpoint=protected_endpoint,
                    methods=["GET", "OPTIONS"],
                )
            )
        issuer_path = str(self.issuer_url).rstrip("/").split("/", 3)[-1] if self.issuer_url else ""
        parsed_path = ""
        if self.issuer_url is not None:
            from urllib.parse import urlparse

            parsed_path = urlparse(str(self.issuer_url)).path.rstrip("/")
        if parsed_path and parsed_path != "/":
            replaced.append(
                Route(
                    f"/.well-known/oauth-authorization-server{parsed_path}",
                    endpoint=metadata_route.endpoint,
                    methods=["GET", "OPTIONS"],
                )
            )
        del issuer_path
        return replaced

    async def _authorize_http(self, request: Request) -> HTMLResponse | RedirectResponse:
        if request.method == "POST":
            form = await request.form()
            params = dict(request.query_params)
            params.update({key: value for key, value in form.items() if isinstance(value, str)})
        else:
            params = dict(request.query_params)
        decision = params.get("decision")
        try:
            auth_request = AuthorizationRequest.model_validate(params)
        except ValidationError:
            return HTMLResponse("The authorization request is missing required OAuth fields.", status_code=400)

        client = await self.get_client(auth_request.client_id)
        if client is None:
            return HTMLResponse("Unknown OAuth client. Register the client and try again.", status_code=400)
        try:
            redirect_uri = client.validate_redirect_uri(auth_request.redirect_uri)
            scopes = client.validate_scope(auth_request.scope)
        except InvalidRedirectUriError as exc:
            return HTMLResponse(exc.message, status_code=400)
        except InvalidScopeError as exc:
            return RedirectResponse(
                construct_redirect_uri(
                    str(auth_request.redirect_uri or ""),
                    error="invalid_scope",
                    error_description=exc.message,
                    state=auth_request.state,
                ),
                status_code=302,
            )

        owner_id = self.owner_lookup(request)
        if owner_id is None:
            return HTMLResponse(_login_page(self._login_url()), status_code=200)
        if request.method != "POST" or decision != "allow":
            if decision == "deny":
                return RedirectResponse(
                    construct_redirect_uri(
                        str(redirect_uri),
                        error="access_denied",
                        error_description="The owner denied this ChatGPT connection.",
                        state=auth_request.state,
                    ),
                    status_code=302,
                )
            return HTMLResponse(_consent_page(auth_request, params), status_code=200)

        raw_code = secrets.token_urlsafe(32)
        self.repository.save_code(
            AuthorizationCode(
                code=raw_code,
                scopes=list(scopes or []),
                expires_at=time.time() + CODE_TTL,
                client_id=client.client_id or auth_request.client_id,
                code_challenge=auth_request.code_challenge,
                redirect_uri=redirect_uri,
                redirect_uri_provided_explicitly=auth_request.redirect_uri is not None,
                resource=auth_request.resource,
            ),
            owner_id,
        )
        return RedirectResponse(
            construct_redirect_uri(str(redirect_uri), code=raw_code, state=auth_request.state),
            status_code=302,
        )

    def _issue_pair(self, client_id: str, scopes: list[str], user_id: int, resource: str | None) -> OAuthToken:
        access_raw = secrets.token_urlsafe(32)
        refresh_raw = secrets.token_urlsafe(32)
        now = int(time.time())
        access = AccessToken(
            token=access_raw,
            client_id=client_id,
            scopes=scopes,
            expires_at=now + ACCESS_TTL,
            resource=resource,
        )
        refresh = RefreshToken(
            token=refresh_raw,
            client_id=client_id,
            scopes=scopes,
            expires_at=now + REFRESH_TTL,
        )
        self.repository.save_token_pair(access, refresh, user_id)
        return OAuthToken(
            access_token=access_raw,
            token_type="Bearer",
            expires_in=ACCESS_TTL,
            refresh_token=refresh_raw,
            scope=" ".join(scopes),
        )

    def _login_url(self) -> str:
        from app.config import get_settings

        settings = get_settings()
        return (settings.frontend_base_url or settings.public_base_url or "/").rstrip("/") or "/"


def _hidden(name: str, value: str | None) -> str:
    if value is None:
        return ""
    return f'<input type="hidden" name="{html.escape(name)}" value="{html.escape(value)}" />'


def _consent_page(auth_request: AuthorizationRequest, params: dict[str, str]) -> str:
    fields = [
        _hidden("client_id", auth_request.client_id),
        _hidden("redirect_uri", str(auth_request.redirect_uri) if auth_request.redirect_uri else None),
        _hidden("response_type", auth_request.response_type),
        _hidden("code_challenge", auth_request.code_challenge),
        _hidden("code_challenge_method", auth_request.code_challenge_method),
        _hidden("state", auth_request.state),
        _hidden("scope", auth_request.scope),
        _hidden("resource", auth_request.resource or params.get("resource")),
    ]
    hidden = "\n".join(field for field in fields if field)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Allow ChatGPT</title></head>
<body style="font-family: sans-serif; max-width: 36rem; margin: 3rem auto;">
<h1>Connect ChatGPT</h1>
<p>This lets ChatGPT read the Strava activities stored for your account. It cannot change Strava or this service.</p>
<form method="post">
{hidden}
<button type="submit" name="decision" value="allow">Allow</button>
<button type="submit" name="decision" value="deny">Deny</button>
</form>
</body></html>"""


def _login_page(login_url: str) -> str:
    safe_url = html.escape(login_url, quote=True)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Sign in required</title></head>
<body style="font-family: sans-serif; max-width: 36rem; margin: 3rem auto;">
<h1>Sign in first</h1>
<p>ChatGPT can connect only while you are signed in to this Strava dashboard.</p>
<p><a href="{safe_url}">Open the dashboard</a>, sign in, then retry the ChatGPT connection.</p>
</body></html>"""


def metadata_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/.well-known/oauth-protected-resource"


def query(params: dict[str, str]) -> str:
    return urlencode(params)
