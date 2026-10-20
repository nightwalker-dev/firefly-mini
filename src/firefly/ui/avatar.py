"""Multi-frame Animated Cyber-Cat Avatar and Feline Mood Matrix for Firefly Mini."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from firefly.ui.themes import CyberTheme, theme_manager


class CatState(str, Enum):
    """Execution state of the cyber-feline familiar."""

    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    PURRING = "purring"
    HISSING = "hissing"
    SLEEPING = "sleeping"
    ALERT = "alert"


class CatMood(str, Enum):
    """Emotional mood state of the cyber-feline familiar."""

    CONTENT = "content"
    EXCITED = "excited"
    FOCUSED = "focused"
    SUSPICIOUS = "suspicious"
    ANNOYED = "annoyed"
    SLEEPY = "sleepy"


# Multi-frame ASCII/Unicode Animation frames for each CatState
# Each frame contains the avatar body with Rich markup placeholders
AVATAR_FRAMES: Dict[CatState, List[str]] = {
    CatState.IDLE: [
        r"""
   /\_/\    [bold {neon_primary}]FIREFLY MINI[/]  [bold {neon_secondary}]v2.0-CYBER[/]
  ( [bold {neon_primary}]o[/].[bold {accent_amber}]o[/] )   [dim {dim_text}]Cyber-Feline Familiar : Idle[/]
   > ^ <    [bold {accent_amber}]Awaiting terminal instructions...[/]
  /  ~  \   [{neon_secondary}]Guardrails active & primed[/]
""",
        r"""
   /\_/\    [bold {neon_primary}]FIREFLY MINI[/]  [bold {neon_secondary}]v2.0-CYBER[/]
  ( [bold {dim_text}]-[/].[bold {dim_text}]-[/]+ )   [dim {dim_text}]Cyber-Feline Familiar : Blinking[/]
   > ^ <    [bold {accent_amber}]Awaiting terminal instructions...[/]
  /  ~  \   [{neon_secondary}]Tail swaying gently...[/]
""",
        r"""
   /\_/\    [bold {neon_primary}]FIREFLY MINI[/]  [bold {neon_secondary}]v2.0-CYBER[/]
  ( [bold {accent_amber}]o[/].[bold {neon_primary}]o[/] )   [dim {dim_text}]Cyber-Feline Familiar : Idle[/]
   > ω <    [bold {success_green}]All cyber systems nominal[/]
  /  ~  \   [{neon_secondary}]Sensors listening...[/]
""",
    ],
    CatState.THINKING: [
        r"""
   /\_/\    [bold {neon_secondary}]FIREFLY MINI[/]  [bold {neon_primary}]REASONING[/]
  ( [bold {neon_primary}]◎[/].[bold {accent_amber}]o[/] )   [dim {dim_text}]Synthesizing ReAct tactical plan...[/]
   > ~ <    [bold {neon_secondary}]Evaluating blast radius & sandbox[/]
  /  ~  \   [{neon_primary}]Querying memory matrix...[/]
""",
        r"""
   /\_/\    [bold {neon_secondary}]FIREFLY MINI[/]  [bold {neon_primary}]REASONING[/]
  ( [bold {accent_amber}]o[/].[bold {neon_primary}]◎[/] )   [dim {dim_text}]Computing tool permutations...[/]
   > ~ <    [bold {neon_secondary}]Heuristics active [◒ ◓ ◑ ◐][/]
  /  ~  \   [{neon_primary}]Neural pathways engaged...[/]
""",
    ],
    CatState.EXECUTING: [
        r"""
   /\_/\    [bold {success_green}]FIREFLY MINI[/]  [bold {accent_amber}]EXECUTING[/]
  ( [bold {neon_primary}]>[/].[bold {neon_primary}]<[/] )   [bold {accent_amber}]⚡ Dispatched command to sandbox[/]
   > ∇ < =* [bold {success_green}]Running tool with safety monitor[/]
  /  W  \   [{neon_primary}]Streaming telemetry pipes...[/]
""",
        r"""
   /\_/\    [bold {success_green}]FIREFLY MINI[/]  [bold {accent_amber}]EXECUTING[/]
  ( [bold {accent_amber}]>[/].[bold {accent_amber}]<[/] )*  [bold {accent_amber}]⚡ Processing subprocess stdout[/]
   > ∇ <    [bold {success_green}]Subsystem responding in realtime[/]
  /  W  \   [{neon_primary}]Audit trail encrypted & logged[/]
""",
    ],
    CatState.PURRING: [
        r"""
   /\_/\    [bold {success_green}]FIREFLY MINI[/]  [bold {neon_secondary}]PURRING[/]
  ( [bold {success_green}]^[/].[bold {success_green}]^[/] )   [bold {success_green}]*purr* Task resolved flawlessly![/]
   > ᴥ < ~  [bold {neon_primary}]Affinity bond increased! +0.05[/]
  /  ~  \ ~ [{accent_amber}]Master's system is safe and sound.[/]
""",
        r"""
   /\_/\    [bold {success_green}]FIREFLY MINI[/]  [bold {neon_secondary}]PURRING[/]
  ( [bold {neon_primary}]♥[/].[bold {neon_primary}]♥[/] )   [bold {success_green}]*soft feline chirp of contentment*[/]
   > ᴥ < ~~ [bold {neon_primary}]Optimal efficiency achieved.[/]
  /  ~  \   [{accent_amber}]Ready for the next mission![/]
