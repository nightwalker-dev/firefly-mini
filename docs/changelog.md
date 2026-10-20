# Changelog

All notable changes to **Firefly Mini** are documented in this file and tracked in the root [`CHANGELOG.md`](https://github.com/nighthunter/fire-bot/blob/main/CHANGELOG.md).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.1.0] - 2026-10-12

### Added
- **Structured JSON Logging (Feature 106)**: Added `firefly.observability.json_logger` with `JSONFormatter`, automatic size-based log rotation, and real-time credential scrubbing via `SecretRedactor`.
- **Performance & Health Metrics (Feature 107)**: Added `MetricsCollector` tracking task success rate, execution latencies (avg and p95), tool reliability breakdowns, and persistent telemetry snapshots.
- **CLI Metrics Dashboard (Feature 108)**: Introduced `firefly stats` terminal dashboard with ANSI colorization and `--json` export support.
- **Lightweight Distributed Tracing (Feature 109)**: Introduced `Tracer` and `TraceSpan` with hierarchical waterfall visualization, execution timing, and OpenTelemetry schema compatibility.
- **Pytest Categorization (Feature 110)**: Configured custom pytest markers (`unit`, `integration`, `adversarial`, `slow`) in `pyproject.toml`.
- **Multi-Version GitHub Actions CI (Feature 111)**: Configured `.github/workflows/ci.yml` matrix covering Python 3.10 through 3.13 with Ruff, Mypy, and Pytest steps.
- **Git Pre-commit Hooks (Feature 112)**: Added `.pre-commit-config.yaml` with linting, formatting, type checking, and an automated regex credential scanner.
- **Simulation Mocks (Feature 113)**: Implemented `MockLLM` with canned and queued responses, and `MockDesktop` with virtual display, mouse/keyboard tracking, and headless synthetic screenshot rendering.
- **Deterministic Session Replay (Feature 114)**: Added `SessionRecorder` and `SessionPlayer` enabling lossless session serialization and replay regression test validation.
- **Shell Auto-Completion (Feature 115)**: Added `firefly completion` supporting Bash, Zsh, and Fish shell completions.
- **Systemd Daemon Integration (Feature 116)**: Added `systemd/firefly-mini.service` template and `firefly service [install|status|uninstall]` CLI management commands.
- **Idempotent Installation Script v2 (Feature 117)**: Upgraded `setup.sh` with `/etc/os-release` Linux distribution detection (Arch, Debian/Ubuntu, Fedora/RHEL), `--dry-run`, `--check`, `--force`, and automated venv provisioning.
- **Containerized Environments (Feature 118)**: Created multi-stage `Dockerfile` (headless Xvfb support) and `.devcontainer/devcontainer.json` for reproducible VS Code devcontainers.
- **Semantic Versioning & Changelog (Feature 119)**: Synchronized package version `2.1.0` in `src/firefly/__init__.py` and established Keep a Changelog standards.
- **MkDocs Documentation (Feature 120)**: Built comprehensive MkDocs Material documentation covering architecture, threat model, plugin guide, and API reference.

---

## [2.0.0] - 2026-10-10

### Added
- Autonomous terminal healing engine with AST diagnosis and self-correcting shell loops (Phase 2).
- Vectorized memory hierarchy with SQLite persistent episodic store and Cosine similarity retrieval (Phase 3).
- Visual perception engine with OCR extraction, icon recognition, and grounded click dispatch (Phase 4).
- Cyber-cat audio engine with STT/TTS pipeline, push-to-talk, and purr acoustics (Phase 5).
- Multi-tier unbypassable security guardrails with TOTP MFA gate, hardware kill-switch, and regex blocklist (Phase 6).
