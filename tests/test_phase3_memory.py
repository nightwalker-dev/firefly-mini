"""Comprehensive test suite for Phase 3: Adaptive Memory (Features 36-55)."""

import time

from typer.testing import CliRunner

from firefly.cli import app
from firefly.memory.consent import ConsentManager
from firefly.memory.decay import MemoryDecayManager
from firefly.memory.ledger import ToolReliabilityLedger
from firefly.memory.preferences import (
    HabitLearner,
    PersonaContinuity,
    RoutineDetector,
    UserPreferencesManager,
)
from firefly.memory.project import ProjectContextManager
from firefly.memory.redactor import SecretRedactor
from firefly.memory.retrieval import ContextAwareRetriever, ContradictionHandler
from firefly.memory.snapshots import MemorySnapshotManager, TaskResumeManager
from firefly.memory.store import MemoryItem, MemoryLayer, MemoryStore
from firefly.memory.summarizer import SessionSummarizer


# ==============================================================================
# Feature 45: Secret Redaction Pipeline
# ==============================================================================
def test_secret_redactor():
    raw = (
        "User entered token ghp_123456789012345678901234567890123456 and password='SuperSecretPassword' "
        "along with totp_secret='JBSWY3DPEHPK3PXP'. Sudo call: echo 'mypass' | sudo -S."
    )
    redacted = SecretRedactor.redact(raw)

    assert "ghp_1234567890" not in redacted
    assert "[REDACTED_API_TOKEN]" in redacted
    assert "SuperSecretPassword" not in redacted
    assert "[REDACTED_SECRET]" in redacted
    assert "JBSWY3DPEHPK3PXP" not in redacted
    assert "totp_secret=[REDACTED_TOTP_SEED]" in redacted
    assert "echo [REDACTED_SUDO_INPUT] | sudo -S" in redacted
    assert SecretRedactor.has_secrets(raw) is True
    assert SecretRedactor.has_secrets("Just normal harmless text here.") is False


# ==============================================================================
# Features 36, 37, 52: Three-Layer SQLite Store, FTS, and Encryption at Rest
# ==============================================================================
def test_memory_store_three_layers_and_encryption(tmp_path):
    db_file = tmp_path / "test_memory.db"
    key_file = tmp_path / "test.key"
    store = MemoryStore(db_path=db_file, key_path=key_file)

    # 1. Add across all three layers
    st_mem = store.add_memory(
        layer=MemoryLayer.SHORT_TERM,
        key="session:last_tool",
        content="bash",
        importance=0.3,
    )
    ep_mem = store.add_memory(
        layer=MemoryLayer.EPISODIC,
        key="task:101",
        content="Installed nginx and verified service active",
        importance=0.6,
    )
    sem_mem = store.add_memory(
        layer=MemoryLayer.SEMANTIC,
        key="fact:os_distro",
        content="Arch Linux x86_64 with Wayland compositor",
        importance=0.9,
        pinned=True,
    )

    assert st_mem.layer == MemoryLayer.SHORT_TERM
    assert ep_mem.layer == MemoryLayer.EPISODIC
    assert sem_mem.layer == MemoryLayer.SEMANTIC

    # Verify encryption at rest: raw database file must not leak plaintext
    raw_db = db_file.read_bytes()
    assert b"Arch Linux x86_64 with Wayland compositor" not in raw_db

    # Verified decrypted retrieval
    loaded = store.get_memory(sem_mem.id)
    assert loaded is not None
    assert loaded.content == "Arch Linux x86_64 with Wayland compositor"
    assert loaded.pinned is True

    # Search via FTS or LIKE
    searched = store.search("nginx")
    assert len(searched) >= 1
    assert "Installed nginx" in searched[0].content


# ==============================================================================
# Feature 38: Session Dialogue Summarizer
# ==============================================================================
def test_session_summarizer(tmp_path):
    db_file = tmp_path / "test_summary.db"
    store = MemoryStore(db_path=db_file)
    summarizer = SessionSummarizer(store=store, max_active_turns=6)

    messages = [
        {"role": "user", "content": "What is the CPU usage?"},
        {"role": "assistant", "content": "CPU usage is 12% across 8 cores."},
        {"role": "user", "content": "Set the wallpaper to cyberpunk cat."},
        {"role": "assistant", "content": "Wallpaper applied via swaybg."},
        {"role": "user", "content": "What is my IP address?"},
        {"role": "assistant", "content": "Your IP address is 192.168.1.50."},
        {"role": "user", "content": "Check disk space."},
        {"role": "assistant", "content": "Disk space has 85GB available."},
    ]

    assert summarizer.needs_summary(messages) is True
    condensed = summarizer.condense_messages(messages, keep_recent=2)

    # Output should have 1 summary system message + 2 recent turns
    assert len(condensed) == 3
    assert condensed[0]["role"] == "system"
    assert "Context Summary" in condensed[0]["content"]
    assert condensed[-1]["content"] == "Disk space has 85GB available."


