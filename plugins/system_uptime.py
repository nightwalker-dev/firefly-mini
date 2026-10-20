"""Example Firefly Mini user plugin demonstrating the @tool decorator and typed Pydantic arguments."""
from __future__ import annotations

import os

from pydantic import BaseModel, Field

from firefly.agent.tool_registry import tool


class UptimeArgs(BaseModel):
    detailed: bool = Field(default=False, description="Whether to include raw load averages")


@tool(name="host_uptime", description="Check system uptime and operational duration", args_schema=UptimeArgs)
def host_uptime(detailed: bool = False) -> str:
    try:
        with open("/proc/uptime", "r") as f:
            total_seconds = float(f.readline().split()[0])
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        report = f"System online for {hours}h {minutes}m ({total_seconds:.0f} seconds total)"
        if detailed and hasattr(os, "getloadavg"):
            report += f" | Load average: {os.getloadavg()}"
        return report
    except Exception as exc:
        return f"Unable to read uptime: {exc}"
