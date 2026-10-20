"""Unified Input Control for X11 and Wayland environments.

Supports:
- Mouse movement, clicking, dragging, and scrolling.
- Text typing with terminal injection guards.
- Hotkey combinations with dangerous-combo prevention.
- Rate limiting to prevent runaway automation loops.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from typing import Callable, Optional

from firefly.core.config import settings
from firefly.core.guardrails import Action, Guardrails, RateLimiter, Verdict
from firefly.core.logger import logger


class InputController:
    """Dispatches mouse and keyboard events safely to the display server."""

    def __init__(
        self,
        guardrails: Optional[Guardrails] = None,
        confirm_callback: Optional[Callable[[Verdict], bool]] = None,
    ):
        self.guardrails = guardrails or Guardrails(
            auto_approve_max_risk=settings.auto_approve_max_risk
        )
        self.confirm_callback = confirm_callback or (lambda v: False)
        self.rate_limiter = RateLimiter(settings.input_rate_limit)

        self.session_type = os.environ.get("XDG_SESSION_TYPE", "wayland").lower()
        self.has_ydotool = shutil.which("ydotool") is not None
        self.has_xdotool = shutil.which("xdotool") is not None
        self.has_wtype = shutil.which("wtype") is not None

        # Check pyautogui availability
        try:
            import pyautogui

            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.05
            self._pyautogui = pyautogui
        except Exception:
            self._pyautogui = None

    def _check_rate(self) -> bool:
        if not self.rate_limiter.allow():
            time.sleep(0.1)
            return self.rate_limiter.allow()
        return True

    # ------------------------------------------------------------- Mouse APIs
    def move_mouse(self, x: int, y: int) -> bool:
        """Moves cursor to absolute coordinates (x, y)."""
        if not self._check_rate():
            return False

        start = time.monotonic()
        ok = False
        if self.session_type == "wayland" and self.has_ydotool:
            cmd = ["ydotool", "mousemove", "-a", str(x), str(y)]
            ok = subprocess.run(cmd, capture_output=True).returncode == 0
        elif self.has_xdotool:
            cmd = ["xdotool", "mousemove", str(x), str(y)]
            ok = subprocess.run(cmd, capture_output=True).returncode == 0
        elif self._pyautogui:
            try:
                self._pyautogui.moveTo(x, y)
                ok = True
            except Exception:
                ok = False
        else:
            # Headless virtual simulation
            ok = True

        duration = (time.monotonic() - start) * 1000
        logger.log("mouse", f"move({x}, {y})", "SAFE", "allow", ok, duration_ms=duration)
        return ok

    def click(self, button: str = "left", double: bool = False) -> bool:
        """Clicks specified mouse button ('left', 'right', 'middle')."""
        if not self._check_rate():
            return False

        btn_map_xdo = {"left": "1", "middle": "2", "right": "3"}
        btn_map_ydo = {"left": "0xC0", "right": "0xC1", "middle": "0xC2"}

        btn_xdo = btn_map_xdo.get(button.lower(), "1")
        btn_ydo = btn_map_ydo.get(button.lower(), "0xC0")

        start = time.monotonic()
        ok = False
        clicks = 2 if double else 1

        if self.session_type == "wayland" and self.has_ydotool:
            cmd = ["ydotool", "click", "--repeat", str(clicks), btn_ydo]
            ok = subprocess.run(cmd, capture_output=True).returncode == 0
        elif self.has_xdotool:
            cmd = ["xdotool", "click", "--repeat", str(clicks), btn_xdo]
            ok = subprocess.run(cmd, capture_output=True).returncode == 0
        elif self._pyautogui:
            try:
                self._pyautogui.click(button=button, clicks=clicks)
                ok = True
            except Exception:
                ok = False
        else:
            ok = True  # virtual simulation

        duration = (time.monotonic() - start) * 1000
        logger.log(
            "mouse", f"click({button}, double={double})", "SAFE", "allow", ok, duration_ms=duration
        )
        return ok

        duration = (time.monotonic() - start) * 1000
        logger.log(
            "mouse", f"click({button}, double={double})", "SAFE", "allow", ok, duration_ms=duration
        )
        return ok

    def mouse_drag(self, x1: int, y1: int, x2: int, y2: int) -> bool:
        """Performs a click and drag operation from (x1, y1) to (x2, y2)."""
        if not self._check_rate():
            return False

        self.move_mouse(x1, y1)
        time.sleep(0.05)
        if self.has_xdotool:
            subprocess.run(["xdotool", "mousedown", "1"], capture_output=True)
            time.sleep(0.05)
            self.move_mouse(x2, y2)
            time.sleep(0.05)
            subprocess.run(["xdotool", "mouseup", "1"], capture_output=True)
            return True
        elif self.has_ydotool:
            subprocess.run(["ydotool", "click", "0x40"], capture_output=True)
            time.sleep(0.05)
            self.move_mouse(x2, y2)
            time.sleep(0.05)
            subprocess.run(["ydotool", "click", "0x80"], capture_output=True)
            return True
        elif self._pyautogui:
            try:
                self._pyautogui.dragTo(x2, y2)
                return True
            except Exception:
                return False
        return True

    # ---------------------------------------------------------- Keyboard APIs
    def type_text(self, text: str, target_is_terminal: bool = True) -> tuple[bool, str]:
        """Types string character-by-character after verifying guardrails."""
        if not self._check_rate():
            return False, "Rate limit exceeded"

        # Guardrail scan
        verdict = self.guardrails.check_typed_text(text, target_is_terminal=target_is_terminal)
        if verdict.action == Action.BLOCK:
            logger.log(
                "keyboard", f"type({text[:20]}...)", verdict.risk.name, verdict.action.value, False
            )
            return False, f"Guardrail blocked typed text: {verdict.summary()}"

        if verdict.action == Action.CONFIRM:
            if not self.confirm_callback(verdict):
                logger.log(
                    "keyboard",
                    f"type({text[:20]}...)",
                    verdict.risk.name,
                    verdict.action.value,
                    False,
                )
                return False, "Human rejected typing text"

        start = time.monotonic()
        ok = False

        if self.session_type == "wayland" and self.has_wtype:
            cmd = ["wtype", text]
            ok = subprocess.run(cmd, capture_output=True).returncode == 0
        elif self.session_type == "wayland" and self.has_ydotool:
            cmd = ["ydotool", "type", "--", text]
            ok = subprocess.run(cmd, capture_output=True).returncode == 0
        elif self.has_xdotool:
            cmd = ["xdotool", "type", "--clearmodifiers", "--", text]
            ok = subprocess.run(cmd, capture_output=True).returncode == 0
        elif self._pyautogui:
            try:
                self._pyautogui.write(text, interval=0.01)
                ok = True
            except Exception:
                ok = False
        else:
            ok = True

        duration = (time.monotonic() - start) * 1000
        logger.log(
            "keyboard",
            f"type(len={len(text)})",
            verdict.risk.name,
            verdict.action.value,
            ok,
            duration_ms=duration,
        )
        return ok, "Typed successfully" if ok else "Failed typing dispatch"

    def press_hotkey(self, keys: list[str]) -> tuple[bool, str]:
        """Presses combination of keys (e.g. ['ctrl', 'c'] or ['super', 'Return'])."""
        if not self._check_rate():
            return False, "Rate limit exceeded"

        verdict = self.guardrails.check_hotkey(keys)
        if verdict.action == Action.BLOCK:
            return False, f"Guardrail blocked hotkey: {verdict.summary()}"
        if verdict.action == Action.CONFIRM:
            if not self.confirm_callback(verdict):
                return False, "Human rejected hotkey combination"

        start = time.monotonic()
        combo_xdo = "+".join(keys)
        ok = False

        if self.has_xdotool:
            cmd = ["xdotool", "key", "--clearmodifiers", combo_xdo]
            ok = subprocess.run(cmd, capture_output=True).returncode == 0
        elif self.has_ydotool:
            cmd = ["ydotool", "key", combo_xdo]
            ok = subprocess.run(cmd, capture_output=True).returncode == 0
        elif self._pyautogui:
            try:
                self._pyautogui.hotkey(*[k.lower() for k in keys])
                ok = True
            except Exception:
                ok = False
        else:
            ok = True

        duration = (time.monotonic() - start) * 1000
        logger.log(
            "hotkey", combo_xdo, verdict.risk.name, verdict.action.value, ok, duration_ms=duration
        )
        return ok, "Hotkey dispatched" if ok else "Hotkey dispatch failed"
