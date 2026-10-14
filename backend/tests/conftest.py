from dataclasses import dataclass, field
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Base
from app.main import create_app


@dataclass
class CapturedMail:
    to: str
    subject: str
    text: str


@dataclass
class Mailbox:
    messages: list[CapturedMail] = field(default_factory=list)

    def send(self, to: str, subject: str, text: str) -> None:
        self.messages.append(CapturedMail(to=to, subject=subject, text=text))


@pytest.fixture
def mailbox() -> Mailbox:
    return Mailbox()


@pytest.fixture
def client(tmp_path: Path, mailbox: Mailbox) -> TestClient:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        jwt_secret="test-secret-with-at-least-thirty-two-characters",
        frontend_origin="https://testserver",
        environment="test",
    )
    app = create_app(settings=settings, mailer=mailbox)
    Base.metadata.create_all(app.state.engine)
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client
