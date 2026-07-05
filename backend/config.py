import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "claude-sonnet-4-6")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./threshold.db")
    SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_DEFAULT_CHANNEL: str = os.getenv("SLACK_DEFAULT_CHANNEL", "#deal-approvals")
    APP_ENV: str = os.getenv("APP_ENV", "development")


settings = Settings()
