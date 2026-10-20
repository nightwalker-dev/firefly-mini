"""Block explanations and actionable safer alternative suggestions (Feature 105)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from firefly.core.guardrails import Action


@dataclass
class BlockExplanation:
    """Clear reason for guardrail block along with a safer actionable alternative."""

    command: str
    risk_level: str
    why_blocked: str
    safer_alternative: str
    cyber_cat_tip: str

    def format_text(self) -> str:
        """Returns human-readable text suitable for terminal output or logs."""
        lines = [
            "🚫 [FIREFLY DEFENSE: COMMAND BLOCKED]",
            f"Command: {self.command}",
            f"Risk Level: {self.risk_level}",
            f"Why Blocked: {self.why_blocked}",
            f"Safer Alternative: {self.safer_alternative}",
            f"🐾 Firefly Tip: {self.cyber_cat_tip}",
        ]
        return "\n".join(lines)


class BlockExplainer:
    """Generates intuitive justifications and safer command substitutions for blocked actions."""

    _PATTERNS = [
        (
            re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*\s+(?:/|/\*|~\b|~/\*)"),
            "Attempts recursive destruction of root or entire home directory.",
            "Target a specific isolated directory instead, e.g.: rm -rf /tmp/test-workspace",
            "Napping is better than wiping the operating system, master! (=^･ω･^=)",
        ),
        (
            re.compile(r"\bchmod\s+(?:-R\s+)?777\b"),
            "Opens world-writable permissions (777), allowing any local user/process to modify or inject code.",
            "Use least-privilege permissions: chmod 755 for directories, chmod 644 for files.",
            "Cats guard their territory with care—never leave every door wide open! 🐾",
        ),
        (
            re.compile(r"(?:curl|wget)\b[^\n|;&]*\|\s*(?:bash|sh)\b"),
            "Piping untrusted remote network scripts directly into a shell bypasses all code review and local inspection.",
            "Download and review the script first: curl -sLO <url> && less script.sh && bash script.sh",
            "Sniff before you sip! Always inspect what comes from the wild web.",
        ),
        (
            re.compile(r"\b(?:sudo\s+)?dd\s+if=[^\s]+\s+of=/dev/"),
            "Direct raw block device overwriting can destroy disk partition tables and unmounted filesystems.",
            "Test disk images with loop devices: losetup -fP disk.img",
            "Direct drive writes leave deep claw marks that cannot be undone!",
        ),
        (
            re.compile(r"\b(?:killall\s+-9|kill\s+-9\s+-1)\b"),
            "Unconditional SIGKILL (-9) prevents applications from saving state, closing sockets, or releasing locks.",
            "Send graceful termination signal first: kill -15 <pid> or systemctl stop <service>",
            "Give processes a gentle tap first before using claws! 🐾",
        ),
        (
            re.compile(r"\b(?:ufw\s+disable|iptables\s+-F)\b"),
            "Flushing firewall rules completely drops the host's perimeter defense.",
            "Add targeted rules instead: ufw allow <port>/tcp or inspect rules with ufw status numbered",
            "Don't turn off the cyber-fence, stay safe inside the castle!",
        ),
        (
            re.compile(r">\s*(?:/etc/|/boot/)"),
            "Direct shell redirection into protected system directories can corrupt critical configuration files.",
            "Write your file to /tmp/ or your user directory, then review and copy carefully.",
            "System configs are the foundation of our playground—tread lightly!",
        ),
    ]

    def explain(self, verdict: Any) -> BlockExplanation:
        """Constructs an explanation and safer alternative based on a guardrail Verdict."""
        cmd = verdict.subject
        risk_name = verdict.risk.name

        # Check matched specific patterns first
        for pat, why, alt, tip in self._PATTERNS:
            if pat.search(cmd):
                return BlockExplanation(
                    command=cmd,
                    risk_level=risk_name,
                    why_blocked=why,
                    safer_alternative=alt,
                    cyber_cat_tip=tip,
                )

        # Fallback explanation constructed from verdict findings
        reasons = [f.reason for f in verdict.findings if f.action == Action.BLOCK]
        if not reasons:
            reasons = [f.reason for f in verdict.findings]

        why = "; ".join(reasons) if reasons else "Violates baseline safety guardrail threshold."
        alt = "Review the command syntax and specify non-critical, scoped parameters."
        tip = "When in doubt, run with '--dry-run' or test inside an isolated container! 🐾"

        return BlockExplanation(
            command=cmd,
            risk_level=risk_name,
            why_blocked=why,
            safer_alternative=alt,
            cyber_cat_tip=tip,
        )


# Global default block explainer
default_block_explainer = BlockExplainer()
