import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")

    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")

    # --- Ollama / Qwen (local testing only) ---
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3:8b")

    LLM_MODEL: str = os.getenv("LLM_MODEL", "")
    ALLOW_LLM_FALLBACKS: bool = os.getenv("ALLOW_LLM_FALLBACKS", "false").lower() == "true"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./threshold.db")
    SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_DEFAULT_CHANNEL: str = os.getenv("SLACK_DEFAULT_CHANNEL", "#deal-approvals")

    EMAIL_API_KEY: str = os.getenv("EMAIL_API_KEY", "")
    APP_ENV: str = os.getenv("APP_ENV", "development")


settings = Settings()
