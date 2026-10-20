"""Comprehensive test suite for Phase 4: Visual Appeal & Anime Cyberpunk HUD (Features 56-80)."""

from PIL import Image
from typer.testing import CliRunner

from firefly.cli import app
from firefly.core.events import Event, EventBus
from firefly.system.themer import DesktopThemer
from firefly.ui.avatar import (
    CatAvatarAnimator,
    CatMood,
    CatMoodEngine,
    CatState,
)
from firefly.ui.desktop import DesktopIntegrationManager
from firefly.ui.formatter import OutputFormatter
from firefly.ui.hud import TerminalHUD
from firefly.ui.telemetry import TelemetryHistory, render_gauge_bar, render_sparkline
from firefly.ui.themes import ContrastVerifier, ThemeManager
from firefly.ui.vision_overlay import VisionOverlayAnnotator
from firefly.ui.widgets import (
    render_glitch_text,
    render_gradient_banner,
    render_neon_progress,
    render_paw_breadcrumbs,
    render_ports_table,
    render_process_tree,
    render_unified_diff,
)


# ==============================================================================
# Feature 56: Multi-Frame Animated Cyber-Cat Avatar
# ==============================================================================
def test_cat_avatar_frames_and_states():
    animator = CatAvatarAnimator()
    for state in CatState:
        total = animator.get_total_frames(state)
        assert total >= 1
        frame0 = animator.get_frame(state, frame_index=0)
        assert "FIREFLY MINI" in frame0
        # Ensure frame indexing wraps correctly
        frame_next = animator.get_frame(state, frame_index=total)
        assert frame_next == frame0


# ==============================================================================
# Feature 57: Dynamic Mood & Expression Matrix
# ==============================================================================
def test_cat_mood_matrix():
    # Threat blocked -> suspicious
    mood_threat = CatMoodEngine.evaluate_mood(CatState.HISSING, had_blocked_threat=True)
    assert mood_threat == CatMood.SUSPICIOUS
    assert "Threat signature" in CatMoodEngine.get_feline_quip(mood_threat)

    # Execution error -> annoyed
    mood_err = CatMoodEngine.evaluate_mood(CatState.IDLE, had_recent_error=True)
    assert mood_err == CatMood.ANNOYED
    assert "glitch in the matrix" in CatMoodEngine.get_feline_quip(mood_err)

    # High affinity purr -> excited
    mood_purr = CatMoodEngine.evaluate_mood(CatState.PURRING, affinity_score=4.5)
    assert mood_purr == CatMood.EXCITED

    # Low CPU idle -> sleepy
    mood_sleep = CatMoodEngine.evaluate_mood(CatState.SLEEPING)
    assert mood_sleep == CatMood.SLEEPY


# ==============================================================================
# Feature 58: Holographic Color Themes Engine
# ==============================================================================
def test_theme_manager():
    mgr = ThemeManager()
    assert mgr.current.name == "tokyo-night"

    assert mgr.set_theme("catppuccin-mocha") is True
    assert mgr.current.name == "catppuccin-mocha"
    assert mgr.current.neon_primary == "#89DCEB"

    assert mgr.set_theme("cyber-matrix") is True
    assert mgr.current.neon_primary == "#00FF66"

    assert mgr.set_theme("nonexistent") is False
    assert len(mgr.list_themes()) == 5


# ==============================================================================
# Feature 78: Color Contrast & A11y Verification (WCAG 2.1)
# ==============================================================================
def test_wcag_contrast_verifier():
    # Black on White: ~21:1
    bw_ratio = ContrastVerifier.calculate_contrast_ratio("#000000", "#FFFFFF")
    assert bw_ratio > 20.0
    assert ContrastVerifier.meets_wcag_aa("#000000", "#FFFFFF") is True

    # Same colors: 1:1 (fails WCAG)
    assert ContrastVerifier.meets_wcag_aa("#888888", "#888888") is False

    # Check all preset themes meet WCAG AA contrast (>= 4.5:1)
    mgr = ThemeManager()
    audit = mgr.verify_all_themes_a11y()
    for theme_name, passes in audit.items():
        assert passes is True, f"Theme {theme_name} failed WCAG AA contrast"


