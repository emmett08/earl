"""Host configuration checks independently of MCP or acquisition code."""

from dataclasses import FrozenInstanceError
import pytest

from eal.server_settings import ServerSettings, parse_server_settings


def write_config(tmp_path, content):
    path = tmp_path / "mcp.toml"
    path.write_text(content, encoding="utf-8")
    return path


def test_defaults_are_immutable_and_do_not_create_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = parse_server_settings([], {})
    assert settings == ServerSettings(workspace=tmp_path)
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(FrozenInstanceError):
        settings.transport = "http"


def test_cli_environment_file_precedence_and_path_origins(tmp_path, monkeypatch):
    file_dir = tmp_path / "file"
    file_dir.mkdir()
    config = write_config(file_dir, '''
[service]
workspace = "workspace"
registry = "registry.toml"
database = "database.sqlite"
methods = "package.module:factory"
limits = "limits.toml"
[server]
transport = "http"
max_in_flight = 2
[server.http]
port = 8001
path = "/file"
''')
    monkeypatch.chdir(tmp_path)
    settings = parse_server_settings(
        ["--config", str(config), "--workspace", "cli", "--port", "8003"],
        {"EAL_MCP_WORKSPACE": "env", "EAL_MCP_DATABASE": "env.sqlite",
         "EAL_MCP_PORT": "8002", "EAL_MCP_PATH": "/env"},
    )
    assert settings.workspace == tmp_path / "cli"
    assert settings.registry == file_dir / "registry.toml"
    assert settings.database == tmp_path / "env.sqlite"
    assert settings.limits == file_dir / "limits.toml"
    assert settings.methods == "package.module:factory"
    assert settings.port == 8003
    assert settings.path == "/env"
    assert settings.transport == "http"
    assert settings.max_in_flight == 2


def test_config_environment_and_cli_selection(tmp_path):
    selected = write_config(tmp_path, '[server]\nmax_in_flight = 3\n')
    assert parse_server_settings([], {"EAL_MCP_CONFIG": str(selected)}).max_in_flight == 3
    assert parse_server_settings(["--config", str(selected)], {"EAL_MCP_CONFIG": "missing.toml"}).max_in_flight == 3


def test_repeated_cli_known_entries_select_registered_exposure_and_replace_env():
    settings = parse_server_settings(
        ["--known-entry", "one", "--known-entry", "two"],
        {"EAL_MCP_KNOWN_ENTRIES": '["environment"]'},
    )
    assert settings.known_entries == ("one", "two")
    assert settings.exposure == "registered"


def test_environment_known_entries_are_json_and_select_registered_exposure():
    settings = parse_server_settings([], {"EAL_MCP_KNOWN_ENTRIES": ' ["one", "two"] '})
    assert settings.known_entries == ("one", "two")
    assert settings.exposure == "registered"


def test_cli_overrides_invalid_lower_priority_environment_values():
    settings = parse_server_settings(
        ["--port", "8003", "--known-entry", "one"],
        {"EAL_MCP_PORT": "invalid", "EAL_MCP_KNOWN_ENTRIES": "invalid"},
    )
    assert settings.port == 8003
    assert settings.known_entries == ("one",)


@pytest.mark.parametrize("content", [
    '[unknown]\nvalue = 1',
    '[service]\nworkspce = "missing"',
    '[server]\ntransprot = "stdio"',
    '[server.http]\nports = 8000',
    'service = "wrong"',
    '[server]\nhttp = "wrong"',
])
def test_unknown_keys_and_wrong_table_types_rejected(tmp_path, content):
    with pytest.raises(ValueError):
        parse_server_settings(["--config", str(write_config(tmp_path, content))], {})


