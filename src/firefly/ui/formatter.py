"""Syntax-highlighted terminal output formatter for tool executions, logs, and code."""

from __future__ import annotations

import json
from typing import Optional, Union

from rich.box import ROUNDED
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from firefly.memory.redactor import SecretRedactor
from firefly.ui.themes import CyberTheme, theme_manager


class OutputFormatter:
    """Formats, syntax-highlights, and safely bounds agent tool execution outputs."""

    def __init__(self, theme: Optional[CyberTheme] = None):
        self.theme = theme or theme_manager.current

    @classmethod
    def detect_language(cls, text: str) -> str:
        """Guesses the syntax language of raw output text."""
        trimmed = text.strip()
        if (trimmed.startswith("{") and trimmed.endswith("}")) or (
            trimmed.startswith("[") and trimmed.endswith("]")
        ):
            try:
                json.loads(trimmed)
                return "json"
            except Exception:
                pass

        if "def " in trimmed or "import " in trimmed or "class " in trimmed:
            return "python"
        if (
            trimmed.startswith("#!/bin/bash")
            or trimmed.startswith("#!/bin/sh")
            or "echo " in trimmed
        ):
            return "bash"
        if "---" in trimmed and ":" in trimmed:
            return "yaml"
        if trimmed.startswith("# ") or "## " in trimmed:
            return "markdown"
        return "text"

    def format_output(
        self,
        raw_output: str,
        title: str = "Execution Output",
        max_lines: int = 40,
        language: Optional[str] = None,
        theme: Optional[CyberTheme] = None,
    ) -> Panel:
        """Sanitizes secrets, applies syntax highlighting, and formats output into a Rich Panel."""
        t = theme or self.theme

        # 1. Mandatory secret redaction before display
        sanitized = SecretRedactor.redact(raw_output)

        # 2. Line truncation handling
        lines = sanitized.splitlines()
        total_lines = len(lines)
        if total_lines > max_lines:
            lines = lines[:max_lines]
            lines.append(
                f"... [{t.dim_text}]({total_lines - max_lines} lines truncated for readability)[/]"
            )

        content_str = "\n".join(lines)
        lang = language or self.detect_language(sanitized)

        # 3. Apply Syntax or Text
        renderable: Union[Syntax, Text]
        if lang != "text":
            renderable = Syntax(
                content_str,
                lexer=lang,
                theme="monokai",
                line_numbers=True if lang in ("python", "bash") else False,
                word_wrap=True,
            )
        else:
            renderable = Text.from_markup(f"[{t.fg_text}]{content_str}[/]")

        return Panel(
            renderable,
            title=f"[bold {t.neon_primary}]✦ {title} ✦[/]",
            subtitle=f"[{t.dim_text}]lang: {lang} | lines: {total_lines}[/]",
            border_style=t.neon_secondary,
            box=ROUNDED,
            expand=True,
        )


output_formatter = OutputFormatter()
