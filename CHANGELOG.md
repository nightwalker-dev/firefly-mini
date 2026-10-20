# Changelog

All notable changes to the **Firefly Mini** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.1.0] - 2026-10-12

### Added
- **Phase 7: DX, Testing, Observability & Packaging** (Features 106–120):
  - Structured JSON logging with levels, rotation, and secret redaction (`firefly.observability.json_logger`).
  - Operational metrics tracking task success rates, retries, latency p95/avg, and tool reliability (`firefly.observability.metrics`).
  - `firefly stats` visual dashboard with telemetry panels and guardrail posture.
  - ReAct step tracing with duration spans, OpenTelemetry compatibility, and text waterfall trees (`firefly.observability.tracing`).
  - Pytest markers (`unit`, `integration`, `adversarial`, `slow`) in `pyproject.toml`.
  - Multi-version GitHub Actions CI pipeline (`.github/workflows/ci.yml`).
  - Pre-commit hooks (`.pre-commit-config.yaml`) with ruff, mypy, and secret scanning.
  - Deterministic `MockLLM` and `MockDesktop` for offline automated tests (`firefly.testing.mocks`).
  - Session interaction recorder and regression replay comparator (`firefly.testing.recorder`).
  - Shell completion scripts generator for bash, zsh, and fish (`firefly completion`).
  - systemd user service manifest (`systemd/firefly-mini.service`) and management CLI (`firefly service install|status`).
  - Idempotent `setup.sh` v2 with distro detection (Arch, Debian, Fedora), `--check`, and `--dry-run`.
  - Containerized test setup (`Dockerfile` & `.devcontainer/devcontainer.json`).
  - Complete architecture, threat model, and plugin documentation site (`mkdocs.yml` & `docs/`).
- **Phase 6: Safety Hardening & Defense-in-Depth** (Features 91–105):
  - Declarative policy-as-code YAML engine with startup validation (`firefly.security.policy`).
  - Granular per-tool permission scopes (`fs:read`, `fs:write`, `proc:exec`, `sys:admin`) with least-privilege defaults (`firefly.security.scopes`).
  - Path canonicalization, allowlist/denylist, and directory traversal defense.
  - Network egress policy rules for network binaries (`curl`, `wget`, `ssh`).
  - Cryptographic tamper-evident SHA-256 hash-chain audit trail with `firefly audit verify` (`firefly.security.audit`).
  - Command provenance tracking linking commands to user prompts and ReAct thoughts (`firefly.security.provenance`).
  - Prompt-injection defense for untrusted OCR and scraped HTML data (`firefly.security.injection`).
  - Multi-bucket sliding-window rate limiters for destructive commands and input floods (`firefly.security.rate_limiter`).
  - Sandboxed command runner with Bubblewrap (`bwrap`), Firejail, and container fallback (`firefly.security.sandbox`).
  - Pre-operation filesystem restore points (btrfs, timeshift, rsync) with atomic rollback (`firefly.security.snapshot`).
  - Guardrail fuzzer testing resilience against pathological inputs and unbalanced quotes.
  - Red-team evasion test pack blocking base64 execution, hex printf, reversed string tricks, and heredocs.
  - Safe-mode controller restricting execution to strictly read-only inspection (`firefly.security.safe_mode`).
  - Session lifetime tracking and inactivity auto-lock guard with PIN authentication (`firefly.security.session`).
  - Block explainer generating clear hazard justifications and actionable safer command alternatives (`firefly.security.explainer`).
- **Phase 5: Voice & Audio Subsystem** (Features 81–90):
  - Procedural mathematical wave audio synthesizer generating 8 cyber-cat soundbites with zero external assets.
  - CyberSpeaker with volume control, mute toggling, multi-backend player fallback, and markdown/SSML cleaning.
  - Voice Activity Detection (VAD) via RMS energy noise gating and silence trimming.
  - WakeWordMatcher supporting exact and fuzzy phonetic Levenshtein matching.
  - VoiceListener running offline Whisper transcription with mock fallbacks.
  - Acoustic event subscriber synchronizing EventBus topics to feline soundbites.
  - Voice CLI commands (`run`, `test-sfx`, `test-tts`, `vad-check`).
- **Phase 4: Visual Appeal & Anime Cyberpunk HUD** (Features 56–80):
  - Cyber-cat ASCII avatar engine with dynamic mood matrix, idle blinking, and ear twitches.
  - Theme manager with 5 high-contrast themes meeting WCAG AA/AAA standards.
  - Live Rich terminal HUD with ASCII sparklines, system telemetry, and command palette.
  - Desktop themer exporting synchronized colors to Kitty, Alacritty, WezTerm, Ghostty, Foot, and Starship.
- **Phase 3: Adaptive Memory System** (Features 36–55):
  - 3-layer encrypted memory store (Short-Term, Episodic, Semantic) with AES-GCM encryption.
  - Secret redaction engine preventing credential leakage.
  - Context-aware memory retrieval and contradiction resolution.
  - Persona continuity and user habit learning.
- **Phase 2: Self-Healing & Error Correction** (Features 16–35):
  - ReAct reflection loop analyzing stderr and exit codes with fix proposals.
  - Error classifier, exponential backoff, and loop detector.
  - `firefly doctor` diagnostic command.
- **Phase 1: Structure Refactor** (Features 1–15):
  - Standardized `src/firefly/` package layout with pyproject.toml.
  - Central EventBus pub/sub, Dependency Injection container, Result[T, E] pattern.
