from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from conftest import Mailbox


def extract_token(mailbox: Mailbox) -> str:
    link = next(part for part in mailbox.messages[-1].text.split() if part.startswith("https://"))
    return parse_qs(urlparse(link).fragment)["token"][0]


def verified_user(client: TestClient, mailbox: Mailbox, email: str = "one@example.com") -> None:
    response = client.post("/api/auth/register", json={"email": email})
    assert response.status_code == 202
    token = extract_token(mailbox)
    assert client.post("/api/auth/verify", json={"token": token, "password": "correct horse battery staple"}).status_code == 204


def test_email_verification_is_one_time(client: TestClient, mailbox: Mailbox) -> None:
    assert client.post(
        "/api/auth/register", json={"email": "one@example.com"}
    ).status_code == 202
    token = extract_token(mailbox)
    assert client.post("/api/auth/verify", json={"token": token, "password": "correct horse battery staple"}).status_code == 204
    repeated = client.post("/api/auth/verify", json={"token": token, "password": "different password value"})
    assert repeated.status_code == 409
    assert repeated.json()["detail"] == "Адрес уже подтверждён. Войдите с ранее сохранённым паролем."
    assert client.post("/api/auth/login", json={"email": "one@example.com", "password": "correct horse battery staple"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "one@example.com", "password": "different password value"}).status_code == 401


def test_address_owner_sets_password_after_competing_registration(client: TestClient, mailbox: Mailbox) -> None:
    email = "owner@example.com"
    attacker_password = "attacker password value"
    owner_password = "owner password value"
    assert client.post("/api/auth/register", json={"email": email}).status_code == 202
    assert client.post("/api/auth/register", json={"email": email}).status_code == 202
    token = extract_token(mailbox)
    assert client.post("/api/auth/verify", json={"token": token, "password": owner_password}).status_code == 204
    assert client.post("/api/auth/login", json={"email": email, "password": attacker_password}).status_code == 401
    assert client.post("/api/auth/login", json={"email": email, "password": owner_password}).status_code == 200


def test_login_uses_httponly_cookies_and_logout_revokes_old_access_token(
    client: TestClient, mailbox: Mailbox
) -> None:
    verified_user(client, mailbox)
    login = client.post(
        "/api/auth/login", json={"email": "one@example.com", "password": "correct horse battery staple"}
    )
    assert login.status_code == 200
    cookie_headers = login.headers.get_list("set-cookie")
    assert len(cookie_headers) == 2
    assert all("httponly" in value.lower() and "secure" in value.lower() for value in cookie_headers)
    old_access = client.cookies["__Host-access"]
    assert client.get("/api/auth/me").status_code == 200
    csrf = login.json()["csrf_token"]
    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
    assert client.get("/api/auth/me", cookies={"__Host-access": old_access}).status_code == 401


def test_refresh_rotates_token_and_old_token_cannot_be_reused(client: TestClient, mailbox: Mailbox) -> None:
    verified_user(client, mailbox)
    login = client.post(
        "/api/auth/login", json={"email": "one@example.com", "password": "correct horse battery staple"}
    )
    old_refresh = client.cookies["__Host-refresh"]
    csrf = login.json()["csrf_token"]
    assert client.post("/api/auth/refresh", headers={"X-CSRF-Token": csrf}).status_code == 200
    assert client.cookies["__Host-refresh"] != old_refresh
    assert client.post(
        "/api/auth/refresh", headers={"X-CSRF-Token": csrf}, cookies={"__Host-refresh": old_refresh}
    ).status_code == 401


