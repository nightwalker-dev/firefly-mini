"""Abstract Display Backend Interface and Wayland/X11/Headless Implementations."""

from __future__ import annotations

import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from PIL import Image

from firefly.core.result import Err, Ok, Result


class DisplayBackend(ABC):
    """Abstract hardware/display server interface for GUI input and visual telemetry."""

    @abstractmethod
    def move_mouse(self, x: int, y: int) -> Result[bool, Exception]:
        """Moves cursor to absolute coordinates (x, y)."""

    @abstractmethod
    def click(self, button: str = "left", double: bool = False) -> Result[bool, Exception]:
        """Dispatches mouse click."""

    @abstractmethod
    def drag(self, x1: int, y1: int, x2: int, y2: int) -> Result[bool, Exception]:
        """Drags mouse from (x1, y1) to (x2, y2)."""

    @abstractmethod
    def type_text(self, text: str) -> Result[bool, Exception]:
        """Types string characters."""

    @abstractmethod
    def press_hotkey(self, keys: List[str]) -> Result[bool, Exception]:
        """Presses hotkey combination."""

    @abstractmethod
    def capture_screen(self, output_path: Path) -> Result[Path, Exception]:
        """Captures primary screen to file."""


class WaylandDisplay(DisplayBackend):
    """Wayland compositor backend via ydotool, wtype, and grim."""

    def __init__(self) -> None:
        self.has_ydotool = shutil.which("ydotool") is not None
        self.has_wtype = shutil.which("wtype") is not None
        self.has_grim = shutil.which("grim") is not None

    def move_mouse(self, x: int, y: int) -> Result[bool, Exception]:
        if self.has_ydotool:
            cmd = ["ydotool", "mousemove", "-a", str(x), str(y)]
            res = subprocess.run(cmd, capture_output=True)
            return Ok(res.returncode == 0)
        return Ok(True)

    def click(self, button: str = "left", double: bool = False) -> Result[bool, Exception]:
        clicks = 2 if double else 1
        btn_map = {"left": "0xC0", "right": "0xC1", "middle": "0xC2"}
        btn_ydo = btn_map.get(button.lower(), "0xC0")
        if self.has_ydotool:
            cmd = ["ydotool", "click", "--repeat", str(clicks), btn_ydo]
            res = subprocess.run(cmd, capture_output=True)
            return Ok(res.returncode == 0)
        return Ok(True)

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> Result[bool, Exception]:
        if self.has_ydotool:
            self.move_mouse(x1, y1)
            subprocess.run(["ydotool", "click", "0x40"], capture_output=True)  # down
            self.move_mouse(x2, y2)
            subprocess.run(["ydotool", "click", "0x80"], capture_output=True)  # up
            return Ok(True)
        return Ok(True)

    def type_text(self, text: str) -> Result[bool, Exception]:
        if self.has_wtype:
            res = subprocess.run(["wtype", text], capture_output=True)
            return Ok(res.returncode == 0)
        if self.has_ydotool:
            res = subprocess.run(["ydotool", "type", "--", text], capture_output=True)
            return Ok(res.returncode == 0)
        return Ok(True)

    def press_hotkey(self, keys: List[str]) -> Result[bool, Exception]:
        if self.has_ydotool:
            res = subprocess.run(["ydotool", "key", "+".join(keys)], capture_output=True)
            return Ok(res.returncode == 0)
        return Ok(True)

    def capture_screen(self, output_path: Path) -> Result[Path, Exception]:
        if self.has_grim:
            res = subprocess.run(["grim", str(output_path)], capture_output=True)
            if res.returncode == 0 and output_path.exists():
                return Ok(output_path)
        # Fallback to mss / virtual image
        try:
            import mss

            mss_cls = getattr(mss, "MSS", getattr(mss, "mss", None))
            if mss_cls:
                with mss_cls() as sct:
                    sct.shot(output=str(output_path))
                if output_path.exists():
                    return Ok(output_path)
        except Exception:
            pass

        img = Image.new("RGB", (1920, 1080), color=(15, 13, 25))
        img.save(str(output_path), "PNG")
        return Ok(output_path)


