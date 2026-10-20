"""Firefly Mini — Command-Line Interface and Subsystem Runner."""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import time
from typing import Optional

import typer
from rich import print as rprint
from rich.table import Table

from firefly.agent.agent import FireflyAgent
from firefly.core.config import settings
from firefly.core.guardrails import KillSwitch
from firefly.core.logger import logger
from firefly.display.base import get_display_backend
from firefly.system.themer import themer
from firefly.ui.hud import hud
from firefly.voice.listener import listener
from firefly.voice.speaker import speaker

app = typer.Typer(
    name="firefly",
    help="🐾 Firefly Mini: Autonomous Cyber-Cat Linux Desktop & Terminal Agent.",
    add_completion=False,
)
kill_switch = KillSwitch(settings.stop_file)


@app.command()
def chat(
    prompt: Optional[str] = typer.Argument(None, help="Command or query for Firefly Mini"),
    safe_mode: bool = typer.Option(False, "--safe-mode", "-s", help="Engage read-only Safe Mode"),
) -> None:
    """Chat with Firefly Mini or start an interactive session."""
    from firefly.security.safe_mode import default_safe_mode

    if safe_mode:
        default_safe_mode.enable()
        rprint("[bold yellow]🛡 Safe Mode active: agent will perform read-only inspection only.[/]")

    if kill_switch.engaged:
        rprint("[bold red]🚨 EMERGENCY KILL SWITCH ENGAGED! Run 'firefly reset' to clear.[/]")
        sys.exit(1)

    agent = FireflyAgent()

    if prompt:
        rprint(f"[bold #BD93F9]🐾 Master:[/] {prompt}")
        ans = asyncio.run(agent.chat(prompt))
        rprint(f"[bold #00F0FF](=^･ω･^=) Firefly:[/] {ans}")
        return

    speaker.chirp()
    rprint("[bold #00F0FF]🐾 Firefly Mini Cyber-Cat Terminal Online. Type 'exit' to quit.[/]")

    while True:
        try:
            user_in = input("\n(=^･ω･^=) ❯ ").strip()
            if not user_in:
                continue
            if user_in.lower() in ("exit", "quit", "q"):
                speaker.purr()
                rprint("[dim #BD93F9]*purrs and curls up* Sleep well, master.[/]")
                break

            ans = asyncio.run(agent.chat(user_in))
            rprint(f"\n[bold #00F0FF]Firefly:[/] {ans}")
        except (KeyboardInterrupt, EOFError):
            print()
            break


@app.command(name="hud")
def hud_cmd(
    live: bool = typer.Option(
        True, "--live/--once", help="Run live interactive HUD or render single snapshot"
    ),
    duration: Optional[int] = typer.Option(None, "--duration", "-d", help="Run HUD for N seconds"),
    theme_name: Optional[str] = typer.Option(None, "--theme", "-t", help="Cyberpunk theme name"),
) -> None:
    """Launch the interactive anime-aesthetic cyberpunk status HUD."""
    from firefly.ui.themes import theme_manager

    if theme_name:
        theme_manager.set_theme(theme_name)
        hud.theme = theme_manager.current
    speaker.beep()
    if live:
        hud.run_live(duration_sec=float(duration) if duration else None)
    else:
        hud.display_once()


@app.command(name="hud-view")
def hud_view(
    duration: Optional[int] = typer.Option(None, "--duration", "-d", help="Run HUD for N seconds"),
) -> None:
    """Launch the live anime-aesthetic cyberpunk status HUD (alias)."""
    hud_cmd(live=True, duration=duration)


theme_app = typer.Typer(
    name="theme",
    help="🎨 Cyberpunk theme and palette manager (list, set, export, a11y, apply).",
    invoke_without_command=True,
)
app.add_typer(theme_app, name="theme")


