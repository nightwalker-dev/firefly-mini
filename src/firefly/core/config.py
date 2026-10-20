"""Layered Configuration Engine with Pydantic Schema Validation and Feature Flags.

Hierarchy:
  Defaults -> config.toml -> FIREFLY_* environment variables -> CLI overrides.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

from firefly.core.platform import secure_chmod, user_config_dir, user_data_dir

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]


def _xdg(var: str, fallback: str) -> Path:
    """Backwards-compatible helper; prefer :func:`user_data_dir` / :func:`user_config_dir`."""
    if var == "XDG_CONFIG_HOME":
        return user_config_dir()
    if var == "XDG_DATA_HOME":
        return user_data_dir()
    return Path(os.environ.get(var, str(Path.home() / fallback))) / "firefly-mini"


def _to_bool(value: str) -> bool:
    v = value.strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off", ""):
        return False
    raise ValueError(f"expected a boolean (true/false), got '{value}'")


class FeatureFlags(BaseModel):
    """Toggles for optional subsystems."""

    enable_voice: bool = True
    enable_vision: bool = True
    enable_hud: bool = True
    enable_audio_sfx: bool = True
    enable_mfa: bool = True


class LLMConfig(BaseModel):
    """Large Language Model and VLM endpoints."""

    base_url: str = "http://localhost:11434/v1"
    api_key: str = "ollama"
    model: str = "qwen2.5:7b-instruct"
    vlm_model: str = "qwen2.5vl:7b"
    timeout: float = Field(default=120.0, gt=0, le=3600)
    max_retries: int = Field(default=2, ge=0, le=10)

    @field_validator("base_url")
    @classmethod
    def _check_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        return v.rstrip("/")


class VoiceConfig(BaseModel):
    """Audio speech synthesis and transcription settings."""

    whisper_model: str = "base.en"
    whisper_device: str = "auto"
    wake_word: str = "firefly"
    piper_bin: str = "piper"
    piper_model: str = ""


class GuardrailsConfig(BaseModel):
    """Security boundaries and privilege thresholds."""

    auto_approve_max_risk: int = Field(default=1, ge=0, le=4)
    input_rate_limit: float = Field(default=10.0, gt=0)
    shell_timeout: float = Field(default=120.0, gt=0, le=86400)
    max_output_chars: int = Field(default=12000, ge=256)
    totp_secret: Optional[str] = None


class PathConfig(BaseModel):
    """Filesystem directories and database paths (OS-aware defaults)."""

    data_dir: Path = Field(default_factory=user_data_dir)
    config_dir: Path = Field(default_factory=user_config_dir)

    @property
    def audit_db(self) -> Path:
        return self.data_dir / "audit.db"

    @property
    def audit_key(self) -> Path:
        return self.data_dir / "audit.key"

    @property
    def checkpoint_dir(self) -> Path:
        return self.data_dir / "checkpoints"

    @property
    def stop_file(self) -> Path:
        return self.data_dir / "STOP"

    @property
    def sounds_dir(self) -> Path:
        return self.data_dir / "sounds"


class FireflyConfig(BaseModel):
    """Root configuration model with complete validation."""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    guardrails: GuardrailsConfig = Field(default_factory=GuardrailsConfig)
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    paths: PathConfig = Field(default_factory=PathConfig)
    max_steps: int = Field(default=15, ge=1, le=100)
    shell: str = "auto"  # auto | bash | sh | zsh | pwsh | powershell | cmd | /abs/path

    # ----------------- Compatibility Properties -----------------
    @property
    def llm_base_url(self) -> str:
        return self.llm.base_url

    @property
    def llm_api_key(self) -> str:
        return self.llm.api_key

    @property
    def llm_model(self) -> str:
        return self.llm.model

    @property
    def vlm_model(self) -> str:
        return self.llm.vlm_model

    @property
    def llm_timeout(self) -> float:
        return self.llm.timeout

    @property
    def auto_approve_max_risk(self) -> int:
        return self.guardrails.auto_approve_max_risk

    @property
    def input_rate_limit(self) -> float:
        return self.guardrails.input_rate_limit

    @property
    def shell_timeout(self) -> float:
        return self.guardrails.shell_timeout

    @property
    def max_output_chars(self) -> int:
        return self.guardrails.max_output_chars

    @property
    def totp_secret(self) -> Optional[str]:
        return self.guardrails.totp_secret

    @property
    def whisper_model(self) -> str:
        return self.voice.whisper_model

    @property
    def whisper_device(self) -> str:
        return self.voice.whisper_device

    @property
    def wake_word(self) -> str:
        return self.voice.wake_word

    @property
    def piper_bin(self) -> str:
        return self.voice.piper_bin

    @property
    def piper_model(self) -> str:
        return self.voice.piper_model

    @property
    def data_dir(self) -> Path:
        return self.paths.data_dir

    @property
    def config_dir(self) -> Path:
        return self.paths.config_dir

    @property
    def audit_db(self) -> Path:
        return self.paths.audit_db

    @property
    def audit_key(self) -> Path:
        return self.paths.audit_key

    @property
    def checkpoint_dir(self) -> Path:
        return self.paths.checkpoint_dir

    @property
    def stop_file(self) -> Path:
        return self.paths.stop_file

    @property
    def sounds_dir(self) -> Path:
        return self.paths.sounds_dir

    def ensure_dirs(self) -> None:
        for d in (
            self.paths.data_dir,
            self.paths.config_dir,
            self.paths.checkpoint_dir,
            self.paths.sounds_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)
        secure_chmod(self.paths.data_dir, 0o700)


def default_config_path() -> Path:
    """Location of the per-user ``config.toml``."""
    return user_config_dir() / "config.toml"


def load_config(
    toml_path: Optional[Path] = None,
    cli_overrides: Optional[Dict[str, Any]] = None,
) -> FireflyConfig:
    """Loads and validates layered configuration with clear error reporting."""
    raw: Dict[str, Any] = {
        "llm": {},
        "voice": {},
        "guardrails": {},
        "features": {},
        "paths": {},
    }

    # 1. TOML layer (explicit path > ./config.toml > per-user config.toml)
    target_toml = toml_path or Path(os.environ.get("FIREFLY_CONFIG", "config.toml"))
    if not target_toml.exists():
        target_toml = default_config_path()

    if target_toml.exists():
        try:
            with open(target_toml, "rb") as f:
                toml_data = tomllib.load(f)
                for sec in ("llm", "voice", "guardrails", "features", "paths"):
                    if sec in toml_data and isinstance(toml_data[sec], dict):
                        raw[sec].update(toml_data[sec])
                if "max_steps" in toml_data:
                    raw["max_steps"] = toml_data["max_steps"]
                if "shell" in toml_data:
                    raw["shell"] = toml_data["shell"]
        except Exception as exc:
            raise ValueError(f"Failed parsing configuration file '{target_toml}': {exc}") from exc

    # 2. Environment variables layer (FIREFLY_*)
    #    value = (section, key[, converter])  or  (root_key, converter)
    env_map: Dict[str, tuple[Any, ...]] = {
        "FIREFLY_LLM_BASE_URL": ("llm", "base_url"),
        "FIREFLY_LLM_API_KEY": ("llm", "api_key"),
        "FIREFLY_LLM_MODEL": ("llm", "model"),
        "FIREFLY_VLM_MODEL": ("llm", "vlm_model"),
        "FIREFLY_LLM_TIMEOUT": ("llm", "timeout", float),
        "FIREFLY_LLM_MAX_RETRIES": ("llm", "max_retries", int),
        "FIREFLY_WHISPER_MODEL": ("voice", "whisper_model"),
        "FIREFLY_WHISPER_DEVICE": ("voice", "whisper_device"),
        "FIREFLY_WAKE_WORD": ("voice", "wake_word"),
        "FIREFLY_PIPER_BIN": ("voice", "piper_bin"),
        "FIREFLY_PIPER_MODEL": ("voice", "piper_model"),
        "FIREFLY_AUTO_APPROVE_MAX_RISK": ("guardrails", "auto_approve_max_risk", int),
        "FIREFLY_INPUT_RATE_LIMIT": ("guardrails", "input_rate_limit", float),
        "FIREFLY_SHELL_TIMEOUT": ("guardrails", "shell_timeout", float),
        "FIREFLY_MAX_OUTPUT_CHARS": ("guardrails", "max_output_chars", int),
        "FIREFLY_TOTP_SECRET": ("guardrails", "totp_secret"),
        "FIREFLY_ENABLE_VOICE": ("features", "enable_voice", _to_bool),
        "FIREFLY_ENABLE_VISION": ("features", "enable_vision", _to_bool),
        "FIREFLY_ENABLE_HUD": ("features", "enable_hud", _to_bool),
        "FIREFLY_ENABLE_AUDIO_SFX": ("features", "enable_audio_sfx", _to_bool),
        "FIREFLY_ENABLE_MFA": ("features", "enable_mfa", _to_bool),
        "FIREFLY_MAX_STEPS": ("max_steps", int),
        "FIREFLY_SHELL": ("shell", str),
    }

    for env_var, m in env_map.items():
        val = os.environ.get(env_var)
        if val is None:
            continue
        try:
            if len(m) == 2 and callable(m[1]) and not isinstance(m[1], str):
                conv_root: Callable[[str], Any] = m[1]
                raw[str(m[0])] = conv_root(val)
            elif len(m) == 2:
                raw[str(m[0])][str(m[1])] = val
            else:
                conv: Callable[[str], Any] = m[2]
                raw[str(m[0])][str(m[1])] = conv(val)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid Firefly configuration:\n  {env_var}={val!r}: {exc}") from exc

    # 3. CLI Overrides layer
    if cli_overrides:
        for k, v in cli_overrides.items():
            if "." in k:
                sec, subkey = k.split(".", 1)
                if sec in raw and isinstance(raw[sec], dict):
                    raw[sec][subkey] = v
            else:
                raw[k] = v

    try:
        return FireflyConfig(**raw)
    except ValidationError as err:
        errors = [f"{e['loc']}: {e['msg']}" for e in err.errors()]
        raise ValueError("Invalid Firefly configuration:\n  " + "\n  ".join(errors)) from err


# Export default settings singleton for zero-overhead import compatibility
settings = load_config()
