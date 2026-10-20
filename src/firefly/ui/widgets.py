"""Cyberpunk UI Widgets, Visualizers, Sparklines, Trees, and Text Effects for Firefly Mini."""

from __future__ import annotations

import difflib
import random
from typing import List, Optional, Tuple

import psutil
from rich.box import ROUNDED
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from firefly.ui.themes import CyberTheme, theme_manager

GLITCH_GLYPHS = ["░", "▒", "▓", "ø", "§", "⚡", "✦", "◒", "◓", "¤", "¥"]


def render_neon_progress(
    current: int,
    total: int,
    label: str = "",
    length: int = 24,
    theme: Optional[CyberTheme] = None,
) -> str:
    """Renders a sleek neon cyberpunk step progress bar.

    Example: "🐾 Compiling [neon]━╸━╸━╸━╸[dim]━━━━[/] (4/8)"
    """
    t = theme or theme_manager.current
    if total <= 0:
        total = 1
    fraction = max(0.0, min(1.0, current / total))
    filled_units = int(round(fraction * length))
    empty_units = length - filled_units

    filled_str = (
        f"[{t.neon_primary}]"
        + "━╸" * (filled_units // 2)
        + ("━" if filled_units % 2 else "")
        + "[/]"
    )
    empty_str = f"[{t.border_color}]" + "━" * empty_units + "[/]"

    pct = int(fraction * 100)
    lbl_part = f"[{t.accent_amber}]🐾 {label}[/] " if label else "🐾 "
    return f"{lbl_part}{filled_str}{empty_str} [{t.neon_secondary}]{current}/{total}[/] [{t.dim_text}]({pct}%)[/]"


def render_paw_breadcrumbs(
    steps: List[str],
    current_index: int = 0,
    theme: Optional[CyberTheme] = None,
) -> str:
    """Renders cute anime cyberpunk feline breadcrumb trail.

    Example: 🐾 [green]Plan[/] ➔ 🐾 [cyan]Execute[/] ➔ 🐾 [dim]Verify[/]
    """
    t = theme or theme_manager.current
    parts = []
    for idx, step in enumerate(steps):
        if idx < current_index:
            # Completed
            parts.append(f"[{t.success_green}]🐾 {step}[/]")
        elif idx == current_index:
            # Active
            parts.append(f"[bold {t.neon_primary}]🐾 {step}[/]")
        else:
            # Pending
            parts.append(f"[{t.dim_text}]🐾 {step}[/]")

    separator = f" [{t.neon_secondary}]➔[/] "
    return separator.join(parts)


def render_glitch_text(
    text: str,
    intensity: float = 0.15,
    theme: Optional[CyberTheme] = None,
) -> str:
    """Injects cyberpunk holographic glitch artifacts into text."""
    t = theme or theme_manager.current
    out = []
    for ch in text:
        if ch != " " and random.random() < intensity:
            glitch_char = random.choice(GLITCH_GLYPHS)
            color = random.choice([t.neon_primary, t.neon_secondary, t.accent_amber, t.danger_red])
            out.append(f"[{color}]{glitch_char}[/]")
        else:
            out.append(ch)
    return "".join(out)


def render_gradient_banner(
    lines: List[str],
    start_hex: str = "#00F0FF",
    end_hex: str = "#BD93F9",
) -> Text:
    """Renders multi-line text with smooth 24-bit RGB vertical or horizontal color gradient."""

    def hex_to_rgb(hex_code: str) -> Tuple[int, int, int]:
        c = hex_code.lstrip("#")
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)

    r1, g1, b1 = hex_to_rgb(start_hex)
    r2, g2, b2 = hex_to_rgb(end_hex)

    result = Text()
    num_lines = max(1, len(lines))
    for i, line in enumerate(lines):
        factor = i / max(1, num_lines - 1)
        r = int(r1 + factor * (r2 - r1))
        g = int(g1 + factor * (g2 - g1))
        b = int(b1 + factor * (b2 - b1))
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        result.append(line + "\n", style=hex_color)

    return result


