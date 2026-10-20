"""Interactive Anime-Aesthetic Cyberpunk Terminal HUD for Firefly Mini.

Built with Rich. Displays:
- Feline cyber-avatar with animated holographic status expressions.
- Real-time CPU, RAM, Disk, and Network telemetry with Unicode sparklines.
- Guardrail sandbox status and audit log stream.
- Active agent state (Idle, Reasoning, Executing, Guardrail Verification).
- Interactive TUI Command Palette and EventBus synchronization.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Optional

import psutil
from rich.box import ROUNDED
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from firefly.core.config import settings
from firefly.core.events import Event, EventBus
from firefly.core.guardrails import Risk
from firefly.core.logger import logger
from firefly.ui.avatar import CatMoodEngine, CatState, avatar_animator
from firefly.ui.telemetry import render_gauge_bar, telemetry_engine
from firefly.ui.themes import CyberTheme, theme_manager

# Backwards-compatible palette mapping
PALETTE = {
    "cyan": "#00F0FF",
    "violet": "#BD93F9",
    "amber": "#FFB86C",
    "red": "#FF5555",
    "green": "#50FA7B",
    "bg": "#0B0A10",
    "panel": "#14121F",
    "dim": "#6E6A86",
}


class TerminalHUD:
    """Renders the cyber-feline terminal dashboard."""

    def __init__(self, console: Optional[Console] = None, theme: Optional[CyberTheme] = None):
        self.console = console or Console()
        self.theme = theme or theme_manager.current
        self.agent_state = "IDLE (LISTENING)"
        self.cat_state = CatState.IDLE
        self.last_action = "System initialized"
        self.last_risk = "SAFE"
        self.active_thought = "Listening on terminal input channels."
        self.frame_index = 0
        self.affinity_score = 1.0
        self.master_name = "Master"

        # Telemetry historical tracker
        self._last_net = psutil.net_io_counters()
        self._last_net_time = time.time()

    def set_state(
        self,
        state: str,
        action: str = "",
        risk: str = "SAFE",
        cat_state: Optional[CatState] = None,
        thought: str = "",
    ) -> None:
        """Updates agent operational and emotional status."""
        self.agent_state = state
        if action:
            self.last_action = action
        self.last_risk = risk
        if thought:
            self.active_thought = thought

        if cat_state:
            self.cat_state = cat_state
        elif "EXEC" in state.upper():
            self.cat_state = CatState.EXECUTING
        elif "THINK" in state.upper() or "REASON" in state.upper():
            self.cat_state = CatState.THINKING
        elif "BLOCK" in state.upper() or risk in ("CRITICAL", "BLOCKED"):
            self.cat_state = CatState.HISSING
        elif "PURR" in state.upper() or "SUCCESS" in state.upper():
            self.cat_state = CatState.PURRING
        elif "ALERT" in state.upper() or "MFA" in state.upper():
            self.cat_state = CatState.ALERT
        else:
            self.cat_state = CatState.IDLE

    def _render_header(self) -> Panel:
        t = self.theme
        frame_text = avatar_animator.get_frame(
            self.cat_state, frame_index=self.frame_index, theme=t
        )
        avatar = Text.from_markup(frame_text)

        # Feline mood
        mood = CatMoodEngine.evaluate_mood(
            state=self.cat_state,
            affinity_score=self.affinity_score,
            cpu_load=psutil.cpu_percent(),
            had_blocked_threat=(self.cat_state == CatState.HISSING),
        )
        feline_quip = CatMoodEngine.get_feline_quip(mood, master_name=self.master_name)

        grid = Table.grid(expand=True)
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)

        import platform

        node_name = platform.node()
        kernel_rel = platform.release()
        sess_name = (
            "WINDOWS"
            if sys.platform == "win32"
            else os.environ.get("XDG_SESSION_TYPE", "wayland").upper()
        )
        sys_info = (
            f"[bold {t.neon_primary}]Host:[/] {node_name}  "
            f"[bold {t.neon_secondary}]Kernel:[/] {kernel_rel}\n"
            f"[bold {t.neon_primary}]Session:[/] {sess_name}  "
            f"[bold {t.accent_amber}]Guardrail Risk Floor:[/] {Risk(settings.auto_approve_max_risk).name}\n"
            f"[bold {t.neon_primary}]Agent State:[/] [{t.accent_amber} blink]{self.agent_state}[/]\n"
            f"[bold {t.neon_secondary}]Active Action:[/] {self.last_action[:45]}\n"
            f"[dim {t.dim_text}]{feline_quip}[/]"
        )

        grid.add_row(
            avatar,
            Panel(
                sys_info,
                border_style=t.neon_secondary,
                box=ROUNDED,
                title=f"[{t.neon_primary}]Core Matrix : {t.display_name}[/]",
            ),
        )
        return Panel(
            grid,
            border_style=t.neon_primary,
            box=ROUNDED,
            title=f"[bold {t.neon_secondary}]✦ FIREFLY MINI CYBER-HUD ✦[/]",
        )

    def _render_system_metrics(self) -> Panel:
        t = self.theme
        snapshot = telemetry_engine.sample()
        cpu_sparkline = telemetry_engine.get_cpu_sparkline(width=14)
        mem_sparkline = telemetry_engine.get_mem_sparkline(width=14)
        rx_sparkline = telemetry_engine.get_net_rx_sparkline(width=10)

        table = Table(expand=True, box=ROUNDED, border_style=t.border_color)
        table.add_column("Subsystem", style=f"bold {t.neon_primary}", width=12)
        table.add_column("Meter", ratio=2)
        table.add_column("History", style=f"bold {t.neon_secondary}", width=16)

        table.add_row(
            "󰻠 CPU Cores",
            render_gauge_bar(snapshot.cpu_percent, length=12, theme=t),
            f"[{t.neon_primary}]{cpu_sparkline}[/]",
        )
        table.add_row(
            "󰍛 Memory",
            render_gauge_bar(snapshot.memory_percent, length=12, theme=t),
            f"[{t.neon_secondary}]{mem_sparkline}[/]",
        )
        table.add_row(
            "󰋊 Root FS",
            render_gauge_bar(snapshot.disk_percent, length=12, theme=t),
            f"[{t.dim_text}]{snapshot.disk_free_gb}GB Free[/]",
        )
        table.add_row(
            "󰌘 Network",
            f"[{t.success_green}]▼ {snapshot.net_rx_kbs:.1f} KB/s[/] [{t.accent_amber}]▲ {snapshot.net_tx_kbs:.1f} KB/s[/]",
            f"[{t.success_green}]{rx_sparkline}[/]",
        )

        return Panel(
            table,
            border_style=t.neon_secondary,
            box=ROUNDED,
            title=f"[{t.accent_amber}]Subsystem Telemetry[/]",
        )

    def _render_guardrail_matrix(self) -> Panel:
        t = self.theme
        table = Table(expand=True, box=ROUNDED, border_style=t.border_color)
        table.add_column("Defense Module", style=f"bold {t.neon_primary}")
        table.add_column("Security Status", style="bold")

        table.add_row("Hard Blocklist", f"[{t.success_green}]ARMED & UNBYPASSABLE[/]")
        table.add_row(
            "Auto-Approve Floor",
            f"[{t.accent_amber}]Risk <= {Risk(settings.auto_approve_max_risk).name}[/]",
        )
        table.add_row("MFA / TOTP Challenge", f"[{t.neon_secondary}]ACTIVE (6-char & OTP)[/]")
        table.add_row("Blast Radius Sandbox", f"[{t.neon_primary}]MONITORED (<50 files dry-run)[/]")
        table.add_row(
            "Kill-Switch Daemon",
            f"[{t.success_green}]STANDBY (~/.local/share/firefly-mini/STOP)[/]",
        )

        return Panel(
            table,
            border_style=t.neon_primary,
            box=ROUNDED,
            title=f"[{t.neon_secondary}]Guardrail & Defense Matrix[/]",
        )

    def _render_audit_log(self) -> Panel:
        t = self.theme
        records = logger.get_recent(limit=5)
        table = Table(expand=True, box=ROUNDED, border_style=t.border_color)
        table.add_column("Time", style="dim", width=8)
        table.add_column("Kind", width=7)
        table.add_column("Action", ratio=1)
        table.add_column("Risk", width=8)
        table.add_column("Status", width=10)

        for rec in reversed(records):
            t_str = time.strftime("%H:%M:%S", time.localtime(rec.timestamp))
            risk_color = (
                t.success_green
                if rec.risk_level in ("SAFE", "LOW")
                else (t.accent_amber if rec.risk_level == "MEDIUM" else t.danger_red)
            )
            status_str = (
                f"[{t.success_green}]APPROVED[/]"
                if rec.approved
                else f"[{t.danger_red}]REJECTED[/]"
            )

            table.add_row(
                t_str,
                f"[{t.neon_primary}]{rec.kind}[/]",
                rec.action[:40],
                f"[{risk_color}]{rec.risk_level}[/]",
                status_str,
            )

        if not records:
            table.add_row(
                "--:--:--",
                "INIT",
                "Audit trail initialized and armed",
                "SAFE",
                f"[{t.success_green}]ONLINE[/]",
            )

        return Panel(
            table,
            border_style=t.neon_primary,
            box=ROUNDED,
            title=f"[{t.neon_secondary}]Encrypted Audit Trail[/]",
        )

    def _render_reasoning_stream(self) -> Panel:
        t = self.theme
        content = (
            f"[bold {t.neon_primary}]Current Thought Protocol:[/]\n"
            f"[{t.fg_text}]{self.active_thought}[/]\n\n"
            f"[bold {t.accent_amber}]Active Step Action:[/] [{t.neon_secondary}]{self.last_action}[/]\n"
            f"[bold {t.neon_primary}]Security Clearance:[/] [{t.success_green}]{self.last_risk}[/]"
        )
        return Panel(
            content,
            border_style=t.neon_secondary,
            box=ROUNDED,
            title=f"[{t.accent_amber}]Agent Reasoning Stream[/]",
        )

    def get_layout(self) -> Layout:
        """Constructs responsive split-dashboard layout."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=9),
            Layout(name="body", ratio=1),
        )
        layout["body"].split_row(
            Layout(name="left_col", ratio=1),
            Layout(name="right_col", ratio=1),
        )
        layout["left_col"].split_column(
            Layout(name="metrics", ratio=1),
            Layout(name="defense", ratio=1),
        )
        layout["right_col"].split_column(
            Layout(name="reasoning", size=7),
            Layout(name="audit", ratio=1),
        )

        layout["header"].update(self._render_header())
        layout["metrics"].update(self._render_system_metrics())
        layout["defense"].update(self._render_guardrail_matrix())
        layout["reasoning"].update(self._render_reasoning_stream())
        layout["audit"].update(self._render_audit_log())
        return layout

    def display_once(self) -> None:
        self.console.print(self.get_layout())

    def run_live(self, duration_sec: Optional[float] = None) -> None:
        """Starts live terminal HUD loop with animated avatar frames."""
        start = time.time()
        with Live(
            self.get_layout(), console=self.console, refresh_per_second=2, screen=False
        ) as live:
            try:
                while True:
                    self.frame_index = (self.frame_index + 1) % 4
                    live.update(self.get_layout())
                    time.sleep(0.5)
                    if duration_sec and (time.time() - start) > duration_sec:
                        break
            except KeyboardInterrupt:
                pass

    # -------------------------------------------------------------------------
    # Feature 72: Interactive TUI Command Palette
    # -------------------------------------------------------------------------
    def render_command_palette(self) -> Panel:
        """Renders interactive quick actions menu palette."""
        t = self.theme
        table = Table(expand=True, box=ROUNDED, border_style=t.border_color)
        table.add_column("Key", style=f"bold {t.neon_primary}", width=6)
        table.add_column("Command Action", style=f"bold {t.fg_text}")
        table.add_column("Description", style=t.dim_text)

        actions = [
            ("1", "Status Telemetry", "Inspect real-time CPU, RAM, and Disk metrics"),
            (
                "2",
                "Self-Healing Doctor",
                "Run diagnostic self-repair check on packages and configs",
            ),
            ("3", "Switch Theme", "Toggle between Tokyo-Night, Catppuccin, and Cyber-Matrix"),
            ("4", "Adaptive Memory", "List and search semantic memories and user habits"),
            ("5", "Kill Switch", "Engage emergency lock on all terminal actions"),
            ("Q", "Exit Menu", "Return to main terminal interface"),
        ]

        for key, name, desc in actions:
            table.add_row(f"[{t.accent_amber}][{key}][/]", name, desc)

        return Panel(
            table,
            title=f"[bold {t.neon_primary}]✦ FIREFLY COMMAND PALETTE ✦[/]",
            border_style=t.neon_secondary,
            box=ROUNDED,
        )

    # -------------------------------------------------------------------------
    # Feature 71: Live Log Viewer
    # -------------------------------------------------------------------------
    def view_live_logs(self, limit: int = 15) -> Panel:
        """Renders formatted decrypted log feed with secret scrubbing."""
        t = self.theme
        records = logger.get_recent(limit=limit)
        table = Table(expand=True, box=ROUNDED, border_style=t.border_color)
        table.add_column("Timestamp", style="dim", width=10)
        table.add_column("Kind", width=8)
        table.add_column("Command Action", ratio=2)
        table.add_column("Risk", width=8)
        table.add_column("Output Summary", ratio=2)

        for rec in reversed(records):
            t_str = time.strftime("%H:%M:%S", time.localtime(rec.timestamp))
            risk_color = (
                t.success_green
                if rec.risk_level in ("SAFE", "LOW")
                else (t.accent_amber if rec.risk_level == "MEDIUM" else t.danger_red)
            )
            out_summary = rec.output_summary or "None"
            table.add_row(
                t_str,
                f"[{t.neon_primary}]{rec.kind}[/]",
                rec.action,
                f"[{risk_color}]{rec.risk_level}[/]",
                f"[{t.dim_text}]{out_summary[:45]}[/]",
            )

        return Panel(
            table,
            title=f"[bold {t.neon_primary}]✦ Live Encrypted Security Audit Stream ✦[/]",
            border_style=t.neon_secondary,
            box=ROUNDED,
        )

    # -------------------------------------------------------------------------
    # Feature 80: EventBus UI Sync
    # -------------------------------------------------------------------------
    def attach_to_event_bus(self, bus: EventBus) -> None:
        """Subscribes to EventBus topics to drive real-time HUD state transitions."""

        def on_turn_start(event: Event) -> None:
            self.set_state(
                "REASONING (TACTICAL PLAN)",
                cat_state=CatState.THINKING,
                thought=str(event.data.get("query", "")),
            )

        def on_tool_exec(event: Event) -> None:
            tool_name = str(event.data.get("name", "tool"))
            self.set_state(
                f"EXECUTING [{tool_name}]", action=tool_name, cat_state=CatState.EXECUTING
            )

        def on_tool_fin(event: Event) -> None:
            tool_name = str(event.data.get("name", "tool"))
            self.set_state(
                "IDLE (ONLINE)", action=f"Finished {tool_name}", cat_state=CatState.PURRING
            )

        def on_block(event: Event) -> None:
            cmd = str(event.data.get("command", "threat"))
            self.set_state(
                "DEFENSE SHIELD ENGAGED", action=cmd, risk="BLOCKED", cat_state=CatState.HISSING
            )

        bus.subscribe("agent.turn_started", on_turn_start)
        bus.subscribe("tool.executing", on_tool_exec)
        bus.subscribe("tool.finished", on_tool_fin)
        bus.subscribe("guardrail.blocked", on_block)


hud = TerminalHUD()
default_hud = hud
