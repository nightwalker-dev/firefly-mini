"""Memory snapshots with versioning/rollback and cross-session task resume."""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from firefly.core.config import settings
from firefly.memory.store import MemoryLayer, MemoryStore


@dataclass
class MemorySnapshot:
    """Metadata for a versioned memory snapshot backup."""

    snapshot_id: str
    label: str
    created_at: float
    file_path: Path
    item_count: int


@dataclass
class SuspendedTask:
    """State of an in-flight or suspended task for cross-session resumption."""

    task_id: str
    description: str
    current_step: int
    plan_steps: List[str]
    context_data: Dict[str, Any] = field(default_factory=dict)
    suspended_at: float = field(default_factory=time.time)
    status: str = "suspended"


class MemorySnapshotManager:
    """Creates, lists, and restores versioned point-in-time snapshots of the memory store."""

    def __init__(self, store: MemoryStore, snapshot_dir: Optional[Path] = None) -> None:
        self.store = store
        self.snapshot_dir = snapshot_dir or (settings.data_dir / "snapshots")
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

    def create_snapshot(self, label: str = "manual") -> MemorySnapshot:
        """Captures a frozen backup of the memory database."""
        now = time.time()
        snap_id = f"snap_{int(now)}_{label}"
        dest = self.snapshot_dir / f"{snap_id}.db"

        # Copy SQLite DB
        shutil.copy2(self.store.db_path, dest)
        items = self.store.list_memories(limit=5000)

        meta_file = self.snapshot_dir / f"{snap_id}.json"
        meta = {
            "snapshot_id": snap_id,
            "label": label,
            "created_at": now,
            "item_count": len(items),
        }
        meta_file.write_text(json.dumps(meta, indent=2))

        return MemorySnapshot(
            snapshot_id=snap_id,
            label=label,
            created_at=now,
            file_path=dest,
            item_count=len(items),
        )

    def list_snapshots(self) -> List[MemorySnapshot]:
        """Lists all available snapshots sorted by creation time descending."""
        snapshots: List[MemorySnapshot] = []
        for meta_file in sorted(self.snapshot_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(meta_file.read_text())
                db_path = meta_file.with_suffix(".db")
                if db_path.exists():
                    snapshots.append(
                        MemorySnapshot(
                            snapshot_id=data["snapshot_id"],
                            label=data.get("label", "auto"),
                            created_at=data["created_at"],
                            file_path=db_path,
                            item_count=data.get("item_count", 0),
                        )
                    )
            except Exception:
                continue
        return snapshots

    def restore_snapshot(self, snapshot_id: str) -> bool:
        """Restores memory database from the given snapshot ID."""
        src_db = self.snapshot_dir / f"{snapshot_id}.db"
        if not src_db.exists():
            return False

        # Safely replace active DB with snapshot
        shutil.copy2(src_db, self.store.db_path)
        # Re-initialize DB connections
        self.store._init_db()
        return True


class TaskResumeManager:
    """Enables seamless cross-session task persistence and continuation ('continue where we stopped')."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def suspend_task(
        self,
        task_id: str,
        description: str,
        plan_steps: List[str],
        current_step: int = 0,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> SuspendedTask:
        """Saves a paused task checkpoint into episodic memory."""
        task = SuspendedTask(
            task_id=task_id,
            description=description,
            current_step=current_step,
            plan_steps=plan_steps,
            context_data=context_data or {},
            suspended_at=time.time(),
            status="suspended",
        )
        self.store.add_memory(
            layer=MemoryLayer.EPISODIC,
            key=f"task:suspended:{task_id}",
            content=f"Suspended task: {description} (step {current_step}/{len(plan_steps)})",
            importance=0.9,
            pinned=True,
            metadata=asdict(task),
        )
        # Also maintain a pointer to latest suspended task
        self.store.add_memory(
            layer=MemoryLayer.SHORT_TERM,
            key="task:latest_suspended",
            content=task_id,
            importance=1.0,
            pinned=False,
        )
        return task

    def get_latest_suspended_task(self) -> Optional[SuspendedTask]:
        """Finds the most recently suspended task waiting to be resumed."""
        pointer = self.store.get_by_key("task:latest_suspended", layer=MemoryLayer.SHORT_TERM)
        task_id = pointer.content if pointer else None

        if task_id:
            mem = self.store.get_by_key(f"task:suspended:{task_id}", layer=MemoryLayer.EPISODIC)
            if mem and mem.metadata:
                return SuspendedTask(**mem.metadata)

        # Fallback: scan episodic memories for any suspended tasks
        mems = self.store.list_memories(layer=MemoryLayer.EPISODIC, limit=50)
        for m in mems:
            if m.key.startswith("task:suspended:") and m.metadata:
                return SuspendedTask(**m.metadata)
        return None

    def mark_completed(self, task_id: str) -> None:
        """Marks a suspended task as finished."""
        mem = self.store.get_by_key(f"task:suspended:{task_id}", layer=MemoryLayer.EPISODIC)
        if mem:
            self.store.delete_memory(mem.id)
        pointer = self.store.get_by_key("task:latest_suspended", layer=MemoryLayer.SHORT_TERM)
        if pointer and pointer.content == task_id:
            self.store.delete_memory(pointer.id)
