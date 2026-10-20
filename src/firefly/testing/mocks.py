"""Deterministic Mock LLM and Virtual Desktop for robust testing (Feature 113)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw

from firefly.core.result import Ok, Result
from firefly.display.base import DisplayBackend
from firefly.providers.base import LLMProvider, LLMResponse, ToolCall


class MockLLM(LLMProvider):
    """Programmable, deterministic mock LLM for testing multi-turn ReAct interactions."""

    def __init__(self, canned_responses: Optional[List[str | LLMResponse]] = None) -> None:
        self.queue: List[LLMResponse] = []
        if canned_responses:
            for r in canned_responses:
                self.queue_response(r)
        self.calls: List[Dict[str, Any]] = []
        self.latency_sec: float = 0.0

    def queue_response(
        self,
        response: str | LLMResponse,
        tool_calls: Optional[List[Tuple[str, Dict[str, Any]]]] = None,
    ) -> None:
        """Queues a deterministic response to be returned by subsequent chat() invocations."""
        if isinstance(response, LLMResponse):
            self.queue.append(response)
        else:
            t_calls: List[ToolCall] = []
            if tool_calls:
                for idx, (fn_name, fn_args) in enumerate(tool_calls):
                    t_calls.append(
                        ToolCall(id=f"call_{idx}_{fn_name}", name=fn_name, arguments=fn_args)
                    )
            self.queue.append(LLMResponse(content=response, tool_calls=t_calls))

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.3,
    ) -> Result[LLMResponse, Exception]:
        """Captures input request and returns next queued mock response."""
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
                "timestamp": time.time(),
            }
        )

        if self.latency_sec > 0:
            time.sleep(self.latency_sec)

        if self.queue:
            return Ok(self.queue.pop(0))

        # Default fallback response
        return Ok(LLMResponse(content="(=^･ω･^=) *chirp* Default mock response."))

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def last_message_content(self) -> str:
        """Extracts content of the last message passed to the model."""
        if not self.calls:
            return ""
        last_msgs = self.calls[-1]["messages"]
        if not last_msgs:
            return ""
        return str(last_msgs[-1].get("content", ""))


class MockDesktop(DisplayBackend):
    """Headless virtual desktop environment simulating screen capture and user input."""

    def __init__(self, width: int = 1920, height: int = 1080) -> None:
        self.width = width
        self.height = height
        self.cursor_x = width // 2
        self.cursor_y = height // 2
        self.active_window_title = "Firefly Terminal"
        self.mouse_events: List[Dict[str, Any]] = []
        self.keyboard_events: List[Dict[str, Any]] = []

    def get_cursor_position(self) -> Tuple[int, int]:
        """Returns simulated cursor coordinates."""
        return (self.cursor_x, self.cursor_y)

    def move_cursor(self, x: int, y: int) -> None:
        """Simulates cursor motion."""
        self.cursor_x = max(0, min(self.width, x))
        self.cursor_y = max(0, min(self.height, y))
        self.mouse_events.append({"action": "move", "x": self.cursor_x, "y": self.cursor_y})

    def move_mouse(self, x: int, y: int) -> Result[bool, Exception]:
        """DisplayBackend implementation of cursor motion."""
        self.move_cursor(x, y)
        return Ok(True)

    def click(self, button: str = "left", double: bool = False) -> Result[bool, Exception]:
        """Simulates mouse button click at active cursor location."""
        self.mouse_events.append(
            {
                "action": "click",
                "button": button,
                "double": double,
                "x": self.cursor_x,
                "y": self.cursor_y,
            }
        )
        return Ok(True)

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> Result[bool, Exception]:
        """Simulates mouse dragging."""
        self.move_cursor(x1, y1)
        self.mouse_events.append({"action": "drag_start", "x": self.cursor_x, "y": self.cursor_y})
        self.move_cursor(x2, y2)
        self.mouse_events.append({"action": "drag_end", "x": self.cursor_x, "y": self.cursor_y})
        return Ok(True)

    def type_text(self, text: str) -> Result[bool, Exception]:
        """Simulates keyboard character typing."""
        self.keyboard_events.append({"action": "type", "text": text})
        return Ok(True)

    def press_hotkey(self, keys: List[str]) -> Result[bool, Exception]:
        """Simulates keyboard shortcut combination."""
        self.keyboard_events.append({"action": "hotkey", "keys": list(keys)})
        return Ok(True)

    def get_active_window(self) -> Optional[str]:
        """Returns virtual focused window title."""
        return self.active_window_title

    def take_screenshot(self, target_path: Optional[str] = None) -> Image.Image:
        """Generates a synthetic PIL Image canvas with mock desktop elements."""
        img = Image.new("RGB", (self.width, self.height), color=(30, 30, 46))
        draw = ImageDraw.Draw(img)

        # Draw virtual desktop top panel
        draw.rectangle([(0, 0), (self.width, 32)], fill=(17, 17, 27))
        draw.text((16, 8), f"Mock Desktop ({self.active_window_title})", fill=(205, 214, 244))

        # Draw mock active window
        draw.rectangle(
            [(200, 150), (self.width - 200, self.height - 150)],
            outline=(0, 240, 255),
            width=2,
            fill=(24, 24, 37),
        )

        # Draw simulated cursor crosshair
        cx, cy = self.cursor_x, self.cursor_y
        draw.line([(cx - 8, cy), (cx + 8, cy)], fill=(255, 0, 127), width=2)
        draw.line([(cx, cy - 8), (cx, cy + 8)], fill=(255, 0, 127), width=2)

        if target_path:
            img.save(target_path)

        return img

    def capture_screen(self, output_path: Path) -> Result[Path, Exception]:
        """DisplayBackend implementation capturing virtual screen to disk."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.take_screenshot(target_path=str(output_path))
        return Ok(output_path)
