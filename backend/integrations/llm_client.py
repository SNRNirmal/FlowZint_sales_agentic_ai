"""Thin wrapper around the Anthropic API so every agent calls the LLM
the same way. Keep prompts in the calling agent, not here."""

from anthropic import Anthropic
from config import settings

_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 1000) -> str:
    response = _client.messages.create(
        model=settings.LLM_MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")
