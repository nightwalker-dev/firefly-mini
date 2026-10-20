<p align="center">
  <img src="https://raw.githubusercontent.com/catppuccin/catppuccin/main/assets/misc/transparent.png" height="10" />
</p>

<div align="center">

```ascii
     /\_/\      ⚡  F I R E F L Y   M I N I  ⚡
    ( o.o )     » Autonomous Cyber-Cat Desktop Agent «
     > ^ <      Terminal Sentinel • Self-Healing • Zero-Trust
```

# 🐾 FIREFLY MINI
### *Your Autonomous Cyber-Cat Companion & Zero-Trust Terminal Sentinel*

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows%20%7C%20macOS-7057ff?style=for-the-badge&logo=linux&logoColor=white)](#-cross-platform-matrix)
[![Tests](https://img.shields.io/badge/Tests-317%20Passed-00F0FF?style=for-the-badge&logo=pytest&logoColor=black)](file:///home/nighthunter/Documents/fire-bot/tests)
[![Code Style: Ruff](https://img.shields.io/badge/Code%20Style-Ruff-000000?style=for-the-badge&logo=ruff&logoColor=white)](https://github.com/astral-sh/ruff)
[![Type Checked: Mypy](https://img.shields.io/badge/Type%20Checked-Mypy-50FA7B?style=for-the-badge&logo=python&logoColor=black)](https://mypy-lang.org/)
[![Version](https://img.shields.io/badge/Version-2.1.0%20Cyber--Neon-BD93F9?style=for-the-badge)](file:///home/nighthunter/Documents/fire-bot/CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-FFB86C?style=for-the-badge)](https://opensource.org/licenses/MIT)

<p align="center">
  <b>Tired of rigid AI scripts and dangerous terminal commands?</b><br>
  Meet <b>Firefly Mini</b> — an agile, anime-inspired cyber-feline companion that lives in your terminal and desktop.<br>
  It repairs broken commands, automates repetitive GUI workflows, guards your system against destructive mishaps, and reacts with charming feline audio-visual telemetry.
</p>

[✨ Superpowers & Benefits](#-why-firefly-mini-key-benefits--superpowers) •
[🚀 Quick Installation](#-installation--setup) •
[🎮 How to Use](#-how-to-use-step-by-step-guide) •
[🛡️ Zero-Trust Guardrails](#-unbypassable-zero-trust-guardrails) •
[🎨 Aesthetic HUD](#-anime-cyberpunk-hud--theming) •
[⌨️ CLI Cheat Sheet](#-cli-command-cheat-sheet)

</div>

---

## 🌟 Why Firefly Mini? (Key Benefits & Superpowers)

Traditional AI assistants either live in browser silos or run dangerous commands blindly. **Firefly Mini bridges this gap with intelligence, aesthetics, and safety:**

### 🛡️ 1. Zero-Trust Autonomous Guardrails (Accident-Proof)
- **Never Wipes Your System:** Commands like `rm -rf /`, `mkfs.*`, disk overwrites, and fork bombs are intercepted by unbypassable, AST-level regex filters before execution.
- **Human-in-the-Loop & TOTP MFA:** Elevated or sensitive actions require your confirmation or a 6-digit TOTP challenge.
- **Tamper-Evident SHA-256 Audit Trail:** Every single command and state change is cryptographically chained.

### 🩺 2. Autonomous Terminal Self-Healing
- **Instant Error Diagnosis:** When a bash, PowerShell, or compiler command fails, Firefly diagnoses the AST output, fixes missing dependencies (via `apt`, `pacman`, `dnf`, or `winget`), corrects typos, and retries safely.
- **Lessons Learned Store:** The agent remembers past failures and does not repeat them.

### 🧠 3. 3-Tier Encrypted Memory (Privacy-First)
- **Semantic, Episodic & Short-Term Memory:** Retains your shell preferences, project architecture contexts, and personal workflows across sessions.
- **Local SQLite + Fernet Encryption:** All stored memories are encrypted with local cryptographic keys. Zero telemetry leaks to the cloud.
- **Automated Secret Redaction:** API tokens, SSH keys, and passwords are automatically scrubbed in real-time from console logs, audio speech, prompts, and memory.

### 🎙️ 4. Multimodal Desktop & Voice Telemetry
- **Procedural Feline Audio:** Synthesizes custom sine-wave purrs, chirps, hiss-alerts, and meows mathematically on-the-fly.
- **Wake-Word Voice Companion:** Hands-free voice commands via Whisper Speech-to-Text and Piper/Windows SAPI Text-to-Speech.
- **Visual Desktop Automation:** Locates UI elements on screen, controls mouse clicks, and types text across Wayland, X11, and Windows.

### 🎨 5. Cyberpunk Anime Aesthetics
- **Live Terminal HUD:** Rich real-time TUI dashboard with animated feline holographic expressions, Unicode CPU/RAM sparklines, and active reasoning states.
- **Harmonious Theme Engine:** Built-in Catppuccin, Tokyo-Night, Dracula, and Cyber-Matrix themes with procedural neon wallpaper generation.

---

## 🔮 Cyber-Cat Terminal HUD Preview

When you launch `firefly hud`, your terminal transforms into a live holographic mission control:

```ascii
╭─────────────────────────────────────────────────────────────────────────────╮
│  🐾 Firefly Mini Cyber-Cat Terminal Sentinel                  [STATUS: OK]  │
├──────────────────────────────────────┬──────────────────────────────────────┤
│      /\_/\    *ears perk up*         │  Host: cyber-sentinel                │
│     ( =^･ω･^= )                      │  OS: Linux x86_64 / Windows 11       │
│     (  "  "  )  [MOOD: VIGILANT]     │  Guardrail Risk Floor: LOW [1]       │
│                                      │  Active State: REASONING (RE-ACT)    │
│  "Master, your system defense is     │  Last Tool: bash_run (exit=0)        │
│   fully armed and purring softly."   │  Memory Store: 42 records encrypted  │
├──────────────────────────────────────┴──────────────────────────────────────┤
│  ⚡ Telemetry: CPU [ ▅█▃  18% ]  RAM [ ▅▅▅  4.2GB / 16GB ]  DISK [ 128GB Free ]│
│  🔐 Audit Hash: sha256:8f2a...c041 (Integrity Verified)                     │
╰─────────────────────────────────────────────────────────────────────────────╯
```

---

## 🌐 Cross-Platform Matrix

Firefly Mini is built with a unified OS abstraction engine ([`firefly.core.platform`](file:///home/nighthunter/Documents/fire-bot/src/firefly/core/platform.py)):

| Feature | Linux (Wayland / X11) | Windows 10 / 11 | macOS |
| :--- | :--- | :--- | :--- |
| **Shell Runner** | `bash`, `sh`, `zsh` | `PowerShell` / `pwsh` / `cmd.exe` | `zsh`, `bash` |
| **GUI Automation** | `ydotool` / `xdotool` / `wtype` | `PyAutoGUI` native driver | `PyAutoGUI` |
| **Screen Capture** | `grim` (Wayland) / `scrot` (X11) | `mss` / `PIL.ImageGrab` | `mss` / `ImageGrab` |
| **Audio Engine** | `pw-play` / `paplay` / `aplay` | `winsound` / `Media.SoundPlayer` | `afplay` / `ffplay` |
| **Speech (TTS)** | Piper TTS / `espeak-ng` | Windows SAPI (`System.Speech`) | macOS `say` / Piper |
| **Wallpaper** | `swaybg` / `feh` / `gsettings` / `hyprctl`| Win32 `SystemParametersInfoW` | AppleScript |
| **Config / Data**| `~/.config/firefly-mini` | `%APPDATA%\firefly-mini` | `~/Library/Application Support` |

---

## 🚀 Installation & Setup

### 🐧 Linux & macOS (Automated)

Run the idempotent sentinel script:
```bash
git clone https://github.com/nighthunter/fire-bot.git
cd fire-bot

# Automated setup (checks packages, provisions .venv, installs dependencies)
./setup.sh
```

*Want to preview changes first?*
```bash
./setup.sh --dry-run
```

---

### 🪟 Windows 10 / 11

#### Option 1 — PowerShell (Recommended)
Open PowerShell as a standard user:
```powershell
git clone https://github.com/nighthunter/fire-bot.git
cd fire-bot

Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\setup.ps1
```

#### Option 2 — Command Prompt (CMD)
Simply run the batch installer:
```cmd
setup.bat
```

---

### 📦 Manual Setup (Any Platform)

```bash
python -m venv .venv

# Activate environment:
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# Install in editable mode with development tools:
pip install --upgrade pip
pip install -e ".[dev]"
```

---

## 🎮 How to Use (Step-by-Step Guide)

### Step 1: Run Environment Health Check (`doctor`)
Make sure your system audio, display drivers, and dependencies are green:
```bash
firefly doctor
```

---

### Step 2: Configure Your LLM Brain
Firefly Mini uses standard OpenAI-compatible REST endpoints. By default, it connects to a local, privacy-first **[Ollama](https://ollama.ai)** instance running `qwen2.5:7b-instruct`.

#### Choice A: 100% Offline with Ollama (Recommended)
```bash
# Install and run Ollama
ollama run qwen2.5:7b-instruct
```

#### Choice B: Cloud LLM (OpenAI, OpenRouter, Groq, vLLM)
Set standard environment variables:
```bash
# Linux / macOS:
export FIREFLY_LLM_BASE_URL="https://api.openai.com/v1"
export FIREFLY_LLM_API_KEY="sk-your-secret-key"
export FIREFLY_LLM_MODEL="gpt-4o-mini"

# Windows PowerShell:
$env:FIREFLY_LLM_BASE_URL="https://api.openai.com/v1"
$env:FIREFLY_LLM_API_KEY="sk-your-secret-key"
$env:FIREFLY_LLM_MODEL="gpt-4o-mini"
```

#### Choice C: Config File (`config.toml`)
Create `~/.config/firefly-mini/config.toml` (or `%APPDATA%\firefly-mini\config.toml` on Windows):
```toml
[llm]
base_url = "http://localhost:11434/v1"
api_key = "ollama"
model = "qwen2.5:7b-instruct"
timeout = 120.0
max_retries = 2

[guardrails]
auto_approve_max_risk = 1  # 0=prompt everything, 1=auto-approve safe read operations
shell_timeout = 120.0
max_output_chars = 12000

[features]
enable_voice = true
enable_vision = true
enable_hud = true
```

---

### Step 3: Interactive Cyber-Cat Chat
Start an interactive terminal dialogue with Firefly:
```bash
firefly chat
```

**Example Conversation:**
```
(=^･ω･^=) ❯ Check my RAM usage and find any process consuming more than 1GB.
🐾 Master: Check my RAM usage and find any process consuming more than 1GB.
*ears perk up* Examining memory ledger...
[Tool: bash_run -> ps aux --sort=-%mem | head -n 5]
(=^･ω･^=) Firefly: *chirp* Master, you have 11.8 GB free of 16 GB.
Top memory consumer is 'firefox' at 1.4 GB. All other processes are calm!
```

**Direct Instruction (Single Line):**
```bash
firefly chat "organize all downloads older than 30 days into an archive folder"
```

**Engage Read-Only Safe Mode:**
```bash
firefly chat --safe-mode "audit open ports and system users"
```

---

### Step 4: Anime Cyberpunk HUD & Themes

```bash
# Launch the live interactive HUD
firefly hud

# Render a single snapshot of system status
firefly hud --once

# Switch aesthetic color palette
firefly theme set tokyo-night
firefly theme set catppuccin-mocha
firefly theme set cyber-matrix

# Generate & set procedural neon cyber-cat wallpaper:
firefly theme
```

---

### Step 5: Voice Companion & SFX
```bash
# Listen for hands-free wake-word ("firefly")
firefly voice run

# Play procedural mathematical audio effects
firefly voice test-sfx purr
firefly voice test-sfx chirp
firefly voice test-sfx alert
firefly voice test-sfx meow

# Test secret-redacted Text-to-Speech
firefly voice test-tts "Firefly Mini defense online."

# Diagnostic check for microphone & Voice Activity Detection (VAD)
firefly voice vad-check
```

---

### Step 6: Memory & Telemetry Ledger
```bash
# List long-term remembered context and preferences
firefly memory list

# Search through memory
firefly memory search "python project guidelines"

# View system operational telemetry (p95 latency, tool reliability)
firefly stats

# Verify cryptographic hash chain integrity
firefly audit verify
```

---

### Step 7: Emergency Brakes (Kill-Switch)
If you ever want to immediately halt all agent reasoning and background tools:
```bash
# Engage emergency stop
firefly stop --reason "Manual emergency override"

# Disengage and return to service
firefly reset
```

---

## 🛡️ Unbypassable Zero-Trust Guardrails

Firefly Mini treats the command line as a high-security surface. Before any command executes:

```
[ User or LLM Command ]
          │
          ▼
┌───────────────────────────────────────────────┐
│        AST Guardrail Inspection               │
│  - Unpack shell operators (&&, ||, |, ;, `)   │
│  - Strip wrappers (sudo, env, nohup, xargs)   │
│  - Evaluate nested code (bash -c, $(...))     │
└───────────────────────┬───────────────────────┘
                        │
       ┌────────────────┴────────────────┐
       ▼                                 ▼
[ Risk Level 4: BLOCK ]        [ Risk Level 2-3: CONFIRM / MFA ]
- Root deletion (`rm -rf /`)   - Package installation / removal
- Disk wipe (`dd`, `mkfs`)     - Firewall modifications (`ufw`)
- Fork bombs & reverse shells  - Sudoers alterations
- Kernel memory writes         - Elevated daemon reloads
       │                                 │
       ▼                                 ▼
   [ REJECTED ]               [ Interactive Human Prompt / TOTP ]
```

---

## ⌨️ CLI Command Cheat Sheet

```bash
# Main Operations
firefly chat [PROMPT]                 # Interactive conversation or direct instruction
firefly chat -s "inspect services"    # Read-only Safe Mode execution

# Aesthetics & Display
firefly hud                           # Live cyberpunk TUI telemetry HUD
firefly hud --once                    # Single snapshot status render
firefly theme                         # Generate & apply cyber-cat neon wallpaper
firefly theme list                    # List available color schemes
firefly theme set [NAME]              # Activate palette (tokyo-night, cyber-matrix...)
firefly theme a11y                    # Verify WCAG 2.1 color contrast compliance

# Health & Observability
firefly doctor                        # Comprehensive system diagnostic audit
firefly stats                         # Reliability metrics, success rate & p95 latency
firefly audit show                    # View cryptographic action ledger
firefly audit verify                  # Verify SHA-256 tamper-evident hash chain

# Audio & Voice
firefly voice run                     # Background voice listener with wake-word
firefly voice test-sfx [chirp|purr]   # Procedural acoustic sound synthesis
firefly voice test-tts [TEXT]         # Secret-scrubbed speech synthesis
firefly voice vad-check               # Microphone & VAD readiness audit

# Adaptive Memory
firefly memory list                   # List stored memories
firefly memory search [QUERY]         # Search semantic memories
firefly memory wipe                   # Clear unpinned temporary memories

# Safety & Daemon
firefly stop                          # Immediate global kill-switch
firefly reset                         # Disengage kill-switch
firefly service install               # Install systemd user background service (Linux)
firefly service status                # Check background daemon status
```

---

## 🧪 Testing & Quality Assurance

Firefly Mini is tested rigorously with **317 automated tests** spanning 9 comprehensive test suites:

```bash
# Run complete test suite (unit, integration, adversarial, safety)
.venv/bin/pytest tests/ -v

# Strict code style and formatting check
.venv/bin/ruff check src/ tests/
.venv/bin/ruff format --check src/ tests/

# Static type verification
.venv/bin/mypy src/
```

---

## 📄 License

This project is open-source software licensed under the **[MIT License](file:///home/nighthunter/Documents/fire-bot/pyproject.toml)**.  
Built with pride for Linux and Windows terminal enthusiasts.

<div align="center">
  <sub>🐾 Designed with cyberpunk precision and feline agility. (=^･ω･^=)</sub>
</div>
