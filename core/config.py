"""Backward-compatibility shim for core.config -> firefly.core.config."""

from __future__ import annotations

from firefly.core.config import (
    FeatureFlags,
    FireflyConfig,
    GuardrailsConfig,
    LLMConfig,
    PathConfig,
    VoiceConfig,
    load_config,
    settings,
)
from firefly.core.config import (
    FireflyConfig as Settings,
)

__all__ = [
    "settings",
    "Settings",
    "FireflyConfig",
    "load_config",
    "LLMConfig",
    "VoiceConfig",
    "GuardrailsConfig",
    "FeatureFlags",
    "PathConfig",
]
