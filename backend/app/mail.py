import base64
from email.message import EmailMessage
import os
from typing import Protocol

import httpx


class Mailer(Protocol):
    def send(self, to: str, subject: str, text: str) -> None: ...


class GmailMailer:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str, sender: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.sender = sender

    @classmethod
    def from_env(cls) -> "GmailMailer":
        return cls(
            client_id=os.environ["GMAIL_CLIENT_ID"],
            client_secret=os.environ["GMAIL_CLIENT_SECRET"],
            refresh_token=os.environ["GMAIL_REFRESH_TOKEN"],
            sender=os.environ["GMAIL_SENDER"],
        )

    def send(self, to: str, subject: str, text: str) -> None:
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = to
        message["Subject"] = subject
        message.set_content(text)
        encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        with httpx.Client(timeout=12) as client:
            token_response = client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            token_response.raise_for_status()
            access_token = token_response.json()["access_token"]
            send_response = client.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"raw": encoded},
            )
            send_response.raise_for_status()
