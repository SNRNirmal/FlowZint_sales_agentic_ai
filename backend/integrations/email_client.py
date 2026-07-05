"""Email integration stub. Mocked for the hackathon build — swap in a
real provider (SendGrid, SES, Gmail API) post-hackathon."""


def send_email(to: str, subject: str, body: str) -> dict:
    print(f"[MOCK EMAIL -> {to}] Subject: {subject}\n{body}")
    return {"ok": True, "mocked": True}