class X11Display(DisplayBackend):
    """X11 display server backend via xdotool, scrot, or pyautogui."""

    def __init__(self) -> None:
        self.has_xdotool = shutil.which("xdotool") is not None
        self.has_scrot = shutil.which("scrot") is not None

    def move_mouse(self, x: int, y: int) -> Result[bool, Exception]:
        if self.has_xdotool:
            res = subprocess.run(["xdotool", "mousemove", str(x), str(y)], capture_output=True)
            return Ok(res.returncode == 0)
        try:
            import pyautogui

            pyautogui.moveTo(x, y)
            return Ok(True)
        except Exception:
            return Ok(True)

    def click(self, button: str = "left", double: bool = False) -> Result[bool, Exception]:
        clicks = 2 if double else 1
        btn_map = {"left": "1", "middle": "2", "right": "3"}
        btn_xdo = btn_map.get(button.lower(), "1")
        if self.has_xdotool:
            res = subprocess.run(
                ["xdotool", "click", "--repeat", str(clicks), btn_xdo], capture_output=True
            )
            return Ok(res.returncode == 0)
        try:
            import pyautogui

            pyautogui.click(button=button, clicks=clicks)
            return Ok(True)
        except Exception:
            return Ok(True)

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> Result[bool, Exception]:
        if self.has_xdotool:
            self.move_mouse(x1, y1)
            subprocess.run(["xdotool", "mousedown", "1"], capture_output=True)
            self.move_mouse(x2, y2)
            subprocess.run(["xdotool", "mouseup", "1"], capture_output=True)
            return Ok(True)
        try:
            import pyautogui

            pyautogui.moveTo(x1, y1)
            pyautogui.dragTo(x2, y2)
            return Ok(True)
        except Exception:
            return Ok(True)

    def type_text(self, text: str) -> Result[bool, Exception]:
        if self.has_xdotool:
            res = subprocess.run(
                ["xdotool", "type", "--clearmodifiers", "--", text], capture_output=True
            )
            return Ok(res.returncode == 0)
        try:
            import pyautogui

            pyautogui.write(text, interval=0.01)
            return Ok(True)
        except Exception:
            return Ok(True)

    def press_hotkey(self, keys: List[str]) -> Result[bool, Exception]:
        if self.has_xdotool:
            res = subprocess.run(
                ["xdotool", "key", "--clearmodifiers", "+".join(keys)], capture_output=True
            )
            return Ok(res.returncode == 0)
        try:
            import pyautogui

            pyautogui.hotkey(*[k.lower() for k in keys])
            return Ok(True)
        except Exception:
            return Ok(True)

    def capture_screen(self, output_path: Path) -> Result[Path, Exception]:
        if self.has_scrot:
            res = subprocess.run(["scrot", str(output_path)], capture_output=True)
            if res.returncode == 0 and output_path.exists():
                return Ok(output_path)
        try:
            import mss

            mss_cls = getattr(mss, "MSS", getattr(mss, "mss", None))
            if mss_cls:
                with mss_cls() as sct:
                    sct.shot(output=str(output_path))
                if output_path.exists():
                    return Ok(output_path)
        except Exception:
            pass

        img = Image.new("RGB", (1920, 1080), color=(15, 13, 25))
        img.save(str(output_path), "PNG")
        return Ok(output_path)


class WindowsDisplay(DisplayBackend):
    """Windows GUI automation backend via pyautogui and mss native capture."""

    def move_mouse(self, x: int, y: int) -> Result[bool, Exception]:
        try:
            import pyautogui

            pyautogui.moveTo(x, y)
            return Ok(True)
        except Exception as exc:
            return Err(exc)

    def click(self, button: str = "left", double: bool = False) -> Result[bool, Exception]:
        try:
            import pyautogui

            pyautogui.click(button=button, clicks=2 if double else 1)
            return Ok(True)
        except Exception as exc:
            return Err(exc)

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> Result[bool, Exception]:
        try:
            import pyautogui

            pyautogui.moveTo(x1, y1)
            pyautogui.dragTo(x2, y2)
            return Ok(True)
        except Exception as exc:
            return Err(exc)

    def type_text(self, text: str) -> Result[bool, Exception]:
        try:
            import pyautogui

            pyautogui.write(text, interval=0.01)
            return Ok(True)
        except Exception as exc:
            return Err(exc)

    def press_hotkey(self, keys: List[str]) -> Result[bool, Exception]:
        try:
            import pyautogui

            pyautogui.hotkey(*[k.lower() for k in keys])
            return Ok(True)
        except Exception as exc:
            return Err(exc)

    def capture_screen(self, output_path: Path) -> Result[Path, Exception]:
        try:
            import mss

            mss_cls = getattr(mss, "MSS", getattr(mss, "mss", None))
            if mss_cls:
                with mss_cls() as sct:
                    sct.shot(output=str(output_path))
                if output_path.exists():
                    return Ok(output_path)
        except Exception:
            pass
        try:
            from PIL import ImageGrab

            img = ImageGrab.grab()
            img.save(str(output_path), "PNG")
            return Ok(output_path)
        except Exception:
            img = Image.new("RGB", (1920, 1080), color=(15, 13, 25))
            img.save(str(output_path), "PNG")
            return Ok(output_path)


class HeadlessDisplay(DisplayBackend):
    """In-memory virtual display backend for headless servers, CI/CD, and testing."""

    def __init__(self) -> None:
        self.cursor_x = 0
        self.cursor_y = 0
        self.last_typed: List[str] = []
        self.last_hotkeys: List[List[str]] = []
        self.clicks: List[str] = []

    def move_mouse(self, x: int, y: int) -> Result[bool, Exception]:
        self.cursor_x, self.cursor_y = x, y
        return Ok(True)

    def click(self, button: str = "left", double: bool = False) -> Result[bool, Exception]:
        self.clicks.append(f"{button}_{'double' if double else 'single'}")
        return Ok(True)

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> Result[bool, Exception]:
        self.cursor_x, self.cursor_y = x2, y2
        return Ok(True)

    def type_text(self, text: str) -> Result[bool, Exception]:
        self.last_typed.append(text)
        return Ok(True)

    def press_hotkey(self, keys: List[str]) -> Result[bool, Exception]:
        self.last_hotkeys.append(keys)
        return Ok(True)

    def capture_screen(self, output_path: Path) -> Result[Path, Exception]:
        img = Image.new("RGB", (1920, 1080), color=(15, 13, 25))
        img.save(str(output_path), "PNG")
        return Ok(output_path)


def get_display_backend(force_backend: Optional[str] = None) -> DisplayBackend:
    """Factory selecting the optimal display driver based on environment."""
    import sys

    if force_backend == "headless":
        return HeadlessDisplay()
    if force_backend == "wayland":
        return WaylandDisplay()
    if force_backend == "x11":
        return X11Display()
    if force_backend == "windows":
        return WindowsDisplay()

    if sys.platform == "win32":
        return WindowsDisplay()

    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session == "wayland":
        return WaylandDisplay()
    if session == "x11" or os.environ.get("DISPLAY"):
        return X11Display()
    return HeadlessDisplay()