@theme_app.callback(invoke_without_command=True)
def theme_callback(
    ctx: typer.Context,
    apply_all: bool = typer.Option(
        True, "--all/--wallpaper-only", help="Apply all themes or wallpaper only"
    ),
) -> None:
    """Generate and apply cyberpunk cat wallpaper and terminal themes."""
    if ctx.invoked_subcommand is None:
        rprint("[bold #BD93F9]✦ Generating Cyber-Cat Wallpaper & Themes...[/]")
        wp = themer.generate_cyber_cat_wallpaper()
        applied = themer.set_wallpaper(wp)
        rprint(f"[bold #00F0FF]✔ Wallpaper generated:[/] {wp} (Applied: {applied})")

        if apply_all:
            k = themer.export_kitty_theme()
            a = themer.export_alacritty_theme()
            f = themer.export_fastfetch_config()
            p = themer.export_shell_prompt()
            rprint(f"[bold #00F0FF]✔ Kitty config:[/] {k}")
            rprint(f"[bold #00F0FF]✔ Alacritty config:[/] {a}")
            rprint(f"[bold #00F0FF]✔ Fastfetch config:[/] {f}")
            rprint(f"[bold #00F0FF]✔ Shell prompt helper:[/] {p}")

        speaker.purr()
        rprint("[bold #FFB86C]🐾 Purrs! Dark Cyberpunk theme active.[/]")


@theme_app.command("list")
def theme_list() -> None:
    """List available cyberpunk color themes."""
    from firefly.ui.themes import theme_manager

    table = Table(title="🎨 Firefly Cyberpunk Themes", border_style="#BD93F9")
    table.add_column("Theme Name", style="bold #00F0FF")
    table.add_column("Display Name")
    table.add_column("Primary Neon", style="bold")
    table.add_column("Accent Color")

    for t in theme_manager.list_themes():
        is_cur = " (active)" if t.name == theme_manager.current.name else ""
        table.add_row(
            f"{t.name}{is_cur}",
            t.display_name,
            f"[{t.neon_primary}]██ {t.neon_primary}[/]",
            f"[{t.accent_amber}]██ {t.accent_amber}[/]",
        )
    rprint(table)


@theme_app.command("set")
def theme_set(theme_name: str = typer.Argument(..., help="Name of theme to activate")) -> None:
    """Activate a cyberpunk theme."""
    from firefly.ui.themes import theme_manager

    if theme_manager.set_theme(theme_name):
        hud.theme = theme_manager.current
        speaker.chirp()
        rprint(
            f"[bold green]✔ Activated theme:[/] [bold {theme_manager.current.neon_primary}]{theme_name}[/]"
        )
    else:
        rprint(
            f"[bold red]✘ Unknown theme '{theme_name}'. Run 'firefly theme list' to see available palettes.[/]"
        )


@theme_app.command("a11y")
def theme_a11y() -> None:
    """Verify WCAG 2.1 color contrast ratios across all themes."""
    from firefly.ui.themes import ContrastVerifier, theme_manager

    table = Table(title="👁 WCAG 2.1 Contrast & Accessibility Audit", border_style="#00F0FF")
    table.add_column("Theme", style="bold")
    table.add_column("Contrast Ratio")
    table.add_column("WCAG AA Status", style="bold")

    for t in theme_manager.list_themes():
        ratio = ContrastVerifier.calculate_contrast_ratio(t.fg_text, t.bg_dark)
        passes = ratio >= 4.5
        status = "[green]PASS (>= 4.5:1)[/]" if passes else "[red]FAIL (< 4.5:1)[/]"
        table.add_row(t.display_name, f"{ratio:.2f}:1", status)

    rprint(table)


@theme_app.command("export")
def theme_export(
    target: str = typer.Argument(
        ..., help="Target terminal: kitty, alacritty, wezterm, ghostty, foot, starship"
    ),
    out: Optional[str] = typer.Option(None, "--out", "-o", help="Target output file path"),
) -> None:
    """Export theme configuration for terminal emulators."""
    from pathlib import Path

    out_p = Path(out) if out else None
    t_clean = target.lower().strip()

    if t_clean == "kitty":
        p = themer.export_kitty_theme(out_p)
    elif t_clean == "alacritty":
        p = themer.export_alacritty_theme(out_p)
    elif t_clean == "wezterm":
        p = themer.export_wezterm_theme(out_p)
    elif t_clean == "ghostty":
        p = themer.export_ghostty_theme(out_p)
    elif t_clean == "foot":
        p = themer.export_foot_theme(out_p)
    elif t_clean in ("starship", "prompt"):
        p = themer.export_starship_preset(out_p)
    else:
        rprint(
            f"[bold red]✘ Unknown target '{target}'. Choose from: kitty, alacritty, wezterm, ghostty, foot, starship.[/]"
        )
        return

    rprint(f"[bold green]✔ Exported {target} config to:[/] {p}")


