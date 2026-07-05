"""Slack integration. Falls back to a console-printed mock if no bot
token is configured, so the demo works without real Slack app review."""

from config import settings


def send_slack_message(channel: str, text: str) -> dict:
    if not settings.SLACK_BOT_TOKEN:
        print(f"[MOCK SLACK -> {channel}] {text}")
        return {"ok": True, "mocked": True}

    import httpx

    response = httpx.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}"},
        json={"channel": channel, "text": text},
    )
    return response.json()