# ==============================================================================
# Features 39, 40, 50, 51: Preferences, Habits, Persona, Routine Detection
# ==============================================================================
def test_user_preferences_learning(tmp_path):
    store = MemoryStore(db_path=tmp_path / "pref.db")
    mgr = UserPreferencesManager(store)

    mgr.set_preference("editor", "nvim")
    assert mgr.get_preference("editor") == "nvim"

    # Natural dialogue extraction
    extracted = mgr.extract_preferences_from_text(
        "For editing files I prefer nano, and please switch to catppuccin theme."
    )
    assert extracted.get("editor") == "nano"
    assert extracted.get("theme") == "catppuccin"
    assert mgr.get_preference("editor") == "nano"
    assert mgr.get_preference("theme") == "catppuccin"


def test_habit_learner(tmp_path):
    store = MemoryStore(db_path=tmp_path / "habit.db")
    learner = HabitLearner(store)

    learner.record_command("pytest -q tests")
    learner.record_command("pytest -q tests")
    learner.record_command("pytest -q tests")
    learner.record_command("git status")

    frequent = learner.get_frequent_commands(min_count=3)
    assert len(frequent) == 1
    assert frequent[0][0] == "pytest -q tests"
    assert frequent[0][1] == 3


def test_persona_continuity(tmp_path):
    store = MemoryStore(db_path=tmp_path / "persona.db")
    persona = PersonaContinuity(store)

    greeting_initial = persona.generate_greeting()
    assert "Firefly Mini" in greeting_initial

    persona.record_interaction(user_name="NightHunter")
    for _ in range(30):
        persona.record_interaction()

    state = persona.get_state()
    assert state.master_name == "NightHunter"
    assert state.affinity_score > 2.0
    greeting_bonded = persona.generate_greeting()
    assert "NightHunter" in greeting_bonded


def test_routine_detector(tmp_path):
    store = MemoryStore(db_path=tmp_path / "routine.db")
    detector = RoutineDetector(store)

    detector.log_routine_action("clean_tmp")
    detector.log_routine_action("clean_tmp")
    detector.log_routine_action("clean_tmp")

    suggestion = detector.check_routine_suggestion("clean_tmp")
    assert suggestion is not None
    assert "You usually run 'clean_tmp'" in suggestion


# ==============================================================================
# Feature 41: Per-Project Memory
# ==============================================================================
def test_project_context_manager(tmp_path):
    repo_dir = tmp_path / "my_project"
    repo_dir.mkdir()
    (repo_dir / "pyproject.toml").write_text("[project]\nname='test-pkg'")

    store = MemoryStore(db_path=tmp_path / "proj.db")
    mgr = ProjectContextManager(store)

    info = mgr.detect_project(repo_dir)
    assert info.name == "my_project"
    assert info.project_type == "python"

    mgr.set_project_memory("my_project", "dev_port", "8080")
    val = mgr.get_project_memory("my_project", "dev_port")
    assert val == "8080"

    projs = mgr.list_project_memories("my_project")
    assert len(projs) == 1


# ==============================================================================
# Feature 42: Tool Reliability Ledger
# ==============================================================================
def test_tool_reliability_ledger(tmp_path):
    store = MemoryStore(db_path=tmp_path / "ledger.db")
    ledger = ToolReliabilityLedger(store)

    # Tool A: 9 successes, 1 failure
    for _ in range(9):
        ledger.record_run("bash_tool", success=True, latency_ms=10.0)
    ledger.record_run("bash_tool", success=False, latency_ms=20.0, error="Timed out")

    # Tool B: 2 successes, 8 failures
    for _ in range(2):
        ledger.record_run("flakey_tool", success=True, latency_ms=50.0)
    for _ in range(8):
        ledger.record_run("flakey_tool", success=False, latency_ms=50.0)

    stats_a = ledger.get_stats("bash_tool")
    assert stats_a.reliability == 0.9

    stats_b = ledger.get_stats("flakey_tool")
    assert stats_b.reliability == 0.2

    ranked = ledger.rank_tools(["flakey_tool", "bash_tool"])
    assert ranked == ["bash_tool", "flakey_tool"]