voice_app = typer.Typer(
    name="voice",
    help="🎙 Firefly voice & audio commands (run, test-sfx, test-tts, vad-check).",
    invoke_without_command=True,
)
app.add_typer(voice_app, name="voice")


def _run_voice_loop() -> None:
    if kill_switch.engaged:
        rprint("[bold red]🚨 EMERGENCY KILL SWITCH ENGAGED![/]")
        sys.exit(1)

    rprint(f"[bold #00F0FF]🎙 Listening for wake-word '{settings.wake_word}'... (Ctrl+C to stop)[/]")
    agent = FireflyAgent()
    speaker.chirp()

    while True:
        try:
            audio_text = listener.listen_and_transcribe(duration_sec=4.0)
            if not audio_text:
                continue

            rprint(f"[dim]Heard: {audio_text}[/]")
            triggered, cmd = listener.check_wake_word(audio_text)
            if triggered:
                speaker.beep()
                rprint(f"[bold #FFB86C]🐾 Wake-word triggered! Executing:[/] {cmd}")
                ans = asyncio.run(agent.chat(cmd))
                speaker.speak(ans)
                rprint(f"[bold #00F0FF]Firefly:[/] {ans}")
        except KeyboardInterrupt:
            rprint("\n[dim]Voice loop stopped.[/]")
            break


@voice_app.callback(invoke_without_command=True)
def voice_callback(ctx: typer.Context) -> None:
    """Start the offline voice listener or route to subcommands."""
    if ctx.invoked_subcommand is None:
        _run_voice_loop()


@voice_app.command("run")
def voice_run() -> None:
    """Start the voice listener daemon."""
    _run_voice_loop()


@voice_app.command("test-sfx")
def voice_test_sfx(
    sound: str = typer.Argument(
        "chirp", help="Sound name: chirp, purr, alert, beep, hiss, meow, fanfare, glitch"
    ),
) -> None:
    """Test procedural mathematical audio synthesis."""
    wav = speaker.generate_sound(sound)
    if wav:
        played = speaker.play_sound(sound)
        status = (
            "[green]Played successfully[/]" if played else "[yellow]Synthesized WAV file created[/]"
        )
        rprint(f"[bold green]✔ Sound '{sound}':[/] {wav} ({status})")
    else:
        rprint(f"[bold red]✘ Failed to synthesize sound '{sound}'.[/]")


@voice_app.command("test-tts")
def voice_test_tts(
    text: str = typer.Argument("Firefly Mini cyber defense online.", help="Text to speak"),
) -> None:
    """Test speech synthesis with secret redaction."""
    spoken = speaker.speak(text)
    rprint(f"[bold green]✔ Spoken (status: {spoken}):[/] '{speaker.clean_text_for_speech(text)}'")


@voice_app.command("vad-check")
def voice_vad_check() -> None:
    """Audit microphone recorder and voice activity detection."""
    from firefly.voice.vad import vad

    table = Table(title="🎙 Voice Subsystem & VAD Readiness", border_style="#00F0FF")
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    table.add_row(
        "Recorder Binary",
        "[green]FOUND[/]" if listener.recorder else "[red]MISSING[/]",
        str(listener.recorder or "None (parecord/arecord/ffmpeg required)"),
    )
    table.add_row(
        "Audio Output Player",
        "[green]READY[/]" if speaker.player else "[yellow]NONE[/]",
        str(speaker.player or "pw-play / paplay / aplay / ffplay"),
    )
    table.add_row(
        "VAD Noise Threshold",
        "[green]ACTIVE[/]",
        f"Energy RMS >= {vad.energy_threshold}",
    )
    table.add_row(
        "Wake-Word Matcher",
        "[green]ACTIVE[/]",
        f"Targets: {', '.join(settings.wake_word.split())}",
    )
    rprint(table)


