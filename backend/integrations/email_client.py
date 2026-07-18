from config import settings

def send_email(to: str, subject: str, body: str) -> dict:
    """Send an email nudge.

    Falls back to a console-printed mock if no EMAIL_API_KEY is configured,
    so the demo works without a real email provider configured. When
    EMAIL_API_KEY is present, wire in a real provider here.
    """
    if not getattr(settings, "EMAIL_API_KEY", ""):
        print(f"[MOCK EMAIL -> {to}] Subject: {subject}\n{body}")
        return {"ok": True, "mocked": True}

    # TODO: Replace with a real provider when EMAIL_API_KEY is configured.
    # Example (SendGrid):
    #   import httpx
    #   response = httpx.post(
    #       "https://api.sendgrid.com/v3/mail/send",
    #       headers={"Authorization": f"Bearer {settings.EMAIL_API_KEY}"},
    #       json={"personalizations": [{"to": [{"email": to}]}],
    #             "from": {"email": "threshold@yourcompany.com"},
    #             "subject": subject,
    #             "content": [{"type": "text/plain", "value": body}]},
    #   )
    #   return {"ok": response.status_code == 202}
    print(f"[MOCK EMAIL -> {to}] Subject: {subject}\n{body}")
    return {"ok": True, "mocked": True}
