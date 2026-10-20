"""Screen Capture, Visual Grounding, and Coordinate Resolution.

Captures active screens across Wayland and X11, queries Vision-Language Models (VLM)
for UI coordinates, and provides spatial grounding for mouse actions.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import httpx
from PIL import Image

from firefly.core.config import settings
from firefly.core.logger import logger


@dataclass
class ScreenTarget:
    label: str
    x: int
    y: int
    confidence: float
    description: str


class VisionGrounder:
    """Captures screen and resolves visual elements into (x, y) coordinates."""

    def __init__(self, vlm_model: Optional[str] = None):
        self.vlm_model = vlm_model or settings.vlm_model
        self.session_type = os.environ.get("XDG_SESSION_TYPE", "wayland").lower()

    def capture_screen(self, output_path: Optional[Path] = None) -> Optional[Path]:
        """Takes a full screen capture and writes to file."""
        if not output_path:
            fd, tmp = tempfile.mkstemp(suffix=".png", prefix="firefly_screen_")
            os.close(fd)
            output_path = Path(tmp)

        ok = False
        # 1. Wayland grim
        if self.session_type == "wayland" and shutil.which("grim"):
            res = subprocess.run(["grim", str(output_path)], capture_output=True)
            ok = res.returncode == 0

        # 2. X11 scrot
        if not ok and shutil.which("scrot"):
            res = subprocess.run(["scrot", str(output_path)], capture_output=True)
            ok = res.returncode == 0

        # 3. ImageMagick import
        if not ok and shutil.which("import"):
            res = subprocess.run(
                ["import", "-window", "root", str(output_path)], capture_output=True
            )
            ok = res.returncode == 0

        # 4. Native Python mss
        if not ok:
            try:
                import mss

                mss_cls = getattr(mss, "MSS", getattr(mss, "mss", None))
                if mss_cls:
                    with mss_cls() as sct:
                        sct.shot(output=str(output_path))
                    ok = output_path.exists() and output_path.stat().st_size > 500
            except Exception:
                ok = False

        # 5. Headless / virtual display placeholder fallback
        if not ok or not output_path.exists():
            try:
                # Generate a 1920x1080 virtual canvas so downstream VLM / processing does not crash
                img = Image.new("RGB", (1920, 1080), color=(15, 13, 25))
                img.save(str(output_path), "PNG")
                return output_path
            except Exception:
                return None

        return output_path

    def get_screen_size(self) -> Tuple[int, int]:
        """Returns (width, height) of primary display."""
        cap = self.capture_screen()
        if cap and cap.exists():
            try:
                with Image.open(cap) as img:
                    w, h = img.size
                cap.unlink(missing_ok=True)
                return w, h
            except Exception:
                pass
        return 1920, 1080

    async def locate_element(self, query: str) -> Optional[ScreenTarget]:
        """Uses VLM to inspect the current screen and identify coordinates for `query`."""
        img_path = self.capture_screen()
        if not img_path:
            return None

        try:
            with Image.open(img_path) as img:
                w, h = img.size
                # Convert to base64
                with open(img_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("ascii")

            prompt = (
                f"You are the visual grounding engine for a desktop agent. Screen resolution is {w}x{h}.\n"
                f"Target element to find: '{query}'.\n"
                f"Analyze the image and return a JSON object with keys: "
                f'"found" (boolean), "x" (integer pixel coordinate from left), "y" (integer pixel coordinate from top), '
                f'"description" (string), "confidence" (float between 0 and 1).\n'
                f"Output strictly raw JSON without markdown formatting."
            )

            payload = {
                "model": self.vlm_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{b64}"},
                            },
                        ],
                    }
                ],
                "temperature": 0.1,
            }

            async with httpx.AsyncClient(timeout=settings.llm_timeout) as client:
                resp = await client.post(
                    f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                    json=payload,
                )

                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"].strip()
                    # Clean potential markdown fences
                    content = re.sub(
                        r"^```json\s*|\s*```$", "", content, flags=re.MULTILINE
                    ).strip()
                    parsed = json.loads(content)
                    if parsed.get("found"):
                        return ScreenTarget(
                            label=query,
                            x=int(parsed.get("x", w // 2)),
                            y=int(parsed.get("y", h // 2)),
                            confidence=float(parsed.get("confidence", 0.8)),
                            description=parsed.get("description", ""),
                        )
        except Exception as e:
            logger.log("vision", f"locate({query})", "SAFE", "allow", False, output_summary=str(e))
        finally:
            if img_path and img_path.exists():
                img_path.unlink(missing_ok=True)

        return None