audit_app = typer.Typer(
    name="audit",
    help="🔐 Tamper-evident hash-chained audit logging and verification.",
    invoke_without_command=True,
)
app.add_typer(audit_app, name="audit")


def _render_audit_table(limit: int = 20) -> None:
    records = logger.get_recent(limit=limit)
    table = Table(title="🐾 Firefly Mini Audit Trail", border_style="#BD93F9")
    table.add_column("Timestamp", style="dim")
    table.add_column("Kind", style="#00F0FF")
    table.add_column("Action", style="#E0DEF4")
    table.add_column("Risk", style="#FFB86C")
    table.add_column("Verdict", style="#BD93F9")
    table.add_column("Approved", style="bold")
    table.add_column("Summary", style="dim")

    for rec in reversed(records):
        t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(rec.timestamp))
        status = "[green]YES[/]" if rec.approved else "[red]NO[/]"
        table.add_row(
            t_str,
            rec.kind,
            rec.action[:40],
            rec.risk_level,
            rec.verdict_action,
            status,
            (rec.output_summary or "")[:30],
        )

    rprint(table)


@audit_app.callback(invoke_without_command=True)
def audit_callback(
    ctx: typer.Context,
    limit: int = typer.Option(20, "--limit", "-n", help="Number of records to show"),
) -> None:
    """Display recent encrypted audit trail entries."""
    if ctx.invoked_subcommand is None:
        _render_audit_table(limit=limit)


@audit_app.command("show")
def audit_show(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of records to show"),
) -> None:
    """Display recent encrypted audit trail entries."""
    _render_audit_table(limit=limit)


@audit_app.command("verify")
def audit_verify() -> None:
    """Cryptographically verify the integrity of the audit hash chain (Feature 95)."""
    from firefly.security.audit import default_audit_chain

    valid, bad_idx, reason = default_audit_chain.verify()
    if valid:
        rprint(f"[bold green]✔ Hash Chain Verified:[/] {reason}")
    else:
        rprint(f"[bold red]✘ Audit Log Tampering Detected:[/] Block index {bad_idx} - {reason}")
        sys.exit(1)


policy_app = typer.Typer(
    name="policy",
    help="📜 Policy-as-code configuration and rules checker (Feature 91).",
)
app.add_typer(policy_app, name="policy")


@policy_app.command("check")
def policy_check(
    policy_path: Optional[str] = typer.Argument(
        None, help="Path to policy YAML file (defaults to standard policy)"
    ),
) -> None:
    """Validate policy-as-code file syntax and active defense rules."""
    from pathlib import Path

    from firefly.security.policy import PolicyEngine, default_policy_engine

    try:
        engine = PolicyEngine.load_file(Path(policy_path)) if policy_path else default_policy_engine
        rprint(f"[bold green]✔ Policy Valid:[/] {engine.policy.name} (v{engine.policy.version})")
        rprint(f"  Rules loaded: {len(engine.policy.rules)}")
        rprint(f"  Denied paths: {len(engine.policy.paths.denied_paths)}")
        rprint(f"  Network mode: {engine.policy.network.mode}")
    except Exception as exc:
        rprint(f"[bold red]✘ Policy Validation Error:[/] {exc}")
        sys.exit(1)


@app.command()
def stop(reason: str = typer.Option("Manual emergency brake", "--reason", "-r")) -> None:
    """Trigger the global emergency kill-switch."""
    kill_switch.trigger(reason=reason)
    speaker.alert()
    rprint(f"[bold red]🚨 EMERGENCY KILL SWITCH ENGAGED! Reason: {reason}[/]")


@app.command()
def reset() -> None:
    """Clear the emergency kill-switch."""
    kill_switch.reset()
    speaker.chirp()
    rprint("[bold green]✔ Emergency kill switch cleared. Firefly Mini ready for action.[/]")