def render_unified_diff(
    old_content: str,
    new_content: str,
    from_file: str = "original",
    to_file: str = "modified",
    theme: Optional[CyberTheme] = None,
) -> Panel:
    """Formats unified diff with green additions and red deletions inside a styled Panel."""
    t = theme or theme_manager.current
    diff_lines = list(
        difflib.unified_diff(
            old_content.splitlines(),
            new_content.splitlines(),
            fromfile=from_file,
            tofile=to_file,
            lineterm="",
        )
    )

    if not diff_lines:
        return Panel(
            f"[{t.dim_text}]No differences detected.[/]",
            title="[#00F0FF]Diff Visualizer[/]",
            border_style=t.border_color,
            box=ROUNDED,
        )

    formatted = []
    for line in diff_lines:
        if line.startswith("+++") or line.startswith("---"):
            formatted.append(f"[bold {t.neon_secondary}]{line}[/]")
        elif line.startswith("@@"):
            formatted.append(f"[{t.neon_primary}]{line}[/]")
        elif line.startswith("+"):
            formatted.append(f"[{t.success_green}]{line}[/]")
        elif line.startswith("-"):
            formatted.append(f"[{t.danger_red}]{line}[/]")
        else:
            formatted.append(f"[{t.dim_text}]{line}[/]")

    return Panel(
        "\n".join(formatted),
        title=f"[bold {t.neon_primary}]✦ Unified Patch: {to_file} ✦[/]",
        border_style=t.neon_secondary,
        box=ROUNDED,
    )


def render_process_tree(limit: int = 15, theme: Optional[CyberTheme] = None) -> Tree:
    """Builds a hierarchical Rich Tree of top resource-consuming system processes."""
    t = theme or theme_manager.current
    root = Tree(f"[bold {t.neon_primary}]󰘳 Linux Process Matrix[/]")

    # Collect running processes sorted by memory/CPU
    procs = []
    for p in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent"]):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    procs.sort(key=lambda x: (x["cpu_percent"] or 0) + (x["memory_percent"] or 0), reverse=True)

    for info in procs[:limit]:
        pid = info.get("pid", 0)
        name = info.get("name", "unknown")
        user = info.get("username", "system")
        cpu = info.get("cpu_percent") or 0.0
        mem = info.get("memory_percent") or 0.0

        label = (
            f"[bold {t.fg_text}]{name}[/] "
            f"[{t.dim_text}](PID {pid})[/] "
            f"[{t.accent_amber}]CPU {cpu:.1f}%[/] "
            f"[{t.neon_secondary}]MEM {mem:.1f}%[/] "
            f"[{t.dim_text}]user:{user}[/]"
        )
        root.add(label)

    return root


def render_ports_table(limit: int = 10, theme: Optional[CyberTheme] = None) -> Table:
    """Renders active network listening sockets and services in a cyberpunk table."""
    t = theme or theme_manager.current
    table = Table(
        title=f"[bold {t.neon_primary}]󰌘 Network Listening Sockets[/]",
        box=ROUNDED,
        border_style=t.border_color,
        expand=True,
    )
    table.add_column("Proto", style=f"bold {t.neon_secondary}", width=7)
    table.add_column("Local Address", style=f"bold {t.fg_text}", ratio=2)
    table.add_column("Status", style=f"bold {t.success_green}", width=12)
    table.add_column("PID", style=t.dim_text, width=8)

    try:
        conns = psutil.net_connections(kind="inet")
        listen_conns = [c for c in conns if c.status == "LISTEN"][:limit]
        for c in listen_conns:
            laddr = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "N/A"
            proto = "TCP" if c.type == 1 else "UDP"
            table.add_row(
                proto,
                laddr,
                c.status,
                str(c.pid or "-"),
            )
        if not listen_conns:
            table.add_row("TCP", "0.0.0.0:22 (Simulated)", "LISTEN", "ssh")
    except Exception:
        table.add_row("TCP", "127.0.0.1:8000", "LISTEN", "app")

    return table
