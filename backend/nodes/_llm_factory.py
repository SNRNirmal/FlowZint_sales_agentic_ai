"""Provider-agnostic construction of the structured-output LLM clients.

The three reasoning nodes (delay_intelligence, document_generator,
communication_planner) each keep their module-global ``_structured_llm``
singleton — that seam is what the test suite patches — but delegate
construction here, so switching providers is a config change
(LLM_PROVIDER / API keys in .env), not a code change.

Provider resolution:
  1. Explicit ``LLM_PROVIDER`` env var ("anthropic" or "gemini") wins.
  2. Otherwise inferred from which API key is set; Anthropic wins if both.

Provider packages are imported lazily inside their branch so a missing
optional dependency for the *unused* provider can never break startup.
"""

from __future__ import annotations

from config import settings

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-6",
    "gemini": "gemini-2.5-flash",
}


def resolve_provider() -> str:
    if settings.LLM_PROVIDER:
        return settings.LLM_PROVIDER.lower()
    if settings.GOOGLE_API_KEY and not settings.ANTHROPIC_API_KEY:
        return "gemini"
    return "anthropic"


def make_structured_llm(schema, max_tokens: int):
    """Build a chat model bound to ``schema`` via with_structured_output.

    Returns an object exposing ``async ainvoke(messages) -> schema`` —
    the only surface the nodes (and their test fakes) rely on.
    """
    provider = resolve_provider()
    if provider not in DEFAULT_MODELS:
        raise ValueError(
            f"Unknown LLM_PROVIDER {provider!r} — use 'anthropic' or 'gemini'."
        )
    model = settings.LLM_MODEL or DEFAULT_MODELS[provider]

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.GOOGLE_API_KEY,
            max_output_tokens=max_tokens,
        ).with_structured_output(schema)

    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=model,
        api_key=settings.ANTHROPIC_API_KEY,
        max_tokens=max_tokens,
    ).with_structured_output(schema)
