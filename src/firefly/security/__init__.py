"""Firefly Security Subsystem (Phase 6: Safety Hardening).

Features:
- Feature 91: Policy-as-code YAML engine with startup validation.
- Feature 92: Per-tool permission scopes and least-privilege defaults.
- Feature 93: Path allowlist/denylist with traversal defenses.
- Feature 94: Network egress controls for curl/wget/ssh.
- Feature 95: Tamper-evident SHA-256 hash chain audit trail.
- Feature 96: Command provenance tracking prompt/thought/trigger.
- Feature 97: Prompt-injection defense for external screen and web data.
- Feature 98: Multi-bucket sliding-window rate limiters.
- Feature 99: Sandboxed execution runner with bubblewrap and container fallback.
- Feature 100: Pre-operation snapshots with btrfs, timeshift, and rsync rollback.
- Feature 103: Safe-mode controller for strictly read-only inspection.
- Feature 104: Session lifetime and inactivity auto-lock guard.
- Feature 105: Clear "why blocked" explanations with safer alternatives.
"""

from __future__ import annotations

from firefly.security.audit import AuditChain, AuditChainEntry, default_audit_chain
from firefly.security.explainer import (
    BlockExplainer,
    BlockExplanation,
    default_block_explainer,
)
from firefly.security.injection import (
    InjectionAssessment,
    PromptInjectionGuard,
    default_injection_guard,
)
from firefly.security.policy import (
    NetworkPolicy,
    PathPolicy,
    PolicyEngine,
    PolicyRule,
    SecurityPolicy,
    default_policy_engine,
)
from firefly.security.provenance import (
    CommandProvenance,
    ProvenanceTracker,
    default_provenance,
)
from firefly.security.rate_limiter import (
    RateLimitExceeded,
    SecurityRateLimiter,
    default_rate_limiter,
)
from firefly.security.safe_mode import (
    SafeModeController,
    SafeModeViolation,
    default_safe_mode,
)
from firefly.security.sandbox import (
    SandboxOptions,
    SandboxRunner,
    default_sandbox_runner,
)
from firefly.security.scopes import (
    DEFAULT_SCOPES,
    PermissionScopeError,
    Scope,
    ScopeManager,
    default_scope_manager,
)
from firefly.security.session import (
    SessionGuard,
    SessionLockedError,
    default_session_guard,
)
from firefly.security.snapshot import (
    SnapshotInfo,
    SnapshotManager,
    default_snapshot_manager,
)

__all__ = [
    "Scope",
    "ScopeManager",
    "PermissionScopeError",
    "DEFAULT_SCOPES",
    "default_scope_manager",
    "PolicyRule",
    "PathPolicy",
    "NetworkPolicy",
    "SecurityPolicy",
    "PolicyEngine",
    "default_policy_engine",
    "AuditChain",
    "AuditChainEntry",
    "default_audit_chain",
    "CommandProvenance",
    "ProvenanceTracker",
    "default_provenance",
    "InjectionAssessment",
    "PromptInjectionGuard",
    "default_injection_guard",
    "SecurityRateLimiter",
    "RateLimitExceeded",
    "default_rate_limiter",
    "SandboxOptions",
    "SandboxRunner",
    "default_sandbox_runner",
    "SnapshotInfo",
    "SnapshotManager",
    "default_snapshot_manager",
    "SafeModeController",
    "SafeModeViolation",
    "default_safe_mode",
    "SessionGuard",
    "SessionLockedError",
    "default_session_guard",
    "BlockExplanation",
    "BlockExplainer",
    "default_block_explainer",
]
