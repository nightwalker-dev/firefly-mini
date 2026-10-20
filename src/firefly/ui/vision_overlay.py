"""Screen annotation and visual grounding overlay visualizer for desktop vision actions."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw

from firefly.ui.themes import CyberTheme, theme_manager


class VisionOverlayAnnotator:
    """Draws cyberpunk bounding boxes, crosshairs, and click markers onto screenshots."""

    def __init__(self, theme: Optional[CyberTheme] = None):
        self.theme = theme or theme_manager.current

    def annotate_screenshot(
        self,
        image_path: Path,
        bounding_boxes: Optional[List[Tuple[int, int, int, int, str]]] = None,
        click_targets: Optional[List[Tuple[int, int, str]]] = None,
        output_path: Optional[Path] = None,
    ) -> Path:
        """Draws annotations on a desktop screenshot and saves the visual verification image.

        Args:
            image_path: Path to original screenshot image.
            bounding_boxes: List of (x1, y1, x2, y2, label) tuples.
            click_targets: List of (x, y, label) target click coordinates.
            output_path: Where to save annotated image (defaults to <original>_annotated.png).
        """
        img = Image.open(image_path).convert("RGBA")
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        from firefly.ui.themes import ContrastVerifier

        r1, g1, b1 = ContrastVerifier.hex_to_rgb(self.theme.neon_primary)
        r2, g2, b2 = ContrastVerifier.hex_to_rgb(self.theme.neon_secondary)
        r3, g3, b3 = ContrastVerifier.hex_to_rgb(self.theme.accent_amber)
        neon_color = (r1, g1, b1, 230)
        box_bg_color = (r2, g2, b2, 45)
        amber_color = (r3, g3, b3, 255)

        # 1. Draw bounding boxes
        if bounding_boxes:
            for x1, y1, x2, y2, label in bounding_boxes:
                # Semi-transparent box fill
                draw.rectangle([(x1, y1), (x2, y2)], fill=box_bg_color, outline=neon_color, width=3)

                # Label tag
                tag_h = 22
                tag_w = max(60, len(label) * 9 + 12)
                draw.rectangle(
                    [(x1, max(0, y1 - tag_h)), (x1 + tag_w, max(0, y1))], fill=(20, 18, 31, 220)
                )
                draw.text((x1 + 6, max(0, y1 - tag_h) + 4), f"✦ {label}", fill=neon_color)

        # 2. Draw click targets & crosshairs
        if click_targets:
            for cx, cy, label in click_targets:
                # Concentric radar rings
                for r in (8, 18, 28):
                    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=amber_color, width=2)
                # Crosshairs
                draw.line([(cx - 36, cy), (cx + 36, cy)], fill=amber_color, width=2)
                draw.line([(cx, cy - 36), (cx, cy + 36)], fill=amber_color, width=2)
                # Label
                draw.rectangle(
                    [(cx + 12, cy + 12), (cx + 12 + len(label) * 9, cy + 32)],
                    fill=(20, 18, 31, 230),
                )
                draw.text((cx + 16, cy + 16), label, fill=amber_color)

        combined = Image.alpha_composite(img, overlay).convert("RGB")
        out = output_path or image_path.with_name(f"{image_path.stem}_annotated.png")
        combined.save(out, "PNG")
        return out


vision_annotator = VisionOverlayAnnotator()
