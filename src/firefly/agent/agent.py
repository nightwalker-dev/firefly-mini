"""Firefly Mini ReAct Orchestrator: brings Planner, Executor, Reflector, and LLMProvider together."""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional

from firefly.agent.executor import ToolExecutor
from firefly.agent.planner import Planner
from firefly.agent.reflector import Reflector
from firefly.agent.tool_registry import ToolRegistry, default_registry
from firefly.core.config import settings
from firefly.core.container import Container, default_container
from firefly.core.events import Event, EventBus, default_bus
from firefly.core.guardrails import Guardrails, MFAGate, Verdict
from firefly.providers.base import LLMProvider, OllamaProvider
from firefly.system.bash_executor import BashExecutor
from firefly.voice.speaker import speaker


class FireflyAgent:
    """The Autonomous Cyber-Cat Agent Core."""

    def __init__(
        self,
        container: Optional[Container] = None,
        confirm_callback: Optional[Callable[[Verdict], bool]] = None,
        mfa_callback: Optional[Callable[[Verdict], bool]] = None,
    ) -> None:
        self.container = container or default_container
        self.bus = self.container.resolve_optional(EventBus) or default_bus

        # Guardrails & safety
        self.guardrails = self.container.resolve_optional(Guardrails) or Guardrails(
            auto_approve_max_risk=settings.auto_approve_max_risk
        )
        self.mfa_gate = MFAGate(totp_secret=settings.totp_secret)
        self.confirm_callback = confirm_callback or self._cli_confirm
        self.mfa_callback = mfa_callback or self._cli_mfa

        # Subsystems
        self.bash = BashExecutor(
            guardrails=self.guardrails,
            confirm_callback=self.confirm_callback,
            mfa_callback=self.mfa_callback,
        )
        self.container.register_instance(BashExecutor, self.bash)
        self.container.register_instance(Guardrails, self.guardrails)

        # Modularity components
        self.planner: Planner = self.container.resolve_optional(Planner) or Planner()
        self.container.register_instance(Planner, self.planner)
        self.registry = self.container.resolve_optional(ToolRegistry) or default_registry
        import firefly.plugins.builtin  # noqa: F401

        self.executor = ToolExecutor(registry=self.registry, bus=self.bus)
        self.reflector = Reflector()

        # LLM Provider
        self.provider = self.container.resolve_optional(LLMProvider) or OllamaProvider(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout=settings.llm_timeout,
            max_retries=getattr(settings.llm, "max_retries", 2),
        )

        # Adaptive Memory System
        from firefly.memory.preferences import PersonaContinuity, UserPreferencesManager
        from firefly.memory.retrieval import ContextAwareRetriever
        from firefly.memory.store import MemoryStore

        self.memory_store = self.container.resolve_optional(MemoryStore) or MemoryStore()
        self.retriever = ContextAwareRetriever(self.memory_store)
        self.preferences = UserPreferencesManager(self.memory_store)
        self.persona = PersonaContinuity(self.memory_store)
        self.container.register_instance(MemoryStore, self.memory_store)

        # Discover external plugins
        self.registry.discover_plugins()

    @property
    def history(self) -> List[Dict[str, Any]]:
        return self.planner.history

    # ------------------------------------------------ Human-in-the-Loop Prompts
    def _cli_confirm(self, verdict: Verdict) -> bool:
        speaker.beep()
        print("\n" + "=" * 60)
        print("🐾 [FIREFLY SAFETY GUARDRAIL: CONFIRMATION REQUIRED]")
        print(verdict.summary())
        print("=" * 60)
        try:
            ans = input("Authorize this elevated operation? [y/N]: ").strip().lower()
            return ans in ("y", "yes")
        except (KeyboardInterrupt, EOFError):
            return False

    def _cli_mfa(self, verdict: Verdict) -> bool:
        speaker.alert()
        challenge = self.mfa_gate.issue(verdict.subject)
        print("\n" + "!" * 60)
        print("🚨 [FIREFLY CRITICAL GUARDRAIL: MULTI-FACTOR AUTH REQUIRED]")
        print(verdict.summary())
        print(f"SECURITY CODE: {challenge.code}")
        print("!" * 60)
        try:
            code = input(
                f"Enter the 6-character code [{challenge.code}] to verify human intent: "
            ).strip()
            totp = None
            if self.mfa_gate.totp_enabled:
                totp = input("Enter your 6-digit TOTP code: ").strip()
            return self.mfa_gate.verify(verdict.subject, code, totp=totp)
        except (KeyboardInterrupt, EOFError):
            return False

    # ------------------------------------------------ ReAct Loop
    async def dispatch_tool(self, name: str, args: Dict[str, Any]) -> str:
        """Executes a tool through the executor."""
        return await self.executor.execute_tool(name, args)

    async def chat(self, user_message: str) -> str:
        """Processes user input through the ReAct multi-step reasoning loop."""
        from firefly.security.provenance import default_provenance
        from firefly.security.session import default_session_guard

        sess_ok, sess_msg = default_session_guard.check_session()
        if not sess_ok:
            return f"(=^xェx^=) Master, my session is locked: {sess_msg}"

        with default_provenance.track(user_prompt=user_message, trigger="user_direct"):
            self.planner.add_user_message(user_message)
            await self.bus.publish(Event(topic="agent.turn_started", data={"query": user_message}))

            # Adaptive memory extraction & context injection
            self.preferences.extract_preferences_from_text(user_message)
            mem_block = self.retriever.format_prompt_block(user_message)
            if mem_block:
                self.planner.inject_system_message(mem_block)

            for step in range(settings.max_steps):
                tools_def = self.registry.get_definitions()
                llm_result = await self.provider.chat(
                    messages=self.planner.get_messages(),
                    tools=tools_def if tools_def else None,
                )

                if llm_result.is_err():
                    # Fallback heuristic if local LLM is down
                    err_str = str(llm_result.unwrap_err())
                    fallback = self._fallback_local_response(user_message, err_str)
                    await self.bus.publish(
                        Event(topic="agent.turn_finished", data={"response": fallback})
                    )
                    return fallback

                response = llm_result.unwrap()
                content = response.content or ""
                tool_calls = response.tool_calls

                # 1. No formal tool calls
                if not tool_calls:
                    # Check for markdown tool call syntax
                    tool_match = re.search(
                        r'```json\s*\{\s*"tool"\s*:\s*"(\w+)"\s*,\s*"args"\s*:\s*(\{.*?\})\s*\}\s*```',
                        content,
                        re.DOTALL,
                    )
                    if tool_match:
                        fn_name, fn_args_str = tool_match.group(1), tool_match.group(2)
                        try:
                            fn_args = json.loads(fn_args_str)
                            res = await self.dispatch_tool(fn_name, fn_args)
                            self.planner.add_assistant_message(content)
                            self.planner.add_user_message(
                                f"Tool {fn_name} returned: {res}. Complete your response."
                            )
                            continue
                        except Exception:
                            pass

                    self.planner.add_assistant_message(content)
                    await self.bus.publish(
                        Event(topic="agent.turn_finished", data={"response": content})
                    )
                    return content or "*purrs softly* Done!"

                # 2. Formal tool calls
                formatted_tc = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in tool_calls
                ]
                self.planner.add_assistant_message(content, tool_calls=formatted_tc)

                for tc in tool_calls:
                    result_str = await self.dispatch_tool(tc.name, tc.arguments)
                    self.planner.add_tool_result(tc.id, tc.name, result_str)

                    # Reflect on outcome
                    eval_step = self.reflector.evaluate_step(tc.name, result_str)
                    if eval_step.should_stop:
                        break

            timeout_msg = "*purrs softly* Task execution limit reached, master."
            await self.bus.publish(
                Event(topic="agent.turn_finished", data={"response": timeout_msg})
            )
            return timeout_msg

    def _fallback_local_response(self, user_query: str, error_detail: str) -> str:
        q = user_query.lower()
        if "theme" in q or "wallpaper" in q:
            from firefly.system.themer import themer

            wp = themer.generate_cyber_cat_wallpaper()
            applied = themer.set_wallpaper(wp)
            themer.export_kitty_theme()
            themer.export_alacritty_theme()
            themer.export_shell_prompt()
            speaker.purr()
            return f"*chirp!* (*=^･ω･^=*) Cyber-Cat Obsidian/Neon theme generated and applied!\nWallpaper: {wp}\nApplied via display daemon: {applied}"

        if "status" in q or "hud" in q or "info" in q:
            speaker.beep()
            return f"*ears perk up* Firefly Mini is active. Local LLM endpoint unreachable ({error_detail[:50]}), operating in Autonomous Guardrail Direct Mode."

        if q.startswith("run ") or q.startswith("exec ") or q.startswith("check "):
            cmd = user_query.split(maxsplit=1)[1]
            res = self.bash.run(cmd)
            return f"*tail flick* Executed `{cmd}`:\n```\n{res.stdout or res.stderr}\n```"

        return f"*chirps curiously* Firefly Mini received: '{user_query}'. (Endpoint notice: {error_detail[:60]})"
