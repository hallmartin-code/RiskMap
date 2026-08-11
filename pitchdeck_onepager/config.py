"""Application configuration.

Values come from (in order of precedence): explicit overrides -> environment
variables (including a local ``.env``) -> defaults. Secrets are read here but
never logged or serialised.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv

load_dotenv()

Provider = Literal["anthropic", "openai", "openai_compatible"]

#: Default model per provider. Only Anthropic gets a default - guessing an
#: OpenAI model id would silently pin the app to a model the user did not pick.
DEFAULT_MODELS: dict[str, str] = {"anthropic": "claude-opus-5"}

PROJECT_ROOT = Path(__file__).resolve().parent.parent

#: Variables set by common container hosts. Used to decide whether the app is
#: publicly reachable and therefore needs an access password.
HOSTING_ENV_VARS = ("RAILWAY_ENVIRONMENT", "RAILWAY_PUBLIC_DOMAIN", "RENDER", "FLY_APP_NAME")


def is_hosted_environment() -> bool:
    """True when running on a hosting platform rather than a local machine."""
    return any(os.environ.get(name) for name in HOSTING_ENV_VARS)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    raw = os.environ.get(name)
    return raw.strip() if raw and raw.strip() else default


@dataclass(frozen=True)
class AppConfig:
    """Immutable runtime configuration."""

    provider: Provider = "anthropic"
    model: str = ""
    effort: str = "high"
    max_tokens: int = 16000
    enable_fallback: bool = True

    page_size: str = "LETTER"
    show_source_references: bool = True
    keep_analysis_json: bool = True

    enable_ocr: bool = False
    libreoffice_path: str | None = None

    output_dir: Path = PROJECT_ROOT / "output"
    temp_dir: Path = PROJECT_ROOT / "temp"
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, **overrides: Any) -> "AppConfig":
        """Build config from environment, then apply non-``None`` overrides."""
        cfg = cls(
            provider=_env_str("LLM_PROVIDER", "anthropic").lower(),  # type: ignore[arg-type]
            model=_env_str("LLM_MODEL", ""),
            effort=_env_str("LLM_EFFORT", "high"),
            max_tokens=_env_int("LLM_MAX_TOKENS", 16000),
            enable_fallback=_env_bool("LLM_ENABLE_FALLBACK", True),
            page_size=_env_str("PAGE_SIZE", "LETTER").upper(),
            show_source_references=_env_bool("SHOW_SOURCE_REFERENCES", True),
            keep_analysis_json=_env_bool("KEEP_ANALYSIS_JSON", True),
            enable_ocr=_env_bool("ENABLE_OCR", False),
            libreoffice_path=os.environ.get("LIBREOFFICE_PATH") or None,
            output_dir=Path(_env_str("OUTPUT_DIR", str(PROJECT_ROOT / "output"))),
            temp_dir=Path(_env_str("TEMP_DIR", str(PROJECT_ROOT / "temp"))),
            log_level=_env_str("LOG_LEVEL", "INFO").upper(),
        )
        clean = {k: v for k, v in overrides.items() if v is not None}
        if clean:
            cfg = replace(cfg, **clean)
        return cfg

    @property
    def resolved_model(self) -> str:
        """Model id to send to the provider."""
        return self.model or DEFAULT_MODELS.get(self.provider, "")

    def api_key(self) -> str | None:
        """API key for the configured provider (never logged)."""
        if self.provider == "anthropic":
            return os.environ.get("ANTHROPIC_API_KEY")
        return os.environ.get("OPENAI_API_KEY")

    def base_url(self) -> str | None:
        if self.provider == "openai_compatible":
            return os.environ.get("OPENAI_BASE_URL")
        return None

    def ensure_dirs(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def redacted(self) -> dict[str, Any]:
        """Loggable view of the config - contains no secrets."""
        return {
            "provider": self.provider,
            "model": self.resolved_model,
            "effort": self.effort,
            "max_tokens": self.max_tokens,
            "page_size": self.page_size,
            "show_source_references": self.show_source_references,
            "enable_ocr": self.enable_ocr,
        }
