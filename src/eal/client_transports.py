"""Transport factories for the one-shot host client.

These factories select connections without constructing the application service.
HTTP targets refer to existing servers; stdio targets own one subprocess for the
duration of the request. Credentials are obtained from the trusted environment.
"""

from __future__ import annotations

from collections.abc import Mapping
import ipaddress
from urllib.parse import urlsplit, urlunsplit

from fastmcp.client.transports import ClientTransport, StdioTransport, StreamableHttpTransport
from mcp import StdioServerParameters

from .credentials import read_bearer_token


def create_client_transport(parameters: StdioServerParameters | ClientTransport) -> ClientTransport:
    """Use a transport directly or translate the host's stdio launch contract."""
    if isinstance(parameters, ClientTransport):
        return parameters
    if not isinstance(parameters, StdioServerParameters):
        raise TypeError("Host target must be an MCP client transport or StdioServerParameters")
    if parameters.encoding.lower().replace("_", "-") != "utf-8" or parameters.encoding_error_handler != "strict":
        raise ValueError("FastMCP stdio requires strict UTF-8 encoding")
    return StdioTransport(command=parameters.command, args=parameters.args,
                          env=parameters.env, cwd=parameters.cwd, keep_alive=False)


def validate_http_url(url: str) -> str:
    """Validate an explicit HTTP endpoint without credentials in its URL."""
    if not isinstance(url, str) or not url or any(character.isspace() or ord(character) < 32 for character in url):
        raise ValueError("HTTP URL must be a non-empty URL without whitespace")
    try:
        parsed = urlsplit(url)
        port = parsed.port
        host = parsed.hostname
    except ValueError as exc:
        raise ValueError("HTTP URL has an invalid host or port") from exc
    if parsed.scheme not in {"http", "https"} or not host or port == 0:
        raise ValueError("HTTP URL must use http or https with a valid hostname and port")
    if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
        raise ValueError("HTTP URL must not contain credentials, a query or a fragment")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def create_http_transport(url: str, *, token_env: str | None = None,
                          environ: Mapping[str, str] | None = None,
                          httpx_client_factory=None) -> StreamableHttpTransport:
    """Connect to an existing HTTP server, requiring a token beyond loopback.

The optional HTTP client factory supports controlled embedding and local tests.
Ordinary clients retain the HTTP library's environment proxy configuration.
"""
    url = validate_http_url(url)
    host = urlsplit(url).hostname
    loopback = host.lower().rstrip(".") == "localhost"
    try:
        loopback = loopback or ipaddress.ip_address(host).is_loopback
    except ValueError:
        pass
    if not loopback and token_env is None:
        raise ValueError("HTTP connections beyond loopback require --token-env authentication")
    token = read_bearer_token(token_env, environ)
    return StreamableHttpTransport(url, auth=token, httpx_client_factory=httpx_client_factory)