@pytest.mark.parametrize("content, message", [
    ('[server]\ntransport = "websocket"', "transport"),
    ('[server]\ntransport = true', "transport"),
    ('[server]\ntransport = ["stdio"]', "transport"),
    ('[server]\nexposure = "public"', "exposure"),
    ('[server]\nmax_in_flight = true', "max_in_flight"),
    ('[server]\nmax_in_flight = 0', "max_in_flight"),
    ('[server]\nmax_in_flight = 1025', "max_in_flight"),
    ('[server.http]\nport = true', "port"),
    ('[server.http]\nport = 8000.0', "port"),
    ('[server.http]\nport = 65536', "port"),
    ('[server.http]\npath = "mcp"', "path"),
    ('[server.http]\npath = "/mcp?secret=yes"', "path"),
    ('[server.http]\npath = "/../mcp"', "path"),
    ('[server.http]\nhost = "https://example.org"', "host"),
    ('[server.http]\ntoken_env = "TOKEN-VALUE"', "token_env"),
    ('[service]\nworkspace = true', "workspace"),
    ('[service]\nmethods = "module.factory"', "methods"),
    ('[service]\nknown_entries = "one"', "known_entries"),
    ('[service]\nknown_entries = ["one", "one"]', "known_entries"),
    ('[service]\nknown_entries = [true]', "known_entries"),
])
def test_invalid_resolved_values_rejected(tmp_path, content, message):
    with pytest.raises(ValueError, match=message):
        parse_server_settings(["--config", str(write_config(tmp_path, content))], {})


def test_registered_empty_selection_fails_closed(tmp_path):
    config = write_config(tmp_path, '[server]\nexposure = "registered"\n')
    with pytest.raises(ValueError, match="requires at least one"):
        parse_server_settings(["--config", str(config)], {})
    with pytest.raises(ValueError, match="requires at least one"):
        parse_server_settings([], {"EAL_MCP_EXPOSURE": "registered", "EAL_MCP_KNOWN_ENTRIES": "[]"})


def test_explicit_operator_conflicts_with_known_entries(tmp_path):
    config = write_config(tmp_path, '[server]\nexposure = "operator"\n')
    with pytest.raises(ValueError, match="conflicts"):
        parse_server_settings(["--config", str(config), "--known-entry", "one"], {})


def test_known_entries_have_a_bounded_unique_collection():
    with pytest.raises(ValueError, match="128 unique"):
        ServerSettings(known_entries=tuple(str(number) for number in range(129)), exposure="registered")
    with pytest.raises(ValueError, match="128 unique"):
        ServerSettings(known_entries=(" ",), exposure="registered")


@pytest.mark.parametrize("host", ["127.0.0.1", "127.1.2.3", "::1", "localhost", "localhost."])
def test_loopback_http_can_run_without_authentication(host):
    assert parse_server_settings(["--transport", "http", "--host", host], {}).token_env is None


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.1", "example.org"])
def test_remote_http_requires_authentication(host):
    with pytest.raises(ValueError, match="requires token_env"):
        parse_server_settings(["--transport", "http", "--host", host], {})


def test_token_variable_name_is_stored_without_reading_credential():
    settings = parse_server_settings(
        ["--transport", "http", "--host", "0.0.0.0", "--token-env", "EAL_TOKEN"],
        {"EAL_TOKEN": "secret-never-in-settings"},
    )
    assert settings.token_env == "EAL_TOKEN"
    assert "secret-never-in-settings" not in repr(settings)
    assert parse_server_settings(
        ["--transport", "http", "--host", "0.0.0.0", "--token-env", "EAL_TOKEN"], {},
    ).token_env == "EAL_TOKEN"


@pytest.mark.parametrize("environ", [
    {"EAL_MCP_PORT": "true"},
    {"EAL_MCP_MAX_IN_FLIGHT": "2.5"},
    {"EAL_MCP_KNOWN_ENTRIES": "one,two"},
    {"EAL_MCP_KNOWN_ENTRIES": '"one"'},
    {"EAL_MCP_WORKSPACE": ""},
])
def test_invalid_environment_values_rejected(environ):
    with pytest.raises(ValueError):
        parse_server_settings([], environ)


def test_missing_config_is_a_configuration_error(tmp_path):
    with pytest.raises(ValueError, match="Cannot read server configuration"):
        parse_server_settings(["--config", str(tmp_path / "missing.toml")], {})


def test_cli_unknown_option_uses_argparse_error():
    with pytest.raises(SystemExit) as error:
        parse_server_settings(["--tranport", "stdio"], {})
    assert error.value.code == 2
