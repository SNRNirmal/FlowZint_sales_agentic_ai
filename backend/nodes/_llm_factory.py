from __future__ import annotations

import json
import re
import textwrap

from config import settings

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-6",
    "gemini": "gemini-1.5-flash",
    "qwen": None,
}


def resolve_provider() -> str:
    if settings.LLM_PROVIDER:
        return settings.LLM_PROVIDER.lower()

    if settings.GOOGLE_API_KEY and not settings.ANTHROPIC_API_KEY:
        return "gemini"

    return "anthropic"


class _QwenStructuredWrapper:
    """
    Replacement for with_structured_output() when using Ollama/Qwen.
    """

    _FENCE_RE = re.compile(
        r"```(?:json)?\s*(.*?)\s*```",
        re.DOTALL,
    )

    def __init__(self, llm, schema):
        self._llm = llm
        self._schema = schema

        try:
            schema_text = json.dumps(
                schema.model_json_schema(),
                indent=2,
            )
        except Exception:
            schema_text = "(schema unavailable)"

        self._system_prompt = textwrap.dedent(
            f"""
            You are a data extraction assistant.

            Return ONLY a valid JSON object.

            Rules:

            - No markdown.
            - No explanations.
            - No code fences.
            - No <think> tags.
            - No extra text.

            JSON schema:

            {schema_text}
            """
        )

    def _build_messages(self, messages):
        from langchain_core.messages import (
            HumanMessage,
            SystemMessage,
        )

        system_message = SystemMessage(
            content=self._system_prompt
        )

        # Case 1: caller passed a string
        if isinstance(messages, str):
            return [
                system_message,
                HumanMessage(content=messages),
            ]

        # Case 2: caller passed LangChain messages
        messages = list(messages)

        if (
            messages
            and getattr(messages[0], "type", None)
            == "system"
        ):
            return [system_message] + messages[1:]

        return [system_message] + messages

    def _parse(self, raw_text: str):
        text = raw_text.strip()

        fence_match = self._FENCE_RE.search(text)

        if fence_match:
            text = fence_match.group(1).strip()

        text = re.sub(
            r"<think>.*?</think>",
            "",
            text,
            flags=re.DOTALL,
        ).strip()

        try:
            return self._schema.model_validate_json(text)

        except Exception as exc:
            raise ValueError(
                f"""
Failed to parse Qwen output.

Raw output:

{raw_text}

Parse error:

{exc}
"""
            ) from exc

    async def ainvoke(self, messages, **kwargs):
        augmented = self._build_messages(messages)

        print("\n=== DEBUG MESSAGES ===")
        print(augmented)
        print("======================\n")

        try:
            response = await self._llm.ainvoke(
                augmented,
                **kwargs,
            )

            print("\n=== RESPONSE TYPE ===")
            print(type(response))
            print("=====================\n")

            print("\n=== RAW RESPONSE ===")
            print(repr(response))
            print("====================\n")

            return self._parse(response.content)

        except Exception as e:
            print("\n=== EXCEPTION ===")
            print(type(e).__name__)
            print(str(e))
            print("=================\n")
            raise

def make_structured_llm(schema, max_tokens: int):
    provider = resolve_provider()

    if provider not in DEFAULT_MODELS:
        raise ValueError(
            f"Unknown provider: {provider}"
        )

    model = settings.LLM_MODEL or DEFAULT_MODELS[provider]

    if provider == "gemini":
        from langchain_google_genai import (
            ChatGoogleGenerativeAI,
        )

        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.GOOGLE_API_KEY,
            max_output_tokens=max_tokens,
        ).with_structured_output(schema)

    if provider == "qwen":
        from langchain_openai import ChatOpenAI

        raw_llm = ChatOpenAI(
            base_url=settings.OLLAMA_BASE_URL,
            api_key="ollama",
            model=settings.OLLAMA_MODEL,
            temperature=0,
            max_tokens=max_tokens,
        )

        return _QwenStructuredWrapper(
            raw_llm,
            schema,
        )

    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=model,
        api_key=settings.ANTHROPIC_API_KEY,
        max_tokens=max_tokens,
    ).with_structured_output(schema)