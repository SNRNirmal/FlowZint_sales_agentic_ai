import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    # "anthropic" | "gemini". Empty = inferred from which API key is set
    # (see nodes/_llm_factory.py); Anthropic wins if both are present.
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "")
    # Empty = provider default (claude-sonnet-4-6 / gemini-2.5-flash),
    # applied in nodes/_llm_factory.py.
    LLM_MODEL: str = os.getenv("LLM_MODEL", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./threshold.db")
    SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_DEFAULT_CHANNEL: str = os.getenv("SLACK_DEFAULT_CHANNEL", "#deal-approvals")
    APP_ENV: str = os.getenv("APP_ENV", "development")


settings = Settings()