@app.command()
def status() -> None:
    """Audit system dependencies and readiness."""
    table = Table(title="🐾 Firefly Mini Subsystem Readiness", border_style="#00F0FF")
    table.add_column("Subsystem", style="bold")
    table.add_column("Status", style="bold")
    table.add_column("Details")

    # Guardrails
    table.add_row(
        "🛡 Guardrail Sandbox", "[green]ARMED[/]", f"Risk Floor: {settings.auto_approve_max_risk}"
    )

    # Audio
    has_audio = speaker.player is not None
    table.add_row(
        "🔊 Audio Engine",
        "[green]READY[/]" if has_audio else "[yellow]PARTIAL[/]",
        f"Player: {speaker.player or 'None'}",
    )

    # Piper
    table.add_row(
        "🗣 Piper TTS",
        "[green]FOUND[/]" if speaker.has_piper else "[yellow]FALLBACK[/]",
        f"Binary: {speaker.piper_bin}",
    )

    # Voice STT
    has_rec = listener.recorder is not None
    table.add_row(
        "🎙 Voice Capture",
        "[green]READY[/]" if has_rec else "[yellow]NONE[/]",
        f"Recorder: {listener.recorder or 'None'}",
    )

    # Display Server
    sess = os.environ.get("XDG_SESSION_TYPE", "wayland")
    display_backend = get_display_backend()
    table.add_row(
        "🖥 Display Backend",
        "[green]ONLINE[/]",
        f"{sess.upper()} ({type(display_backend).__name__})",
    )

    # Screen Capture
    has_cap = shutil.which("grim") or shutil.which("scrot") or shutil.which("import")
    cap_info = "grim/scrot" if has_cap else "mss (python native)"
    table.add_row("📸 Screen Capture", "[green]READY[/]", cap_info)

    # Audit DB
    table.add_row("🔐 Audit Database", "[green]ACTIVE[/]", str(settings.audit_db))

    rprint(table)


@app.command(name="doctor")
def doctor_cmd() -> None:
    """Run comprehensive system self-diagnosis (deps, audio, display, storage, safety)."""
    from firefly.healing.doctor import FireflyDoctor

    doc = FireflyDoctor()
    rprint(doc.render_table())


@app.command(name="stats")
def stats_cmd() -> None:
    """Display system performance, success rate, and tool reliability metrics (Feature 108)."""
    from rich.panel import Panel

    from firefly.observability.metrics import default_metrics

    summary = default_metrics.get_summary()

    # Panel overview
    overview_text = (
        f"[bold #00F0FF]Task Success Rate:[/] [bold green]{summary.success_rate}%[/]  "
        f"([green]{summary.successful_tasks} succeeded[/], [red]{summary.failed_tasks} failed[/])\n"
        f"[bold #BD93F9]Total Tasks:[/] {summary.total_tasks} | "
        f"[bold #FFB86C]Retries:[/] {summary.total_retries} | "
        f"[bold #50FA7B]Avg Latency:[/] {summary.avg_latency_ms:.1f}ms | "
        f"[bold #FF79C6]p95 Latency:[/] {summary.p95_latency_ms:.1f}ms"
    )
    rprint(
        Panel(
            overview_text,
            title="🐾 Firefly Mini Operational Telemetry",
            border_style="#00F0FF",
        )
    )

    # Tool Reliability Table
    tool_table = Table(title="⚡ Tool Reliability & Performance", border_style="#BD93F9")
    tool_table.add_column("Tool", style="bold cyan")
    tool_table.add_column("Calls", justify="right")
    tool_table.add_column("Success Rate", justify="right")
    tool_table.add_column("Avg Latency (ms)", justify="right")

    if summary.tool_reliability:
        for tool, data in summary.tool_reliability.items():
            rate_style = "green" if data["success_rate"] >= 90 else "yellow"
            tool_table.add_row(
                tool,
                str(data["calls"]),
                f"[{rate_style}]{data['success_rate']}%[/]",
                f"{data['avg_duration_ms']:.1f}",
            )
    else:
        tool_table.add_row("No tool invocations recorded yet", "-", "-", "-")
    rprint(tool_table)

    # Guardrail Posture Table
    gr_table = Table(title="🛡 Guardrail Enforcement Posture", border_style="#FF5555")
    gr_table.add_column("Verdict Action", style="bold")
    gr_table.add_column("Total Events", justify="right")
    for act, cnt in summary.guardrail_actions.items():
        color = {
            "allow": "green",
            "confirm": "yellow",
            "mfa": "magenta",
            "block": "red",
        }.get(act, "white")
        gr_table.add_row(f"[{color}]{act.upper()}[/]", str(cnt))
    rprint(gr_table)