# ==============================================================================
# Features 43, 44, 55: Decay, Importance, and Compaction
# ==============================================================================
def test_memory_decay_and_compaction(tmp_path):
    store = MemoryStore(db_path=tmp_path / "decay.db")

    # Importance scoring
    assert MemoryDecayManager.score_importance("I prefer using vim editor") >= 0.7
    assert MemoryDecayManager.score_importance("Transient check completed") <= 0.5

    # Memory item decay
    item = MemoryItem(
        id="m1",
        layer=MemoryLayer.SEMANTIC,
        key="temp",
        content="temporary info",
        importance=0.8,
        created_at=time.time() - 86400 * 30,  # 30 days old
        last_accessed_at=time.time() - 86400 * 30,
        access_count=1,
        pinned=False,
    )
    score_unpinned = MemoryDecayManager.calculate_decay_score(item, current_time=time.time())
    assert score_unpinned < 0.2

    item.pinned = True
    score_pinned = MemoryDecayManager.calculate_decay_score(item, current_time=time.time())
    assert score_pinned == 0.8  # Pinned items do not decay!

    # Compaction
    for i in range(15):
        store.add_memory(
            layer=MemoryLayer.SEMANTIC,
            key=f"k_{i}",
            content=f"content {i}",
            importance=0.1,
            pinned=(i == 0),
        )

    # Force compaction to max 5 items
    pruned = MemoryDecayManager.compact(store, max_items=5, prune_score_threshold=0.9)
    assert pruned > 0
    remaining = store.list_memories(limit=100)
    assert len(remaining) <= 6


# ==============================================================================
# Feature 47: PII Consent Gate
# ==============================================================================
def test_consent_manager():
    consent = ConsentManager()

    assert consent.requires_consent("Call me at +1 (555) 234-5678") is True
    assert consent.requires_consent("Send the invoice to test.user@example.com") is True
    assert consent.requires_consent("Run pytest on the test directory") is False

    # Simulate consent rejection
    rejected = consent.request_consent(
        "Email is alice@domain.org",
        custom_callback=lambda pii_type, text: False,
    )
    assert rejected is False

    # Simulate consent approval
    approved = consent.request_consent(
        "Email is alice@domain.org",
        custom_callback=lambda pii_type, text: True,
    )
    assert approved is True


# ==============================================================================
# Features 48 & 49: Context-Aware Retrieval and Contradiction Handling
# ==============================================================================
def test_retrieval_and_contradiction(tmp_path):
    store = MemoryStore(db_path=tmp_path / "contra.db")
    contra = ContradictionHandler(store)
    retriever = ContextAwareRetriever(store)

    # 1. User says editor is nano
    f1 = contra.update_fact_with_supersession("pref:editor", "nano", importance=0.8)
    m1 = store.get_by_key("pref:editor")
    assert m1 is not None
    assert m1.content == "nano"

    # 2. Later user switches to nvim (contradiction!)
    f2 = contra.update_fact_with_supersession("pref:editor", "nvim", importance=0.9)
    active = store.get_by_key("pref:editor")
    assert active is not None
    assert active.content == "nvim"
    assert active.id == f2.id

    # The old fact is superseded but preserved
    old = store.get_memory(f1.id)
    assert old is not None
    assert old.superseded_by == f2.id

    # Format prompt injection block
    block = retriever.format_prompt_block("Open the config file in my editor")
    assert "FIREFLY ADAPTIVE MEMORY" in block
    assert "nvim" in block
    assert "nano" not in block  # Superseded fact excluded from prompt injection


# ==============================================================================
# Features 53 & 54: Snapshots and Task Resumption
# ==============================================================================
def test_snapshots_and_task_resume(tmp_path):
    store = MemoryStore(db_path=tmp_path / "snap.db")
    store.add_memory(layer=MemoryLayer.SEMANTIC, key="state", content="v1", importance=1.0)

    snap_mgr = MemorySnapshotManager(store, snapshot_dir=tmp_path / "snaps")
    snapshot = snap_mgr.create_snapshot(label="backup_v1")
    assert snapshot.item_count == 1

    # Modify state
    store.add_memory(layer=MemoryLayer.SEMANTIC, key="state", content="v2", importance=1.0)

    # Restore snapshot
    restored = snap_mgr.restore_snapshot(snapshot.snapshot_id)
    assert restored is True

    # Task Resume
    resume_mgr = TaskResumeManager(store)
    resume_mgr.suspend_task(
        task_id="task_build_99",
        description="Compiling C binaries for Wayland display backend",
        plan_steps=["Install gcc", "Compile libei", "Link ydotool"],
        current_step=1,
    )

    resumed = resume_mgr.get_latest_suspended_task()
    assert resumed is not None
    assert resumed.task_id == "task_build_99"
    assert resumed.current_step == 1

    resume_mgr.mark_completed("task_build_99")
    assert resume_mgr.get_latest_suspended_task() is None


# ==============================================================================
# Feature 46: `firefly memory` CLI
# ==============================================================================
def test_memory_cli():
    runner = CliRunner()
    res = runner.invoke(app, ["memory", "--help"])
    assert res.exit_code == 0
    assert "Adaptive Memory commands" in res.stdout

    res_list = runner.invoke(app, ["memory", "list"])
    assert res_list.exit_code == 0
    assert "Firefly Mini" in res_list.stdout