# ==============================================================================
# Feature 59 & 60: System Telemetry & Sparklines
# ==============================================================================
def test_telemetry_and_sparklines():
    # Sparkline rendering
    line = render_sparkline([0.0, 20.0, 50.0, 80.0, 100.0], width=5)
    assert len(line) == 5
    assert line[0] == " "
    assert line[-1] == "█"

    # Gauge bar
    bar = render_gauge_bar(50.0, length=10)
    assert "50.0%" in bar
    assert "█" in bar

    # Rolling history
    history = TelemetryHistory(max_points=5)
    snapshot = history.sample()
    assert snapshot.cpu_percent >= 0.0
    assert snapshot.memory_percent >= 0.0
    assert len(history.get_cpu_sparkline(width=5)) == 5


# ==============================================================================
# Feature 61, 70, 73, 74, 76, 77: Widgets, Trees, and Text Effects
# ==============================================================================
def test_ui_widgets():
    # Neon progress
    prog = render_neon_progress(current=3, total=6, label="Compiling")
    assert "Compiling" in prog
    assert "3/6" in prog
    assert "50%" in prog

    # Paw breadcrumbs
    crumbs = render_paw_breadcrumbs(["Plan", "Execute", "Verify"], current_index=1)
    assert "🐾 Plan" in crumbs
    assert "🐾 Execute" in crumbs
    assert "➔" in crumbs

    # Glitch text
    glitched = render_glitch_text("Cyber Defense Matrix", intensity=0.5)
    assert len(glitched) > 0

    # Gradient banner
    banner = render_gradient_banner(["FIREFLY MINI", "CYBER DEFENSE"])
    assert banner is not None

    # Unified diff
    diff_panel = render_unified_diff("line1\nold_line\nline3", "line1\nnew_line\nline3")
    assert diff_panel is not None

    # Process tree & ports table
    ptree = render_process_tree(limit=3)
    assert ptree is not None
    ports = render_ports_table(limit=3)
    assert ports is not None


# ==============================================================================
# Feature 69: Syntax-Highlighted Output Formatter with Secret Redaction
# ==============================================================================
def test_output_formatter():
    formatter = OutputFormatter()

    # Detect JSON
    json_text = '{"status": "ok", "token": "ghp_123456789012345678901234567890123456"}'
    panel = formatter.format_output(json_text, title="API Response")
    assert panel is not None
    # Secret must be redacted!
    content = getattr(
        panel.renderable, "code", getattr(panel.renderable, "plain", str(panel.renderable))
    )
    assert "ghp_1234567890" not in content
    assert "[REDACTED_API_TOKEN]" in content

    # Line truncation
    long_text = "\n".join([f"line {i}" for i in range(100)])
    truncated_panel = formatter.format_output(long_text, max_lines=10)
    trunc_content = getattr(
        truncated_panel.renderable,
        "code",
        getattr(truncated_panel.renderable, "plain", str(truncated_panel.renderable)),
    )
    assert "truncated" in trunc_content


# ==============================================================================
# Feature 75: Screen Annotation and Vision Overlay
# ==============================================================================
def test_vision_overlay_annotator(tmp_path):
    img_path = tmp_path / "desktop.png"
    img = Image.new("RGB", (640, 480), color=(30, 30, 40))
    img.save(img_path)

    annotator = VisionOverlayAnnotator()
    out_annotated = annotator.annotate_screenshot(
        image_path=img_path,
        bounding_boxes=[(50, 50, 200, 150, "Terminal")],
        click_targets=[(120, 100, "Click Button")],
    )

    assert out_annotated.exists()
    assert out_annotated.stat().st_size > 1000


