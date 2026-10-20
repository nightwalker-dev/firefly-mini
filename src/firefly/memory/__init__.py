"""Adaptive multi-layer memory system for Firefly Mini."""

from __future__ import annotations

from firefly.memory.consent import ConsentManager
from firefly.memory.decay import MemoryDecayManager
from firefly.memory.ledger import ToolReliabilityLedger, ToolStats
from firefly.memory.preferences import (
    HabitLearner,
    PersonaContinuity,
    PersonaState,
    RoutineDetector,
    UserPreferencesManager,
)
from firefly.memory.project import ProjectContextManager, ProjectInfo
from firefly.memory.redactor import SecretRedactor
from firefly.memory.retrieval import ContextAwareRetriever, ContradictionHandler
from firefly.memory.snapshots import (
    MemorySnapshot,
    MemorySnapshotManager,
    SuspendedTask,
    TaskResumeManager,
)
from firefly.memory.store import MemoryItem, MemoryLayer, MemoryStore
from firefly.memory.summarizer import SessionSummarizer, SummaryBlock

__all__ = [
    "SecretRedactor",
    "MemoryLayer",
    "MemoryItem",
    "MemoryStore",
    "MemoryDecayManager",
    "PersonaState",
    "PersonaContinuity",
    "UserPreferencesManager",
    "HabitLearner",
    "RoutineDetector",
    "ProjectInfo",
    "ProjectContextManager",
    "ToolStats",
    "ToolReliabilityLedger",
    "SummaryBlock",
    "SessionSummarizer",
    "ContradictionHandler",
    "ContextAwareRetriever",
    "ConsentManager",
    "MemorySnapshot",
    "MemorySnapshotManager",
    "SuspendedTask",
    "TaskResumeManager",
]