def test_refresh_recovers_after_page_reload_without_csrf_in_memory(client: TestClient, mailbox: Mailbox) -> None:
    verified_user(client, mailbox)
    assert client.post("/api/auth/login", json={"email": "one@example.com", "password": "correct horse battery staple"}).status_code == 200
    client.cookies.pop("__Host-access")
    assert client.post("/api/auth/refresh").status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_registration_can_retry_after_email_delivery_failure(client: TestClient, mailbox: Mailbox, monkeypatch) -> None:
    original_send = mailbox.send
    def fail(*_args):
        raise RuntimeError("mail unavailable")
    monkeypatch.setattr(mailbox, "send", fail)
    payload = {"email": "one@example.com"}
    assert client.post("/api/auth/register", json=payload).status_code == 503
    monkeypatch.setattr(mailbox, "send", original_send)
    assert client.post("/api/auth/register", json=payload).status_code == 202
    assert len(mailbox.messages) == 1
    assert client.post("/api/auth/verify", json={"token": extract_token(mailbox), "password": "correct horse battery staple"}).status_code == 204


def test_profile_update_requires_csrf_and_persists(client: TestClient, mailbox: Mailbox) -> None:
    verified_user(client, mailbox)
    login = client.post(
        "/api/auth/login", json={"email": "one@example.com", "password": "correct horse battery staple"}
    )
    profile = {"name": "Айжан", "timezone": "Asia/Almaty"}
    assert client.patch("/api/profile", json=profile).status_code == 403
    saved = client.patch("/api/profile", json=profile, headers={"X-CSRF-Token": login.json()["csrf_token"]})
    assert saved.status_code == 200
    assert client.get("/api/profile").json()["name"] == "Айжан"


def test_hidden_sections_are_private_and_persist(client: TestClient, mailbox: Mailbox) -> None:
    verified_user(client, mailbox)
    login = client.post("/api/auth/login", json={"email": "one@example.com", "password": "correct horse battery staple"})
    csrf = login.json()["csrf_token"]
    assert client.patch("/api/profile/sections", json={"hidden_sections": ["finance", "work"]}).status_code == 403
    assert client.patch("/api/profile/sections", json={"hidden_sections": ["finance", "work"]}, headers={"X-CSRF-Token": csrf}).status_code == 200
    assert client.get("/api/profile/sections").json()["hidden_sections"] == ["finance", "work"]
    verified_user(client, mailbox, "two@example.com")
    client.post("/api/auth/login", json={"email": "two@example.com", "password": "correct horse battery staple"})
    assert client.get("/api/profile/sections").json()["hidden_sections"] == []


def test_password_reset_revokes_sessions(client: TestClient, mailbox: Mailbox) -> None:
    verified_user(client, mailbox)
    assert client.post(
        "/api/auth/login", json={"email": "one@example.com", "password": "correct horse battery staple"}
    ).status_code == 200
    old_access = client.cookies["__Host-access"]
    assert client.post("/api/auth/password-reset/request", json={"email": "one@example.com"}).status_code == 202
    token = extract_token(mailbox)
    assert client.post(
        "/api/auth/password-reset/confirm", json={"token": token, "password": "new secret with enough length"}
    ).status_code == 204
    assert client.get("/api/auth/me", cookies={"__Host-access": old_access}).status_code == 401
    assert client.post(
        "/api/auth/login", json={"email": "one@example.com", "password": "correct horse battery staple"}
    ).status_code == 401
    assert client.post(
        "/api/auth/login", json={"email": "one@example.com", "password": "new secret with enough length"}
    ).status_code == 200


def test_repeated_wrong_password_is_limited(client: TestClient, mailbox: Mailbox) -> None:
    verified_user(client, mailbox)
    for _ in range(10):
        assert client.post("/api/auth/login", json={"email": "one@example.com", "password": "incorrect password value"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "one@example.com", "password": "correct horse battery staple"}).status_code == 429


def test_password_reset_requests_are_limited_even_for_unknown_email(client: TestClient) -> None:
    for _ in range(5):
        assert client.post("/api/auth/password-reset/request", json={"email": "missing@example.com"}).status_code == 202
    assert client.post("/api/auth/password-reset/request", json={"email": "missing@example.com"}).status_code == 429
