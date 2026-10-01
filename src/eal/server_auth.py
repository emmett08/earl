"""Authenticate HTTP callers within one operator-configured EAL trust domain."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import hmac

from fastmcp.server.auth import AccessToken, TokenVerifier

from .credentials import read_bearer_token, validate_bearer_token
from .server_settings import ServerSettings


class BearerTokenVerifier(TokenVerifier):
    """Verify an opaque token while retaining only its SHA-256 digest."""

    def __init__(self, secret: str):
        validate_bearer_token(secret)
        super().__init__()
        self._token_digest = hashlib.sha256(secret.encode("utf-8")).digest()

    async def verify_token(self, token: str) -> AccessToken | None:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        if not hmac.compare_digest(digest, self._token_digest):
            return None
        return AccessToken(token=token, client_id="eal-operator", subject="eal-operator",
                           scopes=["eal:invoke"])


def configured_auth(settings: ServerSettings, *,
                    environ: Mapping[str, str] | None = None) -> TokenVerifier | None:
    """Read a configured credential without adding its value to settings or diagnostics."""
    if settings.transport != "http" or settings.token_env is None:
        return None
    secret = read_bearer_token(settings.token_env, environ)
    return BearerTokenVerifier(secret)
