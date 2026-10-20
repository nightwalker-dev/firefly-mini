"""Three-layer adaptive memory store backed by SQLite, FTS5, and encryption at rest."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from firefly.core.config import settings
from firefly.memory.redactor import SecretRedactor

try:
    from cryptography.fernet import Fernet

    HAS_FERNET = True
except ImportError:
    Fernet = None  # type: ignore[assignment,misc]
    HAS_FERNET = False


class MemoryLayer(str, Enum):
    """The three conceptual tiers of Firefly Mini's memory architecture."""

    SHORT_TERM = "short_term"  # Ephemeral dialogue, turn scratchpad
    EPISODIC = "episodic"  # Past task executions and action history
    SEMANTIC = "semantic"  # Facts, configuration, preferences, habits


@dataclass
class MemoryItem:
    """A discrete unit of recorded knowledge."""

    id: str
    layer: MemoryLayer
    key: str
    content: str
    importance: float = 0.5
    created_at: float = field(default_factory=time.time)
    last_accessed_at: float = field(default_factory=time.time)
    access_count: int = 1
    pinned: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    superseded_by: Optional[str] = None


class MemoryStore:
    """Manages persistent SQLite memory storage with encryption and full-text search."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        key_path: Optional[Path] = None,
    ) -> None:
        settings.ensure_dirs()
        self.db_path = db_path or (settings.data_dir / "memory.db")
        self.key_path = key_path or settings.audit_key
        self._cipher = self._init_cipher()
        self._fts_conn: Optional[sqlite3.Connection] = None
        self._has_fts = False
        self._init_db()
        self._init_fts()

    def _init_cipher(self) -> Optional[Any]:
        if not HAS_FERNET or Fernet is None:
            return None
        if not self.key_path.exists():
            key = Fernet.generate_key()
            self.key_path.write_bytes(key)
            os.chmod(self.key_path, 0o600)
        else:
            key = self.key_path.read_bytes().strip()
        return Fernet(key)

    def _encrypt(self, text: str) -> str:
        if self._cipher:
            return self._cipher.encrypt(text.encode("utf-8")).decode("ascii")
        # Salted base64 fallback obfuscation
        chk = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
        b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        return f"PLAIN:{chk}:{b64}"

    def _decrypt(self, payload: str) -> str:
        if payload.startswith("PLAIN:"):
            _, _, b64 = payload.split(":", 2)
            return base64.b64decode(b64.encode("ascii")).decode("utf-8", errors="replace")
        if self._cipher:
            try:
                return self._cipher.decrypt(payload.encode("ascii")).decode(
                    "utf-8", errors="replace"
                )
            except Exception:
                return "<DECRYPT_FAILED>"
        return payload

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    layer TEXT NOT NULL,
                    key TEXT NOT NULL,
                    encrypted_content TEXT NOT NULL,
                    importance REAL NOT NULL,
                    created_at REAL NOT NULL,
                    last_accessed_at REAL NOT NULL,
                    access_count INTEGER NOT NULL,
                    pinned INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL,
                    superseded_by TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_layer_key ON memories (layer, key)")
            conn.commit()

    def _init_fts(self) -> None:
        try:
            self._fts_conn = sqlite3.connect(":memory:")
            self._fts_conn.execute(
                "CREATE VIRTUAL TABLE memories_fts USING fts5(id UNINDEXED, key, content)"
            )
            self._has_fts = True
            items = self.list_memories(limit=10000)
            for it in items:
                self._fts_conn.execute(
                    "INSERT INTO memories_fts (id, key, content) VALUES (?, ?, ?)",
                    (it.id, it.key, it.content),
                )
            self._fts_conn.commit()
        except Exception:
            self._has_fts = False
            self._fts_conn = None

    def add_memory(
        self,
        layer: MemoryLayer,
        key: str,
        content: str,
        importance: float = 0.5,
        pinned: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        memory_id: Optional[str] = None,
    ) -> MemoryItem:
        """Stores a new memory, running secret redaction and encryption at rest."""
        clean_content = SecretRedactor.redact(content)
        clean_key = SecretRedactor.redact(key)
        now = time.time()
        m_id = memory_id or f"mem_{int(now * 1000)}_{os.urandom(3).hex()}"
        meta = metadata or {}

        item = MemoryItem(
            id=m_id,
            layer=layer,
            key=clean_key,
            content=clean_content,
            importance=max(0.0, min(1.0, importance)),
            created_at=now,
            last_accessed_at=now,
            access_count=1,
            pinned=pinned,
            metadata=meta,
        )

        enc_content = self._encrypt(clean_content)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO memories (
                    id, layer, key, encrypted_content, importance,
                    created_at, last_accessed_at, access_count, pinned,
                    metadata_json, superseded_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.layer.value,
                    item.key,
                    enc_content,
                    item.importance,
                    item.created_at,
                    item.last_accessed_at,
                    item.access_count,
                    1 if item.pinned else 0,
                    json.dumps(item.metadata),
                    item.superseded_by,
                ),
            )
            conn.commit()

        if self._has_fts and self._fts_conn:
            try:
                self._fts_conn.execute(
                    "INSERT OR REPLACE INTO memories_fts (id, key, content) VALUES (?, ?, ?)",
                    (item.id, item.key, clean_content),
                )
                self._fts_conn.commit()
            except Exception:
                pass

        return item

    def get_memory(self, memory_id: str) -> Optional[MemoryItem]:
        """Retrieves and decrypts a specific memory by its ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT id, layer, key, encrypted_content, importance,
                       created_at, last_accessed_at, access_count, pinned,
                       metadata_json, superseded_by
                FROM memories WHERE id = ?
                """,
                (memory_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            # Update access statistics
            conn.execute(
                "UPDATE memories SET access_count = access_count + 1, last_accessed_at = ? WHERE id = ?",
                (time.time(), memory_id),
            )
            conn.commit()

        return self._row_to_item(row)

    def get_by_key(
        self,
        key: str,
        layer: Optional[MemoryLayer] = None,
    ) -> Optional[MemoryItem]:
        """Finds the most recently active active memory matching key and optional layer."""
        query = "SELECT id, layer, key, encrypted_content, importance, created_at, last_accessed_at, access_count, pinned, metadata_json, superseded_by FROM memories WHERE key = ? AND superseded_by IS NULL"
        params: list[Any] = [key]
        if layer:
            query += " AND layer = ?"
            params.append(layer.value)
        query += " ORDER BY last_accessed_at DESC LIMIT 1"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE memories SET access_count = access_count + 1, last_accessed_at = ? WHERE id = ?",
                (time.time(), row[0]),
            )
            conn.commit()

        return self._row_to_item(row)

    def search(
        self,
        query: str,
        layer: Optional[MemoryLayer] = None,
        limit: int = 10,
    ) -> List[MemoryItem]:
        """Full-text or token search across memories."""
        results: List[MemoryItem] = []
        clean_q = query.strip()
        if not clean_q:
            return results

        if self._has_fts and self._fts_conn:
            try:
                cursor = self._fts_conn.execute(
                    "SELECT id FROM memories_fts WHERE memories_fts MATCH ?",
                    (clean_q,),
                )
                for (m_id,) in cursor.fetchall():
                    mem = self.get_memory(m_id)
                    if mem and mem.superseded_by is None:
                        if not layer or mem.layer == layer:
                            results.append(mem)
                            if len(results) >= limit:
                                return results
                if results:
                    return results
            except Exception:
                pass

        # Fallback decrypted search
        all_items = self.list_memories(layer=layer, limit=500)
        q_lower = clean_q.lower()
        for it in all_items:
            if q_lower in it.key.lower() or q_lower in it.content.lower():
                results.append(it)
                if len(results) >= limit:
                    break
        return results

    def list_memories(
        self,
        layer: Optional[MemoryLayer] = None,
        include_superseded: bool = False,
        limit: int = 50,
    ) -> List[MemoryItem]:
        """Lists memories ordered by last access time."""
        sql = "SELECT id, layer, key, encrypted_content, importance, created_at, last_accessed_at, access_count, pinned, metadata_json, superseded_by FROM memories WHERE 1=1"
        params: list[Any] = []
        if not include_superseded:
            sql += " AND superseded_by IS NULL"
        if layer:
            sql += " AND layer = ?"
            params.append(layer.value)
        sql += " ORDER BY last_accessed_at DESC LIMIT ?"
        params.append(limit)

        results: List[MemoryItem] = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(sql, params)
            for row in cursor.fetchall():
                results.append(self._row_to_item(row))
        return results

    def update_memory(
        self,
        memory_id: str,
        new_content: str,
        importance: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Updates content and importance of an existing memory."""
        clean_content = SecretRedactor.redact(new_content)
        enc = self._encrypt(clean_content)
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            set_clauses = ["encrypted_content = ?", "last_accessed_at = ?"]
            params: list[Any] = [enc, now]
            if importance is not None:
                set_clauses.append("importance = ?")
                params.append(importance)
            if metadata is not None:
                set_clauses.append("metadata_json = ?")
                params.append(json.dumps(metadata))
            params.append(memory_id)
            conn.execute(
                f"UPDATE memories SET {', '.join(set_clauses)} WHERE id = ?",
                params,
            )
            conn.commit()
            changed = conn.total_changes > 0

        if self._has_fts and self._fts_conn:
            try:
                self._fts_conn.execute(
                    "UPDATE memories_fts SET content = ? WHERE id = ?",
                    (clean_content, memory_id),
                )
                self._fts_conn.commit()
            except Exception:
                pass
        return changed

    def delete_memory(self, memory_id: str) -> bool:
        """Deletes a memory record permanently."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
            changed = conn.total_changes > 0

        if self._has_fts and self._fts_conn:
            try:
                self._fts_conn.execute("DELETE FROM memories_fts WHERE id = ?", (memory_id,))
                self._fts_conn.commit()
            except Exception:
                pass
        return changed

    def wipe(
        self,
        layer: Optional[MemoryLayer] = None,
        unpinned_only: bool = True,
    ) -> int:
        """Purges memory entries according to scope."""
        sql = "DELETE FROM memories WHERE 1=1"
        params: list[Any] = []
        if unpinned_only:
            sql += " AND pinned = 0"
        if layer:
            sql += " AND layer = ?"
            params.append(layer.value)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(sql, params)
            deleted_count = cursor.rowcount
            conn.commit()
            conn.execute("VACUUM")

        if self._has_fts and self._fts_conn:
            try:
                self._fts_conn.execute("DELETE FROM memories_fts")
                self._fts_conn.commit()
            except Exception:
                pass

        return deleted_count

    def _row_to_item(self, row: Any) -> MemoryItem:
        dec_content = self._decrypt(row[3])
        meta = json.loads(row[9]) if row[9] else {}
        return MemoryItem(
            id=row[0],
            layer=MemoryLayer(row[1]),
            key=row[2],
            content=dec_content,
            importance=row[4],
            created_at=row[5],
            last_accessed_at=row[6],
            access_count=row[7],
            pinned=bool(row[8]),
            metadata=meta,
            superseded_by=row[10],
        )
