"""Credential validation precedes service state creation at the composition boundary."""

import asyncio

import pytest

from eal.server import build_server
from eal.server_auth import configured_auth
from eal.server_settings import ServerSettings


TOKEN_ENV = "EAL_TEST_OPERATOR_TOKEN"


@pytest.mark.parametrize("environment", [
    {},
    {TOKEN_ENV: ""},
    {TOKEN_ENV: "secret with spaces"},
    {TOKEN_ENV: "secret\twith-tab"},
    {TOKEN_ENV: "secret\nwith-newline"},
    {TOKEN_ENV: "secret-\u00e9"},
    {TOKEN_ENV: "secret-\x7f"},
])
def test_invalid_http_credentials_fail_before_creating_service_state(tmp_path, environment):
    workspace = tmp_path / "workspace"
    database = tmp_path / "database" / "runs.sqlite3"
    settings = ServerSettings(workspace=workspace, database=database,
                              transport="http", token_env=TOKEN_ENV)

    with pytest.raises(ValueError, match=TOKEN_ENV) as rejected:
        build_server(settings, environ=environment)

    secret = environment.get(TOKEN_ENV)
    if secret:
        assert secret not in str(rejected.value)
    assert not workspace.exists()
    assert not database.parent.exists()
    assert list(tmp_path.iterdir()) == []


def test_configured_http_verifier_accepts_only_the_configured_token(tmp_path):
    secret = "test-operator-token.ABC_123~"
    settings = ServerSettings(workspace=tmp_path, transport="http", token_env=TOKEN_ENV)
    verifier = configured_auth(settings, environ={TOKEN_ENV: secret})
    assert verifier is not None

    accepted = asyncio.run(verifier.verify_token(secret))
    assert accepted is not None
    assert accepted.client_id == "eal-operator"
    assert accepted.subject == "eal-operator"
    assert accepted.scopes == ["eal:invoke"]
    assert asyncio.run(verifier.verify_token(secret + "-wrong")) is None
    assert asyncio.run(verifier.verify_token("")) is None
    assert secret not in repr(settings)
    assert secret not in repr(verifier)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("environment", [{}, {TOKEN_ENV: "unused invalid credential"}])
def test_stdio_does_not_require_or_read_the_unused_http_credential(tmp_path, environment):
    settings = ServerSettings(workspace=tmp_path, token_env=TOKEN_ENV)
    server = build_server(settings, environ=environment)

    assert server.auth is None
    assert (tmp_path / ".eal" / "runs.sqlite3").is_file()
