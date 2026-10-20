"""Tamper-evident audit log backed by a cryptographically verifiable SHA-256 hash chain (Feature 95)."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from firefly.core.config import settings
from firefly.memory.redactor import SecretRedactor

GENESIS_HASH = "0" * 64


@dataclass
class AuditChainEntry:
    """An individual verifiable block in the audit trail hash chain."""

    index: int
    timestamp: float
    action: str
    command: str
    status: str
    provenance: Dict[str, Any]
    prev_hash: str
    hash: str

    def compute_hash(self) -> str:
        """Deterministically computes the SHA-256 hash of this entry's contents."""
        payload = {
            "index": self.index,
            "timestamp": self.timestamp,
            "action": self.action,
            "command": self.command,
            "status": self.status,
            "provenance": self.provenance,
            "prev_hash": self.prev_hash,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AuditChain:
    """Tamper-evident append-only ledger using cryptographic hash chaining."""

    def __init__(self, log_path: Optional[Path] = None) -> None:
        self.log_path = log_path or (settings.paths.data_dir / "audit" / "chain.jsonl")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._last_entry: Optional[AuditChainEntry] = self._read_tail()

    def _read_tail(self) -> Optional[AuditChainEntry]:
        """Reads the last entry in the chain log to determine the tip hash and index."""
        if not self.log_path.exists() or self.log_path.stat().st_size == 0:
            return None
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
                if not lines:
                    return None
                data = json.loads(lines[-1])
                return AuditChainEntry(**data)
        except Exception:
            return None

    def record(
        self,
        action: str,
        command: str,
        status: str,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> AuditChainEntry:
        """Appends a new audited action into the tamper-evident hash chain."""
        # Non-negotiable: secret redaction before persisting to audit log
        clean_command = SecretRedactor.redact(command)

        if self._last_entry is None:
            index = 0
            prev_hash = GENESIS_HASH
        else:
            index = self._last_entry.index + 1
            prev_hash = self._last_entry.hash

        entry = AuditChainEntry(
            index=index,
            timestamp=time.time(),
            action=action,
            command=clean_command,
            status=status,
            provenance=provenance or {},
            prev_hash=prev_hash,
            hash="",  # placeholder before computation
        )
        entry.hash = entry.compute_hash()

        # Atomic append to log file
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

        self._last_entry = entry
        return entry

    def verify(self) -> Tuple[bool, Optional[int], str]:
        """Validates the cryptographic integrity of the entire chain from genesis.

        Returns (valid: bool, bad_index: Optional[int], reason: str).
        """
        if not self.log_path.exists() or self.log_path.stat().st_size == 0:
            return True, None, "Audit chain is empty (valid)."

        expected_prev = GENESIS_HASH
        count = 0

        with open(self.log_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entry = AuditChainEntry(**data)
                except Exception as exc:
                    return (
                        False,
                        line_no,
                        f"Corrupted or invalid JSON at line {line_no}: {exc}",
                    )

                if entry.index != count:
                    return (
                        False,
                        count,
                        f"Sequence break: expected index {count}, found {entry.index}.",
                    )

                if entry.prev_hash != expected_prev:
                    return (
                        False,
                        count,
                        f"Hash chain broken at index {count}: prev_hash does not match prior block hash.",
                    )

                recalculated = entry.compute_hash()
                if entry.hash != recalculated:
                    return (
                        False,
                        count,
                        f"Tampering detected at entry {count}: block content modified (hash mismatch).",
                    )

                expected_prev = entry.hash
                count += 1

        return True, None, f"Audit chain verified successfully ({count} blocks intact)."

    def get_entries(self, limit: int = 50) -> List[AuditChainEntry]:
        """Returns the most recent entries in the audit trail."""
        if not self.log_path.exists():
            return []

        entries: List[AuditChainEntry] = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entries.append(AuditChainEntry(**data))
                except Exception:
                    continue

        return entries[-limit:]


# Global default audit chain
default_audit_chain = AuditChain()
