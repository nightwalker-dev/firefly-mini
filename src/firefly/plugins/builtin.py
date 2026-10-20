"""Built-in core tools registered through the @tool plugin system."""

from __future__ import annotations

import json
from typing import Any, List

from pydantic import BaseModel, Field

from firefly.agent.tool_registry import tool
from firefly.core.container import default_container
from firefly.display.base import get_display_backend
from firefly.input.vision_ground import VisionGrounder
from firefly.system.bash_executor import BashExecutor
from firefly.system.themer import themer
from firefly.voice.speaker import speaker


# --- Argument Schemas ---
class BashRunArgs(BaseModel):
    command: str = Field(description="The shell command to execute safely inside the sandbox")


class MouseMoveArgs(BaseModel):
    x: int = Field(description="X pixel coordinate")
    y: int = Field(description="Y pixel coordinate")


class MouseClickArgs(BaseModel):
    button: str = Field(default="left", description="'left', 'right', or 'middle'")
    double: bool = Field(default=False, description="Whether to double-click")


class TypeTextArgs(BaseModel):
    text: str = Field(description="The text to type")


class PressHotkeyArgs(BaseModel):
    keys: List[str] = Field(description="List of key names, e.g. ['ctrl', 'c']")


class LocateUIArgs(BaseModel):
    query: str = Field(description="Description of visual target element on screen")


class SpeakVoiceArgs(BaseModel):
    text: str = Field(description="Text to synthesize via TTS")
    sound_effect: str = Field(default="chirp", description="'chirp', 'purr', 'alert', or 'beep'")


class ApplyThemeArgs(BaseModel):
    component: str = Field(
        default="all", description="'all', 'wallpaper', 'kitty', 'alacritty', or 'prompt'"
    )


class EmptyArgs(BaseModel):
    pass


# --- Tool Implementations ---
@tool(
    name="bash_run",
    description="Execute a bash command safely inside the guardrail sandbox",
    args_schema=BashRunArgs,
)
def bash_run_tool(command: str) -> str:
    executor = default_container.resolve_optional(BashExecutor) or BashExecutor()
    res = executor.run(command)
    return json.dumps(
        {
            "exit_code": res.exit_code,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "approved": res.approved,
            "checkpoint_id": res.checkpoint_id,
        }
    )


@tool(
    name="mouse_move",
    description="Move mouse cursor to coordinates (x, y)",
    args_schema=MouseMoveArgs,
)
def mouse_move_tool(x: int, y: int) -> str:
    display = get_display_backend()
    res = display.move_mouse(x, y)
    return json.dumps({"success": res.unwrap_or(False), "x": x, "y": y})


@tool(
    name="mouse_click",
    description="Click mouse button at current position",
    args_schema=MouseClickArgs,
)
def mouse_click_tool(button: str = "left", double: bool = False) -> str:
    display = get_display_backend()
    res = display.click(button=button, double=double)
    return json.dumps({"success": res.unwrap_or(False)})


@tool(name="type_text", description="Type text into the active window", args_schema=TypeTextArgs)
def type_text_tool(text: str) -> str:
    display = get_display_backend()
    res = display.type_text(text)
    return json.dumps({"success": res.unwrap_or(False)})


@tool(name="press_hotkey", description="Press a hotkey combination", args_schema=PressHotkeyArgs)
def press_hotkey_tool(keys: List[str]) -> str:
    display = get_display_backend()
    res = display.press_hotkey(keys)
    return json.dumps({"success": res.unwrap_or(False)})


@tool(name="capture_screen", description="Capture screenshot of display", args_schema=EmptyArgs)
def capture_screen_tool() -> str:
    vg = VisionGrounder()
    out = vg.capture_screen()
    if out:
        return json.dumps({"success": True, "path": str(out)})
    return json.dumps({"success": False, "error": "Display capture unavailable"})


@tool(
    name="locate_ui_element",
    description="Find UI element coordinates on screen using VLM",
    args_schema=LocateUIArgs,
)
async def locate_ui_element_tool(query: str) -> str:
    vg = VisionGrounder()
    target = await vg.locate_element(query)
    if target:
        return json.dumps(
            {
                "found": True,
                "x": target.x,
                "y": target.y,
                "confidence": target.confidence,
                "description": target.description,
            }
        )
    return json.dumps({"found": False})


@tool(
    name="speak_voice",
    description="Play feline sound effect and speak text",
    args_schema=SpeakVoiceArgs,
)
def speak_voice_tool(text: str, sound_effect: str = "chirp") -> str:
    getattr(speaker, sound_effect, speaker.chirp)()
    speaker.speak(text)
    return json.dumps({"spoken": text})


@tool(
    name="apply_theme",
    description="Generate and apply cyberpunk cat wallpaper and terminal themes",
    args_schema=ApplyThemeArgs,
)
def apply_theme_tool(component: str = "all") -> str:
    out_info: dict[str, Any] = {}
    if component in ("all", "wallpaper"):
        w_path = themer.generate_cyber_cat_wallpaper()
        applied = themer.set_wallpaper(w_path)
        out_info["wallpaper"] = {"path": str(w_path), "applied": applied}
    if component in ("all", "kitty"):
        k_path = themer.export_kitty_theme()
        out_info["kitty"] = str(k_path)
    if component in ("all", "alacritty"):
        a_path = themer.export_alacritty_theme()
        out_info["alacritty"] = str(a_path)
    if component in ("all", "prompt"):
        p_path = themer.export_shell_prompt()
        out_info["prompt"] = str(p_path)
    speaker.purr()
    return json.dumps(out_info)


@tool(name="system_status", description="Query host telemetry", args_schema=EmptyArgs)
def system_status_tool() -> str:
    import platform

    import psutil

    from firefly.core.platform import root_path

    try:
        disk_free = psutil.disk_usage(str(root_path())).free // (1024**3)
    except Exception:
        disk_free = 0

    return json.dumps(
        {
            "os": platform.system(),
            "release": platform.release(),
            "cpu_percent": psutil.cpu_percent(),
            "mem_percent": psutil.virtual_memory().percent,
            "disk_free_gb": disk_free,
        }
    )