@app.command(name="completion")
def completion_cmd(
    shell: str = typer.Argument("bash", help="Shell type: bash, zsh, fish"),
) -> None:
    """Generate shell tab-completion scripts (Feature 115)."""
    sh = shell.lower().strip()
    if sh == "bash":
        script = 'eval "$(_FIREFLY_COMPLETE=bash_source firefly)"'
    elif sh == "zsh":
        script = 'eval "$(_FIREFLY_COMPLETE=zsh_source firefly)"'
    elif sh == "fish":
        script = "eval (_FIREFLY_COMPLETE=fish_source firefly)"
    else:
        rprint(f"[bold red]Unsupported shell '{shell}'. Supported: bash, zsh, fish.[/]")
        return
    rprint(f"# Firefly Mini completion script for {sh}:\n{script}")


service_app = typer.Typer(
    name="service",
    help="⚙ Manage Firefly Mini systemd user service (Feature 116).",
)
app.add_typer(service_app, name="service")


@service_app.command("install")
def service_install(
    user_dir: Optional[str] = typer.Option(None, "--dir", help="Target systemd user directory"),
) -> None:
    """Install systemd user service for background daemon operation."""
    from pathlib import Path

    dest = (
        Path(user_dir).expanduser() if user_dir else (Path.home() / ".config" / "systemd" / "user")
    )
    dest.mkdir(parents=True, exist_ok=True)
    service_file = dest / "firefly-mini.service"

    firefly_bin = shutil.which("firefly") or str(Path(sys.executable).parent / "firefly")
    content = f"""[Unit]
Description=Firefly Mini Autonomous Cyber-Cat Desktop Agent
Documentation=https://github.com/nighthunter/fire-bot
After=graphical-session.target sound.target

[Service]
Type=simple
ExecStart={firefly_bin} chat
Restart=on-failure
RestartSec=5s
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
"""
    service_file.write_text(content, encoding="utf-8")
    rprint(f"[bold green]✔ Installed systemd service to:[/] {service_file}")
    rprint(
        "[dim]Run 'systemctl --user daemon-reload && systemctl --user enable --now firefly-mini' to start.[/]"
    )


@service_app.command("status")
def service_status() -> None:
    """Check systemd user service installation status."""
    from pathlib import Path

    svc_path = Path.home() / ".config" / "systemd" / "user" / "firefly-mini.service"
    if svc_path.exists():
        rprint(f"[bold green]✔ Service Installed:[/] {svc_path}")
    else:
        rprint("[yellow]Service not installed yet. Run 'firefly service install' to install.[/]")


# --------------------------------------------------------------------------- #
# Feature 46: Memory Management CLI Subcommands
# --------------------------------------------------------------------------- #
memory_app = typer.Typer(
    name="memory",
    help="🧠 Firefly Adaptive Memory commands (list, search, edit, forget, export, wipe).",
)
app.add_typer(memory_app, name="memory")


