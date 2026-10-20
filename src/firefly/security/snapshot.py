"""Pre-operation filesystem snapshots with btrfs, timeshift, or rsync rollback (Feature 100)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from firefly.core.config import settings


@dataclass
class SnapshotInfo:
    """Metadata describing a saved pre-operation restore point."""

    snapshot_id: str
    backend: str  # "btrfs", "timeshift", "rsync"
    timestamp: float
    target_paths: List[str]
    backup_path: Optional[str]
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SnapshotManager:
    """Manages pre-operation system and file snapshots before bulk modifications."""

    _BULK_PATTERN = re.compile(
        r"\b(?:rm\s+-[a-zA-Z]*r[a-zA-Z]*|sed\s+-i|truncate|apt-get\s+(?:remove|purge)|"
        r"dnf\s+remove|pacman\s+-R|rsync\s+--delete|mv\s+.*\*)\b"
    )

    def __init__(self, snapshot_root: Optional[Path] = None) -> None:
        self.snapshot_root = snapshot_root or (settings.paths.data_dir / "snapshots")
        self.snapshot_root.mkdir(parents=True, exist_ok=True)
        self._meta_file = self.snapshot_root / "snapshots.jsonl"
        self._backend = self._detect_backend()

    def _detect_backend(self) -> str:
        """Determines the best available snapshot technology."""
        if shutil.which("btrfs"):
            # Check if root or home is btrfs
            try:
                res = subprocess.run(
                    ["btrfs", "subvolume", "show", str(Path.home())],
                    capture_output=True,
                    timeout=2,
                )
                if res.returncode == 0:
                    return "btrfs"
            except Exception:
                pass
        if shutil.which("timeshift"):
            return "timeshift"
        return "rsync"

    @property
    def backend(self) -> str:
        return self._backend

    def is_bulk_operation(self, command: str) -> bool:
        """Checks if a command is a bulk or recursive state-altering operation."""
        return bool(self._BULK_PATTERN.search(command))

    def create_snapshot(
        self, target_paths: List[str | Path], reason: str = "pre_bulk_op"
    ) -> SnapshotInfo:
        """Creates a restore point prior to executing a risky or bulk filesystem action."""
        snap_id = f"snap_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        now = time.time()
        targets_str = [str(Path(p).resolve()) for p in target_paths]

        backup_loc: Optional[str] = None

        if self._backend == "btrfs":
            try:
                # btrfs subvolume snapshot
                target_dir = Path.home()
                snap_dest = self.snapshot_root / snap_id
                subprocess.run(
                    ["btrfs", "subvolume", "snapshot", "-r", str(target_dir), str(snap_dest)],
                    check=True,
                    capture_output=True,
                    timeout=10,
                )
                backup_loc = str(snap_dest)
            except Exception:
                # Fall back to rsync
                pass

        if self._backend == "timeshift" and not backup_loc:
            try:
                subprocess.run(
                    [
                        "timeshift",
                        "--create",
                        "--comments",
                        f"Firefly pre-op: {snap_id}",
                        "--tags",
                        "O",
                    ],
                    check=True,
                    capture_output=True,
                    timeout=60,
                )
                backup_loc = f"timeshift://{snap_id}"
            except Exception:
                pass

        # Fallback rsync backup to snapshot_root / snap_id
        if not backup_loc:
            dest_dir = self.snapshot_root / snap_id
            dest_dir.mkdir(parents=True, exist_ok=True)
            for t in targets_str:
                src_path = Path(t)
                if src_path.is_file():
                    shutil.copy2(src_path, dest_dir / src_path.name)
                elif src_path.is_dir():
                    shutil.copytree(src_path, dest_dir / src_path.name, dirs_exist_ok=True)
            backup_loc = str(dest_dir)

        info = SnapshotInfo(
            snapshot_id=snap_id,
            backend=self._backend,
            timestamp=now,
            target_paths=targets_str,
            backup_path=backup_loc,
            reason=reason,
        )

        with open(self._meta_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(info.to_dict()) + "\n")

        return info

    def list_snapshots(self) -> List[SnapshotInfo]:
        """Lists all recorded snapshots."""
        if not self._meta_file.exists():
            return []
        items: List[SnapshotInfo] = []
        with open(self._meta_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        items.append(SnapshotInfo(**json.loads(line.strip())))
                    except Exception:
                        continue
        return items

    def rollback(self, snapshot_id: str) -> bool:
        """Restores filesystem state from a specific snapshot ID."""
        matches = [s for s in self.list_snapshots() if s.snapshot_id == snapshot_id]
        if not matches:
            return False
        info = matches[-1]
        if not info.backup_path or not Path(info.backup_path).exists():
            return False

        backup_p = Path(info.backup_path)
        for target_str in info.target_paths:
            target_p = Path(target_str)
            src_in_backup = backup_p / target_p.name
            if src_in_backup.is_file():
                shutil.copy2(src_in_backup, target_p)
            elif src_in_backup.is_dir():
                shutil.copytree(src_in_backup, target_p, dirs_exist_ok=True)
        return True


# Global default snapshot manager
default_snapshot_manager = SnapshotManager()
