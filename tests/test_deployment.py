"""Deployment configuration checks.

These are cheap consistency assertions over the files a hosting platform reads.
They catch the failure modes that only surface after a deploy - a hard-coded
port, a health check pointing at a path the server does not serve, a secret that
would be baked into the image.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest

from pitchdeck_onepager.config import HOSTING_ENV_VARS, AppConfig, is_hosted_environment

ROOT = Path(__file__).resolve().parent.parent

#: The endpoint Streamlit serves and railway.json health-checks.
HEALTH_PATH = "/_stcore/health"


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


# --- Hosting detection --------------------------------------------------------


def test_local_run_is_not_treated_as_hosted(monkeypatch) -> None:
    for name in HOSTING_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    assert is_hosted_environment() is False


@pytest.mark.parametrize("variable", HOSTING_ENV_VARS)
def test_platform_variables_flag_a_hosted_run(monkeypatch, variable: str) -> None:
    for name in HOSTING_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(variable, "production")
    assert is_hosted_environment() is True


def test_api_key_is_read_from_the_environment_at_call_time(monkeypatch) -> None:
    """Platform variables are injected at runtime, not at import time."""
    config = AppConfig.from_env(provider="anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    assert config.api_key() == "sk-ant-not-a-real-key"

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert config.api_key() is None


def test_secrets_never_appear_in_the_redacted_config(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    redacted = json.dumps(AppConfig.from_env().redacted())

    assert "sk-ant" not in redacted
    assert "api_key" not in redacted


# --- Start command / port binding --------------------------------------------


def _start_commands() -> dict[str, str]:
    """The actual start command each platform file declares.

    Extracted rather than grepped over whole files: an earlier version of these
    tests scanned raw file contents, so a `$PORT` mentioned in a *comment*
    satisfied the assertion while the real command was wrong.
    """
    procfile = next(
        line.split(":", 1)[1].strip()
        for line in _read("Procfile").splitlines()
        if line.startswith("web:")
    )
    dockerfile = next(
        line[len("CMD ") :].strip()
        for line in _read("Dockerfile").splitlines()
        if line.startswith("CMD ")
    )
    railway = json.loads(_read("railway.json"))["deploy"]["startCommand"]
    return {"Procfile": procfile, "Dockerfile": dockerfile, "railway.json": railway}


@pytest.mark.parametrize("filename", ["Procfile", "Dockerfile", "railway.json"])
def test_start_command_binds_the_injected_port(filename: str) -> None:
    command = _start_commands()[filename]

    # Braced form only. Railway does not shell-expand every start command path -
    # a bare `$PORT` reached Streamlit as a literal and it exited with
    # "'$PORT' is not a valid integer". `${PORT:-8501}` still needs a shell, so
    # the Procfile wraps itself in `sh -c`.
    assert "${PORT:-8501}" in command, f"{filename} must use the braced, defaulted port"
    assert not re.search(r"\$PORT\b", command), f"{filename} has an unbraced $PORT"

    # `::` and not `0.0.0.0`: Railway runs its health check over an IPv6-only
    # internal network, and an IPv4 bind makes every attempt fail with "service
    # unavailable" on a container that started perfectly. A `::` socket on Linux
    # accepts IPv4 as well, so this loses nothing.
    assert "--server.address=::" in command, f"{filename} must bind dual-stack"
    assert "--server.address=0.0.0.0" not in command, f"{filename} must not bind IPv4-only"


@pytest.mark.parametrize("filename", ["Procfile", "railway.json"])
def test_start_command_forces_a_shell_so_the_port_expands(filename: str) -> None:
    """Railway execs these directly; without `sh -c` ${PORT} stays literal.

    This is the failure that produced "'$PORT' is not a valid integer" - the
    Dockerfile CMD is shell form already, but neither of these two is.
    """
    assert _start_commands()[filename].startswith("sh -c ")


def test_no_hard_coded_port_in_start_commands() -> None:
    """A literal port would make the platform's health check fail."""
    for filename, command in _start_commands().items():
        assert "--server.port=8501" not in command, filename


def test_railway_config_is_valid_and_points_at_the_real_health_endpoint() -> None:
    config = json.loads(_read("railway.json"))

    assert config["build"]["builder"] == "DOCKERFILE"
    assert config["deploy"]["healthcheckPath"] == HEALTH_PATH
    # An explicit startCommand is required, not optional: with it absent Railway
    # falls back to the Procfile rather than the Dockerfile CMD.
    assert "streamlit run streamlit_app.py" in config["deploy"]["startCommand"]


def test_dockerfile_runs_as_a_non_root_user() -> None:
    dockerfile = _read("Dockerfile")

    assert "USER appuser" in dockerfile
    assert dockerfile.index("USER appuser") < dockerfile.index("CMD "), "USER must precede CMD"


def test_dockerfile_gives_the_non_root_user_a_writable_home() -> None:
    """Docker does not move HOME when USER changes.

    Left at /root, Streamlit dies creating ~/.streamlit before it binds a port.
    """
    dockerfile = _read("Dockerfile")

    assert "ENV HOME=/home/appuser" in dockerfile
    assert dockerfile.index("USER appuser") < dockerfile.index("ENV HOME=")


# --- Image hygiene ------------------------------------------------------------


def test_dockerignore_excludes_secrets_and_confidential_material() -> None:
    ignored = {line.strip() for line in _read(".dockerignore").splitlines()}

    assert ".env" in ignored, "the .env file must never be copied into the image"
    for path in ("input/*", "output/*", "temp/*"):
        assert path in ignored, f"{path} must be excluded from the image"


def test_env_example_contains_no_real_secret() -> None:
    for line in _read(".env.example").splitlines():
        if line.startswith(("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "APP_PASSWORD")):
            assert line.split("=", 1)[1].strip() == "", f"{line} must ship empty"


def test_gitignore_excludes_the_env_file() -> None:
    assert ".env" in {line.strip() for line in _read(".gitignore").splitlines()}


# --- Streamlit runtime config -------------------------------------------------


def test_streamlit_config_is_deployment_safe() -> None:
    config = tomllib.loads(_read(".streamlit/config.toml"))

    assert config["server"]["headless"] is True
    assert config["server"]["enableXsrfProtection"] is True
    # Streamlit silently overrides enableCORS when XSRF is on; setting it only
    # produces a startup warning.
    assert "enableCORS" not in config["server"]
    assert config["client"]["showErrorDetails"] == "none", "no tracebacks on a public URL"
    assert config["browser"]["gatherUsageStats"] is False
    assert 0 < config["server"]["maxUploadSize"] <= 200
