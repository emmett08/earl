"""Read and validate operator-owned opaque bearer credentials without disclosure."""

from collections.abc import Mapping
import os
import re


_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*", re.ASCII)


def validate_bearer_token(token: str) -> None:
    """Require a token that both HTTP server and client can represent exactly."""
    if (not isinstance(token, str) or not token
            or any(character.isspace() or not 33 <= ord(character) <= 126 for character in token)):
        raise ValueError("HTTP bearer token must contain only non-whitespace printable ASCII characters")


def read_bearer_token(token_env: str | None,
                      environ: Mapping[str, str] | None = None) -> str | None:
    """Read one credential; diagnostics identify the variable without its value."""
    if token_env is None:
        return None
    if not isinstance(token_env, str) or not _ENV_NAME.fullmatch(token_env):
        raise ValueError("token_env must name an environment variable")
    environ = os.environ if environ is None else environ
    token = environ.get(token_env)
    if not isinstance(token, str) or not token:
        raise ValueError(f"HTTP bearer token environment variable {token_env} is missing or empty")
    try:
        validate_bearer_token(token)
    except ValueError:
        raise ValueError(f"HTTP bearer token environment variable {token_env} contains invalid characters") from None
    return token
