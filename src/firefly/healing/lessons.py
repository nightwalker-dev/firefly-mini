"""Lessons Learned store: records and matches proven self-healing fixes."""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Lesson:
    """A verified remediation lesson learned from past operations."""

    id: str
    error_pattern: str
    original_command: str
    successful_fix: str
    success_count: int = 1
    created_at: float = 0.0
    last_used_at: float = 0.0


class LessonsStore:
    """Persistent storage for successful error corrections with secret redaction."""

    def __init__(self, store_path: Optional[Path] = None) -> None:
        self.store_path = store_path or (Path.home() / ".config" / "firefly" / "lessons.json")
        self._lessons: Dict[str, Lesson] = {}
        self._load()

    def _sanitize(self, text: str) -> str:
        """Redacts sensitive credentials, passwords, and tokens before persistence."""
        # Redact passwords, tokens, API keys
        sanitized = re.sub(
            r"(password|token|secret|key)=['\"][^'\"]+['\"]",
            r"\1=[REDACTED]",
            text,
            flags=re.IGNORECASE,
        )
        sanitized = re.sub(
            r"(ghp_[a-zA-Z0-9]{36}|xox[baprs]-[a-zA-Z0-9]+)", "[REDACTED_TOKEN]", sanitized
        )
        return sanitized

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        try:
            raw = self.store_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            for item in data.get("lessons", []):
                les = Lesson(**item)
                self._lessons[les.id] = les
        except Exception:
            pass

    def _save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"lessons": [asdict(les) for les in self._lessons.values()]}
        self.store_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def record_success(self, error_pattern: str, original_command: str, fix_command: str) -> Lesson:
        """Stores or increments a successful fix remediation."""
        clean_err = self._sanitize(error_pattern.strip())
        clean_orig = self._sanitize(original_command.strip())
        clean_fix = self._sanitize(fix_command.strip())

        key = f"{clean_orig}::{clean_err}"
        now = time.time()

        if key in self._lessons:
            lesson = self._lessons[key]
            lesson.successful_fix = clean_fix
            lesson.success_count += 1
            lesson.last_used_at = now
        else:
            lesson = Lesson(
                id=f"lesson_{len(self._lessons) + 1}",
                error_pattern=clean_err,
                original_command=clean_orig,
                successful_fix=clean_fix,
                success_count=1,
                created_at=now,
                last_used_at=now,
            )
            self._lessons[key] = lesson

        self._save()
        return lesson

    def find_lesson(self, error_text: str, command: str) -> Optional[Lesson]:
        """Finds matching historical lesson for an error/command combination."""
        clean_err = self._sanitize(error_text.strip())
        clean_cmd = self._sanitize(command.strip())

        # Exact match
        key = f"{clean_cmd}::{clean_err}"
        if key in self._lessons:
            lesson = self._lessons[key]
            lesson.last_used_at = time.time()
            self._save()
            return lesson

        # Substring / token-overlap matching
        for lesson in self._lessons.values():
            cmd_words = set(clean_cmd.split())
            lesson_words = set(lesson.original_command.split())
            words_overlap = len(cmd_words & lesson_words) / max(len(cmd_words), 1)

            cmd_match = (
                lesson.original_command == clean_cmd
                or clean_cmd in lesson.original_command
                or lesson.original_command in clean_cmd
                or words_overlap >= 0.6
            )
            err_match = lesson.error_pattern in clean_err or clean_err in lesson.error_pattern
            if cmd_match and err_match:
                lesson.last_used_at = time.time()
                self._save()
                return lesson

        return None

    def list_lessons(self) -> List[Lesson]:
        """Returns all recorded lessons."""
        return list(self._lessons.values())

    def clear(self) -> None:
        """Clears all stored lessons."""
        self._lessons.clear()
        if self.store_path.exists():
            self.store_path.unlink()