@memory_app.command("list")
def memory_list(
    layer: Optional[str] = typer.Option(
        None, "--layer", "-l", help="Filter by layer: semantic, episodic, short_term"
    ),
    limit: int = typer.Option(20, "--limit", "-n", help="Max entries to display"),
) -> None:
    """List stored memory entries."""
    from firefly.memory.store import MemoryLayer, MemoryStore

    store = MemoryStore()
    l_enum = MemoryLayer(layer) if layer else None
    items = store.list_memories(layer=l_enum, limit=limit)

    table = Table(title="🧠 Firefly Mini — Stored Memories", border_style="#BD93F9")
    table.add_column("ID", style="dim cyan", width=16)
    table.add_column("Layer", style="bold yellow", width=12)
    table.add_column("Key", style="bold green", width=24)
    table.add_column("Content", style="white")
    table.add_column("Score", justify="right", width=6)
    table.add_column("Pinned", justify="center", width=8)

    for it in items:
        table.add_row(
            it.id[:14] + "…",
            it.layer.value,
            it.key,
            it.content[:60] + ("…" if len(it.content) > 60 else ""),
            f"{it.importance:.2f}",
            "📌" if it.pinned else "-",
        )
    rprint(table)


@memory_app.command("search")
def memory_search(query: str = typer.Argument(..., help="Query keyword or phrase")) -> None:
    """Search memories via full-text index."""
    from firefly.memory.store import MemoryStore

    store = MemoryStore()
    results = store.search(query)
    table = Table(title=f"🔍 Memory Search Results for '{query}'", border_style="#00F0FF")
    table.add_column("ID", style="dim", width=16)
    table.add_column("Layer", style="yellow", width=12)
    table.add_column("Key", style="bold green", width=24)
    table.add_column("Matched Content", style="white")

    for it in results:
        table.add_row(
            it.id[:14] + "…",
            it.layer.value,
            it.key,
            it.content[:80] + ("…" if len(it.content) > 80 else ""),
        )
    rprint(table)


@memory_app.command("edit")
def memory_edit(
    memory_id: str = typer.Argument(..., help="ID of memory to modify"),
    new_value: str = typer.Argument(..., help="New memory content text"),
) -> None:
    """Update a stored memory item."""
    from firefly.memory.store import MemoryStore

    store = MemoryStore()
    if store.update_memory(memory_id, new_value):
        rprint(f"[bold green]✔ Memory {memory_id} updated successfully.[/]")
    else:
        rprint(f"[bold red]✘ Memory {memory_id} not found.[/]")


@memory_app.command("forget")
def memory_forget(key_or_id: str = typer.Argument(..., help="Memory ID or key to delete")) -> None:
    """Delete a memory item."""
    from firefly.memory.store import MemoryStore

    store = MemoryStore()
    # Try by ID first
    if store.delete_memory(key_or_id):
        rprint(f"[bold green]✔ Memory '{key_or_id}' forgotten.[/]")
        return
    # Try by key
    item = store.get_by_key(key_or_id)
    if item and store.delete_memory(item.id):
        rprint(f"[bold green]✔ Memory '{key_or_id}' forgotten.[/]")
        return
    rprint(f"[bold yellow]Item '{key_or_id}' was not found in memory.[/]")


@memory_app.command("export")
def memory_export(
    output_path: Optional[str] = typer.Option(None, "--out", "-o", help="Target JSON file path"),
) -> None:
    """Export memories to JSON format."""
    import json
    from dataclasses import asdict
    from pathlib import Path

    from firefly.memory.store import MemoryStore

    store = MemoryStore()
    items = store.list_memories(limit=10000)
    data = [asdict(it) for it in items]
    out_file = Path(output_path) if output_path else (Path.home() / "firefly_memory_export.json")
    out_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    rprint(f"[bold green]✔ Exported {len(items)} memories to {out_file}[/]")


@memory_app.command("wipe")
def memory_wipe(
    force: bool = typer.Option(False, "--force", "-f", help="Bypass confirmation prompt"),
) -> None:
    """Wipe unpinned memories."""
    from firefly.memory.store import MemoryStore

    if not force:
        confirm = typer.confirm("Are you sure you want to wipe all unpinned memories?")
        if not confirm:
            rprint("[dim]Aborted memory wipe.[/]")
            return
    store = MemoryStore()
    count = store.wipe(unpinned_only=True)
    rprint(f"[bold green]✔ Wiped {count} unpinned memories. Pinned items preserved.[/]")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
