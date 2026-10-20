"""Per-project memory scoping and automatic repository context detection."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from firefly.memory.store import MemoryItem, MemoryLayer, MemoryStore


@dataclass
class ProjectInfo:
    """Discovered context for the current active project directory."""

    name: str
    root: Path
    project_type: str  # "python", "node", "rust", "go", "generic"
    has_git: bool


class ProjectContextManager:
    """Manages project-scoped memories and detects active workspace boundaries."""

    PROJECT_MARKERS: Dict[str, str] = {
        "pyproject.toml": "python",
        "requirements.txt": "python",
        "setup.py": "python",
        "package.json": "node",
        "Cargo.toml": "rust",
        "go.mod": "go",
        "Makefile": "generic",
    }

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    @classmethod
    def detect_project(cls, start_dir: Optional[Path | str] = None) -> ProjectInfo:
        """Ascends directory tree to locate project root and inspect environment."""
        cur = Path(start_dir or os.getcwd()).resolve()

        project_root: Optional[Path] = None
        project_type = "generic"
        has_git = False

        for candidate in [cur] + list(cur.parents):
            if (candidate / ".git").exists():
                has_git = True
                project_root = candidate
                break

            for marker, p_type in cls.PROJECT_MARKERS.items():
                if (candidate / marker).exists():
                    project_root = candidate
                    project_type = p_type
                    break
            if project_root:
                break

        final_root = project_root or cur
        if final_root and (final_root / ".git").exists():
            has_git = True

        for marker, p_type in cls.PROJECT_MARKERS.items():
            if (final_root / marker).exists():
                project_type = p_type
                break

        return ProjectInfo(
            name=final_root.name,
            root=final_root,
            project_type=project_type,
            has_git=has_git,
        )

    def set_project_memory(
        self,
        project_name: str,
        key: str,
        value: str,
        pinned: bool = False,
    ) -> MemoryItem:
        """Stores a scoped memory item associated with a specific project."""
        scoped_key = f"project:{project_name}:{key}"
        return self.store.add_memory(
            layer=MemoryLayer.SEMANTIC,
            key=scoped_key,
            content=value,
            importance=0.8,
            pinned=pinned,
            metadata={"project": project_name, "scoped_key": key},
        )

    def get_project_memory(self, project_name: str, key: str) -> Optional[str]:
        """Retrieves a scoped project memory value."""
        scoped_key = f"project:{project_name}:{key}"
        mem = self.store.get_by_key(scoped_key, layer=MemoryLayer.SEMANTIC)
        return mem.content if mem else None

    def list_project_memories(self, project_name: str) -> List[MemoryItem]:
        """Lists all memory entries associated with the specified project."""
        all_semantic = self.store.list_memories(layer=MemoryLayer.SEMANTIC, limit=500)
        prefix = f"project:{project_name}:"
        return [m for m in all_semantic if m.key.startswith(prefix)]
