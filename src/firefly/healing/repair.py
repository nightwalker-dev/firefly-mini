"""Self-repair engines: broken configuration auto-recovery and LLM tool-call JSON repair."""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Optional

from firefly.core.result import Err, Ok, Result


class ConfigAutoRepair:
    """Detects and repairs corrupted configuration or state files using backup or default recovery."""

    @staticmethod
    def repair_json_file(
        target_path: Path,
        default_content: Optional[Dict[str, Any]] = None,
    ) -> Result[Dict[str, Any], str]:
        """Validates a JSON config file. If corrupted, preserves artifact and restores from .bak or defaults."""
        if not target_path.exists():
            defaults = default_content or {}
            target_path.parent.mkdir(parents=True, exist_ok=True)
            content = json.dumps(defaults, indent=2)
            target_path.write_text(content, encoding="utf-8")
            bak_path = target_path.with_suffix(target_path.suffix + ".bak")
            bak_path.write_text(content, encoding="utf-8")
            return Ok(defaults)

        raw = target_path.read_text(encoding="utf-8")
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                # Healthy file: create/update fresh backup
                bak_path = target_path.with_suffix(target_path.suffix + ".bak")
                bak_path.write_text(raw, encoding="utf-8")
                return Ok(parsed)
        except Exception:
            # File is corrupted!
            timestamp = int(time.time())
            corrupted_path = target_path.with_name(f"{target_path.name}.corrupted.{timestamp}")
            shutil.copy2(target_path, corrupted_path)

            bak_path = target_path.with_suffix(target_path.suffix + ".bak")
            if bak_path.exists():
                try:
                    bak_content = bak_path.read_text(encoding="utf-8")
                    restored_dict = json.loads(bak_content)
                    target_path.write_text(bak_content, encoding="utf-8")
                    return Ok(restored_dict)
                except Exception:
                    pass

            # Restore from fallback defaults
            fallback = default_content or {}
            target_path.write_text(json.dumps(fallback, indent=2), encoding="utf-8")
            return Ok(fallback)

        return Err("Configuration structure invalid.")


class JSONRepair:
    """Robust parser that cleans and heals malformed JSON from LLM generation."""

    @classmethod
    def repair_json(cls, raw: str) -> Dict[str, Any]:
        """Repairs common LLM formatting flaws and returns parsed JSON dictionary."""
        text = raw.strip()

        # 1. Direct standard parse attempt
        try:
            res = json.loads(text)
            if isinstance(res, dict):
                return res
        except Exception:
            pass

        # 2. Extract content within markdown code blocks if present
        code_block = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if code_block:
            text = code_block.group(1).strip()
            try:
                res = json.loads(text)
                if isinstance(res, dict):
                    return res
            except Exception:
                pass

        # 3. Find outermost curly braces { ... }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
        elif start != -1 and end == -1:
            text = text[start:] + "}"

        # 4. Normalize Python literals to JSON
        text = re.sub(r"\bTrue\b", "true", text)
        text = re.sub(r"\bFalse\b", "false", text)
        text = re.sub(r"\bNone\b", "null", text)

        # 5. Fix single quotes to double quotes for keys and values
        # Replace unquoted or single quoted keys: {'key': -> {"key":
        text = re.sub(r"([{,]\s*)'([^']+)'\s*:", r'\1"\2":', text)
        # Replace unquoted keys: {key: -> {"key":
        text = re.sub(r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\1"\2":', text)
        # Replace single quoted string values: : 'val' -> : "val"
        text = re.sub(r":\s*'([^']*)'", r': "\1"', text)

        # 6. Remove trailing commas before closing braces/brackets
        text = re.sub(r",\s*([}\]])", r"\1", text)

        # 7. Balance missing closing braces/brackets
        open_braces = text.count("{") - text.count("}")
        open_brackets = text.count("[") - text.count("]")

        if open_brackets > 0:
            text = text + ("]" * open_brackets)
        if open_braces > 0:
            text = text + ("}" * open_braces)

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
            return {"data": parsed}
        except Exception as e:
            raise ValueError(f"Unable to heal malformed JSON: {e} (source: {text[:80]})") from e
