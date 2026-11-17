"""A minimal client for any OpenAI-compatible chat API (Ollama, OpenAI, etc.).

Written with plain HTTP instead of an SDK so every step is visible.
"""

import json
import re
from typing import Protocol

from app.config import settings


class ChatModel(Protocol):
    """Anything with a `chat` method can be used by the agent (handy for tests)."""

    def chat(self, system: str, user: str) -> str: ...


class OpenAICompatibleLLM:
    def __init__(
        self,
        base_url: str = settings.llm_base_url,
        api_key: str = settings.llm_api_key,
        model: str = settings.llm_model,
        timeout: float = settings.llm_timeout,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def chat(self, system: str, user: str) -> str:
        import httpx

        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


def parse_json(text: str) -> dict:
    """Pull the first JSON object out of a model reply.

    Models often wrap JSON in ```json fences or add a sentence before it,
    so we look for the outermost {...} instead of trusting the whole reply.
    """
    text = re.sub(r"```(?:json)?", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("No JSON object found in model reply")
    return json.loads(text[start : end + 1])


def chat_json(llm: ChatModel, system: str, user: str, retries: int = 1) -> dict:
    """Ask for JSON; if the reply is not valid JSON, ask once more."""
    reply = llm.chat(system, user)
    for attempt in range(retries + 1):
        try:
            return parse_json(reply)
        except (ValueError, json.JSONDecodeError):
            if attempt == retries:
                raise
            reply = llm.chat(
                system,
                user + "\n\nYour previous reply was not valid JSON. Reply with JSON only.",
            )
    return {}  # unreachable, keeps type checkers happy
