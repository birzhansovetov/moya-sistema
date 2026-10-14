from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from conftest import Mailbox


def sign_in(client: TestClient, mailbox: Mailbox, email: str) -> str:
    assert client.post("/api/auth/register", json={"email": email}).status_code == 202
    link = next(part for part in mailbox.messages[-1].text.split() if part.startswith("https://"))
    token = parse_qs(urlparse(link).fragment)["token"][0]
    assert client.post("/api/auth/verify", json={"token": token, "password": "correct horse battery staple"}).status_code == 204
    response = client.post("/api/auth/login", json={"email": email, "password": "correct horse battery staple"})
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_sphere_preferences_are_private_and_do_not_change_task_sections(client: TestClient, mailbox: Mailbox) -> None:
    csrf = sign_in(client, mailbox, "one@example.com")
    assert client.get("/api/profile/spheres").json() == {"hidden_spheres": []}
    assert client.patch("/api/profile/spheres", json={"hidden_spheres": ["finance"]}).status_code == 403
    saved = client.patch(
        "/api/profile/spheres", json={"hidden_spheres": ["finance"]}, headers={"X-CSRF-Token": csrf}
    )
    assert saved.status_code == 200
    assert client.get("/api/profile/spheres").json() == {"hidden_spheres": ["finance"]}
    assert client.get("/api/profile/sections").json() == {"hidden_sections": []}
    sign_in(client, mailbox, "two@example.com")
    assert client.get("/api/profile/spheres").json() == {"hidden_spheres": []}


def test_sphere_preferences_reject_unknown_and_duplicate_values(client: TestClient, mailbox: Mailbox) -> None:
    csrf = sign_in(client, mailbox, "one@example.com")
    headers = {"X-CSRF-Token": csrf}
    assert client.patch("/api/profile/spheres", json={"hidden_spheres": ["other"]}, headers=headers).status_code == 422
    assert client.patch("/api/profile/spheres", json={"hidden_spheres": ["health", "health"]}, headers=headers).status_code == 422
    assert client.get("/api/profile/spheres").json() == {"hidden_spheres": []}
