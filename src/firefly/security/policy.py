"""Policy-as-code YAML engine, path containment, and network egress controls.

Features:
- Feature 91: Policy-as-code file (YAML) for allow/deny/confirm rules, validated at startup.
- Feature 93: Path allowlist/denylist for file operations with canonicalization.
- Feature 94: Network egress rules for commands that use curl/wget/etc.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError

from firefly.core.guardrails import Action, Finding, Risk

# Optional PyYAML with JSON/manual fallback for offline environments
try:
    import yaml

    HAS_YAML = True
except ImportError:
    yaml = None  # type: ignore[assignment]
    HAS_YAML = False


class PolicyRule(BaseModel):
    """Declarative safety rule defined in the policy file."""

    id: str
    match: str
    is_regex: bool = False
    action: Action = Action.CONFIRM
    risk: Risk = Risk.MEDIUM
    reason: str
    required_scope: Optional[str] = None


class PathPolicy(BaseModel):
    """Filesystem boundaries and path containment rules."""

    # Default strictly forbidden system & credential locations
    denied_paths: List[str] = Field(
        default_factory=lambda: [
            "/etc/shadow",
            "/etc/passwd",
            "/etc/sudoers",
            "/etc/sudoers.d",
            "/boot",
            "/dev",
            "/proc/sysrq-trigger",
            "/proc/kcore",
            "~/.ssh",
            "~/.gnupg",
            "~/.aws",
            "~/.config/firefly/keys",
        ]
    )
    # If non-empty, file modifications must be strictly confined to these roots
    allowed_roots: List[str] = Field(default_factory=list)


class NetworkPolicy(BaseModel):
    """Egress traffic rules for network-capable binaries."""

    mode: str = "allow_all"  # "allow_all", "restricted", "deny_all"
    allowed_domains: List[str] = Field(
        default_factory=lambda: [
            "localhost",
            "127.0.0.1",
            "::1",
            "github.com",
            "api.github.com",
            "raw.githubusercontent.com",
            "pypi.org",
            "files.pythonhosted.org",
            "ollama.ai",
        ]
    )
    denied_domains: List[str] = Field(
        default_factory=lambda: [
            "pastebin.com",
            "ngrok.io",
            "webhook.site",
            "canarytokens.org",
        ]
    )
    denied_ips: List[str] = Field(default_factory=list)


class SecurityPolicy(BaseModel):
    """Root policy-as-code schema."""

    version: str = "1.0"
    name: str = "Firefly Standard Defense Policy"
    rules: List[PolicyRule] = Field(default_factory=list)
    paths: PathPolicy = Field(default_factory=PathPolicy)
    network: NetworkPolicy = Field(default_factory=NetworkPolicy)


class PolicyEngine:
    """Evaluates declarative policies against shell commands and system operations."""

    def __init__(self, policy: Optional[SecurityPolicy] = None) -> None:
        self.policy = policy or SecurityPolicy()
        self._compiled_regexes: Dict[str, re.Pattern[str]] = {}
        self._compile_rules()

    def _compile_rules(self) -> None:
        """Pre-compiles regex patterns for performance."""
        self._compiled_regexes.clear()
        for rule in self.policy.rules:
            if rule.is_regex:
                try:
                    self._compiled_regexes[rule.id] = re.compile(rule.match, re.IGNORECASE)
                except re.error as err:
                    raise ValueError(
                        f"Invalid regex in policy rule '{rule.id}': {rule.match} ({err})"
                    ) from err

    @classmethod
    def load_file(cls, path: str | Path) -> PolicyEngine:
        """Loads and validates policy file at startup. Supports YAML and JSON."""
        target = Path(path).expanduser().resolve()
        if not target.exists():
            raise FileNotFoundError(f"Policy file not found: {target}")

        content = target.read_text(encoding="utf-8")
        return cls.from_string(content, filename=str(target))

    @classmethod
    def from_string(cls, content: str, filename: str = "<string>") -> PolicyEngine:
        """Parses policy YAML/JSON text into validated SecurityPolicy."""
        data: Dict[str, Any]
        if HAS_YAML and yaml is not None:
            try:
                raw = yaml.safe_load(content)
                data = raw if isinstance(raw, dict) else {}
            except yaml.YAMLError as exc:
                raise ValueError(f"YAML Syntax Error in policy '{filename}': {exc}") from exc
        else:
            # Fallback to JSON or basic key-value parser
            import json

            try:
                data = json.loads(content)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Failed to parse policy (PyYAML not installed and JSON parse failed): {exc}"
                ) from exc

        try:
            policy = SecurityPolicy.model_validate(data)
            return cls(policy=policy)
        except ValidationError as val_err:
            raise ValueError(f"Policy validation failed in '{filename}': {val_err}") from val_err

    # ------------------------------------------------ Feature 91: Command Rules
    def evaluate_command(self, command: str, cwd: Optional[str] = None) -> Optional[Finding]:
        """Checks command against declarative rules."""
        cmd_clean = command.strip()
        for rule in self.policy.rules:
            matched = False
            if rule.is_regex:
                regex = self._compiled_regexes.get(rule.id)
                if regex and regex.search(cmd_clean):
                    matched = True
            else:
                # Prefix or exact match
                if cmd_clean.startswith(rule.match) or rule.match in cmd_clean:
                    matched = True

            if matched:
                return Finding(
                    rule=f"policy:{rule.id}",
                    risk=rule.risk,
                    action=rule.action,
                    reason=rule.reason,
                    segment=cmd_clean,
                )
        return None

    # ------------------------------------------------ Feature 93: Path Controls
    def check_path(
        self,
        path: str | Path,
        operation: str = "write",
        cwd: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Validates filesystem path against allowlist and denylist.

        Returns (allowed: bool, reason: str).
        """
        # Null bytes check
        path_str = str(path)
        if "\x00" in path_str:
            return False, "Null byte injection detected in path."

        base_cwd = Path(cwd).resolve() if cwd else Path.cwd()
        raw_path = Path(path_str).expanduser()

        if not raw_path.is_absolute():
            resolved = (base_cwd / raw_path).resolve()
        else:
            resolved = raw_path.resolve()

        resolved_str = str(resolved)

        # 1. Check denylist
        for denied in self.policy.paths.denied_paths:
            denied_resolved = str(Path(denied).expanduser().resolve())
            if resolved_str == denied_resolved or resolved_str.startswith(denied_resolved + os.sep):
                return False, f"Path '{resolved_str}' matches forbidden path rule: '{denied}'"

        # 2. Check allowlist if configured
        if self.policy.paths.allowed_roots:
            in_allowed_root = False
            for root in self.policy.paths.allowed_roots:
                root_resolved = str(Path(root).expanduser().resolve())
                if resolved_str == root_resolved or resolved_str.startswith(root_resolved + os.sep):
                    in_allowed_root = True
                    break
            if not in_allowed_root:
                allowed_str = ", ".join(self.policy.paths.allowed_roots)
                return False, f"Path '{resolved_str}' is outside allowed roots: [{allowed_str}]"

        return True, "Path access permitted by security policy."

    # ------------------------------------------------ Feature 94: Network Egress
    _NET_TOOLS = ("curl", "wget", "nc", "ncat", "ssh", "scp", "rsync", "socat")

    def check_network_egress(self, command: str) -> Tuple[bool, str, Optional[str]]:
        """Extracts destination host/domain from network commands and enforces egress rules.

        Returns (allowed: bool, reason: str, host: Optional[str]).
        """
        mode = self.policy.network.mode.lower()
        if mode == "deny_all":
            # Completely offline / air-gapped mode
            for tool in self._NET_TOOLS:
                if re.search(rf"\b{tool}\b", command):
                    return False, f"Network egress completely blocked in '{mode}' mode.", None

        # Check for URL or host in command
        url_match = re.search(r"https?://([a-zA-Z0-9\.\-_]+)(?::\d+)?", command)
        host: Optional[str] = None
        if url_match:
            host = url_match.group(1).lower()
        else:
            # Check host arguments for curl/wget/ssh
            host_match = re.search(
                r"\b(?:curl|wget|ssh|scp|nc|ncat)\b[^\n|;&]*\s+([a-zA-Z0-9\.\-]+)(?:\s|$)", command
            )
            if host_match:
                candidate = host_match.group(1)
                if not candidate.startswith("-") and "." in candidate:
                    host = candidate.lower()

        if not host:
            # No network host identified; if tool is present in deny_all, block
            if mode == "deny_all" and any(re.search(rf"\b{t}\b", command) for t in self._NET_TOOLS):
                return False, "Unspecified network egress blocked in deny_all mode.", None
            return True, "No restricted network targets detected.", None

        # Denied domains
        for denied in self.policy.network.denied_domains:
            if host == denied.lower() or host.endswith("." + denied.lower()):
                return False, f"Destination host '{host}' is in network denylist ({denied}).", host

        # Denied IPs
        for denied_ip in self.policy.network.denied_ips:
            if host == denied_ip:
                return False, f"Destination IP '{host}' is explicitly denied.", host

        # Restricted mode: must be in allowed_domains
        if mode == "restricted":
            allowed = False
            for allowed_domain in self.policy.network.allowed_domains:
                al = allowed_domain.lower()
                if host == al or host.endswith("." + al):
                    allowed = True
                    break
            if not allowed:
                return (
                    False,
                    f"Destination host '{host}' not found in egress allowlist (restricted mode).",
                    host,
                )

        return True, f"Network egress to '{host}' permitted.", host


# Default global policy engine
default_policy_engine = PolicyEngine()