# ==============================================================================
# Features 62, 63, 64, 65, 66, 67: Desktop Themer & Exporters
# ==============================================================================
def test_desktop_themer_and_exporters(tmp_path):
    themer = DesktopThemer(config_dir=tmp_path / "config")

    # Wallpaper generation
    wp = themer.generate_cyber_cat_wallpaper(output_path=tmp_path / "wp.png", width=640, height=360)
    assert wp.exists()

    # Config exporters
    wz = themer.export_wezterm_theme(out_path=tmp_path / "wezterm.lua")
    assert wz.exists()
    assert "Firefly Mini" in wz.read_text()

    gh = themer.export_ghostty_theme(out_path=tmp_path / "ghostty.config")
    assert gh.exists()

    ft = themer.export_foot_theme(out_path=tmp_path / "foot.ini")
    assert ft.exists()

    st = themer.export_starship_preset(out_path=tmp_path / "starship.toml")
    assert st.exists()
    assert "(=^･ω･^=)" in st.read_text()

    # Desktop notification dispatcher
    desk_mgr = DesktopIntegrationManager()
    ok = desk_mgr.send_notification("Test Alert", "Verification message", play_sound=False)
    assert ok is True


# ==============================================================================
# Feature 59, 71, 72: Multi-Panel Terminal HUD & Command Palette
# ==============================================================================
def test_terminal_hud_panels():
    hud = TerminalHUD()
    hud.set_state("REASONING (TACTICAL PLAN)", action="Analyze memory", cat_state=CatState.THINKING)
    assert hud.cat_state == CatState.THINKING

    layout = hud.get_layout()
    assert layout is not None

    palette = hud.render_command_palette()
    assert "FIREFLY COMMAND PALETTE" in str(palette.title)

    logs = hud.view_live_logs(limit=5)
    assert "Live Encrypted Security Audit Stream" in str(logs.title)


# ==============================================================================
# Feature 80: EventBus UI Synchronization
# ==============================================================================
def test_event_bus_hud_sync():
    bus = EventBus()
    hud = TerminalHUD()
    hud.attach_to_event_bus(bus)

    # 1. Turn started -> Thinking
    bus.publish_sync(Event(topic="agent.turn_started", data={"query": "List files"}))
    assert hud.cat_state == CatState.THINKING
    assert "List files" in hud.active_thought

    # 2. Tool executing -> Executing
    bus.publish_sync(Event(topic="tool.executing", data={"name": "bash_tool"}))
    assert hud.cat_state == CatState.EXECUTING
    assert hud.last_action == "bash_tool"

    # 3. Tool finished -> Purring
    bus.publish_sync(Event(topic="tool.finished", data={"name": "bash_tool"}))
    assert hud.cat_state == CatState.PURRING

    # 4. Threat blocked -> Hissing
    bus.publish_sync(Event(topic="guardrail.blocked", data={"command": "rm -rf /"}))
    assert hud.cat_state == CatState.HISSING
    assert hud.last_risk == "BLOCKED"


# ==============================================================================
# Feature 79: CLI Commands for Themes and HUD
# ==============================================================================
def test_theme_and_hud_cli():
    runner = CliRunner()

    # Theme list
    res_list = runner.invoke(app, ["theme", "list"])
    assert res_list.exit_code == 0
    assert "tokyo-night" in res_list.stdout

    # Theme set
    res_set = runner.invoke(app, ["theme", "set", "cyber-matrix"])
    assert res_set.exit_code == 0
    assert "Activated theme" in res_set.stdout

    # Theme A11y
    res_a11y = runner.invoke(app, ["theme", "a11y"])
    assert res_a11y.exit_code == 0
    assert "PASS" in res_a11y.stdout

    # Theme export
    res_exp = runner.invoke(app, ["theme", "export", "ghostty"])
    assert res_exp.exit_code == 0
    assert "Exported ghostty" in res_exp.stdout

    # HUD snapshot
    res_hud = runner.invoke(app, ["hud", "--once"])
    assert res_hud.exit_code == 0
    assert "FIREFLY MINI CYBER-HUD" in res_hud.stdout
