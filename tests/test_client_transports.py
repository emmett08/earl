"""Connection selection and credential handling for the text-only host."""

import pytest
from fastmcp.client.transports import StdioTransport, StreamableHttpTransport
from mcp import StdioServerParameters

from eal.client_transports import create_client_transport, create_http_transport, validate_http_url


def test_stdio_parameters_use_a_subprocess_owned_by_one_request(tmp_path):
    parameters = StdioServerParameters(command="python", args=["-m", "eal.server"],
                                      env={"EAL_SAMPLE": "value"}, cwd=str(tmp_path))
    transport = create_client_transport(parameters)
    assert isinstance(transport, StdioTransport)
    assert transport.command == parameters.command
    assert transport.args == parameters.args
    assert transport.env == parameters.env
    assert transport.cwd == parameters.cwd
    assert transport.keep_alive is False


def test_direct_client_transport_is_preserved():
    transport = StreamableHttpTransport("http://127.0.0.1:8000/mcp")
    assert create_client_transport(transport) is transport


@pytest.mark.parametrize("url", [
    "stdio://localhost/mcp", "https:///mcp", "http://user:secret@localhost/mcp",
    "http://localhost/mcp?token=secret", "http://localhost/mcp#fragment",
    "http://localhost:65536/mcp", "http://localhost:0/mcp", "http://localhost /mcp",
])
def test_http_endpoint_rejects_invalid_or_credential_bearing_urls(url):
    with pytest.raises(ValueError):
        validate_http_url(url)


@pytest.mark.parametrize("url", ["http://localhost/mcp", "http://127.0.0.1/mcp", "http://[::1]:8000/mcp"])
def test_loopback_http_can_connect_without_a_token(url):
    transport = create_http_transport(url, environ={})
    assert transport.url == url


def test_remote_http_requires_explicit_environment_authentication():
    with pytest.raises(ValueError, match="require --token-env"):
        create_http_transport("https://eal.example.com/mcp", environ={})
    with pytest.raises(ValueError, match="missing or empty"):
        create_http_transport("https://eal.example.com/mcp", token_env="EAL_TOKEN", environ={})
    transport = create_http_transport("https://eal.example.com/mcp", token_env="EAL_TOKEN",
                                      environ={"EAL_TOKEN": "token-value"})
    assert isinstance(transport, StreamableHttpTransport)
    assert "token-value" not in repr(transport)
    assert transport.httpx_client_factory is None


@pytest.mark.parametrize("token", ["", "secret\nvalue", "secret value", "secret\u00e9"])
def test_invalid_bearer_tokens_never_appear_in_diagnostics(token):
    with pytest.raises(ValueError) as caught:
        create_http_transport("http://localhost/mcp", token_env="EAL_TOKEN", environ={"EAL_TOKEN": token})
    if token:
        assert token not in str(caught.value)


def test_http_client_factory_is_explicitly_injectable():
    def factory(**kwargs):
        raise AssertionError("construction must not connect")
    transport = create_http_transport("http://127.0.0.1/mcp", httpx_client_factory=factory)
    assert transport.httpx_client_factory is factory


def test_invalid_token_variable_name_does_not_read_the_environment():
    with pytest.raises(ValueError, match="name an environment variable"):
        create_http_transport("http://localhost/mcp", token_env="bad name", environ={"bad name": "secret"})
