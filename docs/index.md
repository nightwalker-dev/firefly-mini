# 🐾 Firefly Mini

**Autonomous Cyber-Cat Desktop Assistant & Terminal Defense Sentinel for Linux**

Firefly Mini is an open-source, lightweight, offline-capable Linux desktop assistant with an anime-cyberpunk aesthetic. It merges autonomous task reasoning (ReAct) with unbypassable terminal security guardrails, self-healing reflection loops, encrypted memory, and synthesized cyber-cat audio.

---

## ⚡ Quick Start

### Installation

```bash
git clone https://github.com/nighthunter/fire-bot.git
cd fire-bot
./setup.sh
```

### Launch Interactive HUD

```bash
firefly hud --live
```

### Run Autonomous Chat Turn

```bash
firefly chat "Check system disk usage and clean temporary logs in /tmp"
```

### Security Audit Verification

```bash
firefly audit verify
```

---

## 🛡 Key Features

1. **Unbypassable Guardrails**: Commands are evaluated through deep lexical analysis, AST parsing, and blast-radius predictors. Dangerous commands (`rm -rf /`, raw disk writes, fork bombs) are unconditionally blocked.
2. **Cryptographic Audit Chain**: Every command is logged into a tamper-evident SHA-256 hash chain verified with `firefly audit verify`.
3. **Adaptive Encrypted Memory**: Three distinct memory tiers (Short-Term, Episodic, Semantic) encrypted with AES-GCM and protected by an automated secret redaction pipeline.
4. **Self-Healing ReAct Loop**: Automatically classifies errors, retries with exponential backoff and jitter, performs dry runs, and suggests missing package fixes.
5. **Anime Cyberpunk Aesthetic**: Live ASCII cyber-cat HUD avatar with mood expressions, WCAG AAA compliant color themes, and procedural audio synthesis.