""",
    ],
    CatState.HISSING: [
        r"""
   /\_/\    [bold {danger_red}]FIREFLY MINI[/]  [bold {danger_red}]ALERT : THREAT BLOCKED[/]
  ( [bold {danger_red}]◣[/]_[bold {danger_red}]◢[/] )   [bold {danger_red}]*HIIISSS!* Malicious pattern detected![/]
   > ⏝ < !  [bold {danger_red}]Guardrail shield deployed: BLOCKED[/]
  /  ▼  \ ! [{accent_amber}]Blast radius violation averted![/]
""",
        r"""
   /\_/\    [bold {danger_red}]FIREFLY MINI[/]  [bold {danger_red}]DEFENSE SHIELD ENGAGED[/]
  ( [bold {danger_red}]▼[/].[bold {danger_red}]▼[/] ) ! [bold {danger_red}]Destructive command denied![/]
   > ⏝ < !! [bold {danger_red}]Action quarantined in sandbox[/]
  /  ▼  \   [{accent_amber}]Terminal integrity 100% maintained[/]
""",
    ],
    CatState.SLEEPING: [
        r"""
   /\_/\    [dim {dim_text}]FIREFLY MINI[/]  [dim {dim_text}]STANDBY / SLEEP[/]
  ( [dim {dim_text}]-[/].[dim {dim_text}]-[/]) z  [dim {dim_text}]Low power cyber standby mode...[/]
   > . <  Z [dim {dim_text}]Monitoring background daemon...[/]
  /  _  \   [dim {dim_text}]Tap or invoke 'firefly' to awaken[/]
""",
    ],
    CatState.ALERT: [
        r"""
   /\___/\  [bold {accent_amber}]FIREFLY MINI[/]  [bold {neon_primary}]HIGH ALERT[/]
  ( [bold {neon_primary}]⊙[/].[bold {neon_primary}]⊙[/] ) ! [bold {accent_amber}]Anomalous system condition sensed![/]
   > O < !! [bold {neon_secondary}]Elevation or MFA authorization required[/]
  /  !  \   [{danger_red}]Human master confirmation needed[/]
""",
    ],
}


class CatMoodEngine:
    """Calculates feline temperament, mannerisms, and contextual dialogue."""

    @staticmethod
    def evaluate_mood(
        state: CatState,
        affinity_score: float = 1.0,
        cpu_load: float = 10.0,
        had_recent_error: bool = False,
        had_blocked_threat: bool = False,
    ) -> CatMood:
        """Determines mood based on internal status and external conditions."""
        if had_blocked_threat:
            return CatMood.SUSPICIOUS
        if had_recent_error:
            return CatMood.ANNOYED
        if state == CatState.SLEEPING or (
            state == CatState.IDLE and cpu_load < 5.0 and affinity_score < 1.2
        ):
            return CatMood.SLEEPY
        if state == CatState.PURRING or affinity_score > 3.0:
            return CatMood.EXCITED if affinity_score > 4.0 else CatMood.CONTENT
        if state in (CatState.THINKING, CatState.EXECUTING):
            return CatMood.FOCUSED
        return CatMood.CONTENT

    @staticmethod
    def get_feline_quip(mood: CatMood, master_name: str = "Master") -> str:
        """Returns personality dialogue tailored to mood."""
        quips = {
            CatMood.CONTENT: f"*purrs softly* Everything is peaceful and well-guarded, {master_name}.",
            CatMood.EXCITED: f"*tail swishes with neon sparks* Ready for high-speed terminal tasks, {master_name}!",
            CatMood.FOCUSED: "*ears swivel alertly* Locking onto system target... executing protocols.",
            CatMood.SUSPICIOUS: "*holographic claws extend slightly* Threat signature analyzed. Shield armed.",
            CatMood.ANNOYED: "*flicks tail irritably* A glitch in the matrix? Self-healing heuristics deployed.",
            CatMood.SLEEPY: "*curls around the terminal prompt* Purring in low-power standby mode... zzz.",
        }
        return quips.get(mood, f"*chirps alertly* Online and ready, {master_name}.")


class CatAvatarAnimator:
    """Renders formatted and theme-colored multi-frame cat avatar frames."""

    def __init__(self, theme: Optional[CyberTheme] = None):
        self.theme = theme or theme_manager.current

    def get_frame(
        self, state: CatState, frame_index: int = 0, theme: Optional[CyberTheme] = None
    ) -> str:
        """Returns rendered Rich markup for the avatar at the specified frame."""
        t = theme or self.theme
        frames = AVATAR_FRAMES.get(state, AVATAR_FRAMES[CatState.IDLE])
        raw_frame = frames[frame_index % len(frames)]

        # Interpolate theme colors into frame template
        return raw_frame.strip("\n").format(
            neon_primary=t.neon_primary,
            neon_secondary=t.neon_secondary,
            accent_amber=t.accent_amber,
            success_green=t.success_green,
            danger_red=t.danger_red,
            dim_text=t.dim_text,
            bg_dark=t.bg_dark,
        )

    def get_total_frames(self, state: CatState) -> int:
        return len(AVATAR_FRAMES.get(state, AVATAR_FRAMES[CatState.IDLE]))


avatar_animator = CatAvatarAnimator()
