"""Abstract LLM Provider interface, OpenAI/Ollama implementation, and deterministic Mock provider."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import httpx

from firefly.core.result import Err, Ok, Result


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class LLMResponse:
    content: Optional[str]
    tool_calls: List[ToolCall] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract interface decoupling agent reasoning from specific LLM vendors."""

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.3,
    ) -> Result[LLMResponse, Exception]:
        """Sends chat request and returns structured response or Result Err."""


class OllamaProvider(LLMProvider):
    """Client for local Ollama, llama.cpp, vLLM, or any OpenAI-compatible API."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "ollama",
        model: str = "qwen2.5:7b-instruct",
        timeout: float = 120.0,
        max_retries: int = 2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max(0, max_retries)

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.3,
    ) -> Result[LLMResponse, Exception]:
        import asyncio

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {"Authorization": f"Bearer {self.api_key}"}

        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    if resp.status_code in (429, 502, 503, 504) and attempt < self.max_retries:
                        await asyncio.sleep(0.5 * (2**attempt))
                        continue
                    if resp.status_code != 200:
                        return Err(
                            RuntimeError(
                                f"HTTP {resp.status_code} from LLM endpoint ({self.base_url}): {resp.text}"
                            )
                        )
                    data = resp.json()

                if "choices" not in data or not data["choices"]:
                    return Err(RuntimeError(f"LLM returned empty choices: {data}"))

                choice = data["choices"][0]
                msg = choice.get("message", {})
                content = msg.get("content")

                tool_calls: List[ToolCall] = []
                for tc in msg.get("tool_calls", []):
                    fn = tc.get("function", {})
                    name = fn.get("name", "")
                    raw_args = fn.get("arguments", "{}")
                    if isinstance(raw_args, dict):
                        args = raw_args
                    else:
                        try:
                            args = json.loads(raw_args)
                        except Exception:
                            args = {}
                    tool_calls.append(
                        ToolCall(id=tc.get("id", f"call_{name}"), name=name, arguments=args)
                    )

                return Ok(LLMResponse(content=content, tool_calls=tool_calls, raw=data))

            except (httpx.ConnectError, httpx.ConnectTimeout):
                last_exc = RuntimeError(
                    f"Cannot connect to LLM at '{self.base_url}'. "
                    f"Ensure Ollama/vLLM is running ('ollama serve') or set FIREFLY_LLM_BASE_URL."
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
            except Exception as exc:
                last_exc = exc
                if attempt < self.max_retries and isinstance(
                    exc, (httpx.TimeoutException, httpx.NetworkError)
                ):
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                break

        return Err(last_exc or RuntimeError("LLM request failed after retries"))


class MockLLMProvider(LLMProvider):
    """Deterministic, mockable LLM provider for tests and offline simulation."""

    def __init__(self, responses: Optional[List[LLMResponse]] = None) -> None:
        self.queue: List[LLMResponse] = list(responses or [])
        self.call_history: List[List[Dict[str, Any]]] = []
        self.handler: Optional[Callable[[List[Dict[str, Any]]], LLMResponse]] = None

    def enqueue(self, response: LLMResponse) -> None:
        self.queue.append(response)

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.3,
    ) -> Result[LLMResponse, Exception]:
        self.call_history.append(messages)
        if self.handler:
            return Ok(self.handler(messages))
        if self.queue:
            return Ok(self.queue.pop(0))
        return Ok(LLMResponse(content="*chirp* Mock response."))
