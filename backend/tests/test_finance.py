from datetime import datetime, timezone

from conftest import Mailbox
from fastapi.testclient import TestClient
from test_spheres import sign_in


def setup_finance(client, mailbox, email="finance@example.com"):
    headers = {"X-CSRF-Token": sign_in(client, mailbox, email)}
    response = client.get("/api/finance/categories")
    assert response.status_code == 200
    return headers, response.json()["items"]


def expense(initial_category, **changes):
    data = {"amount": "10.10", "currency": "KZT", "category_id": initial_category, "date": "2026-02-28", "note": " Продукты домой ", "create_key": "purchase-1"}
    return {**data, **changes}


def test_first_category_write_commits_defaults_and_custom_item_together(client: TestClient, mailbox: Mailbox):
    headers = {"X-CSRF-Token": sign_in(client, mailbox, "fresh-finance@example.com")}
    response = client.post("/api/finance/categories", json={"name": "Книги"}, headers=headers)
    assert response.status_code == 201
    items = client.get("/api/finance/categories").json()["items"]
    assert len(items) == 9
    assert sum(item["name"] == "Книги" for item in items) == 1


def test_finance_categories_settings_and_writes_are_private(client: TestClient, mailbox: Mailbox):
    assert client.get("/api/finance/categories").status_code == 401
    headers, categories = setup_finance(client, mailbox)
    assert len(categories) == 8
    assert client.get("/api/finance/settings").json()["currency"] == "KZT"
    assert client.patch("/api/finance/settings", json={"currency": "USD"}, headers=headers).status_code == 200
    assert client.patch("/api/finance/settings", json={"currency": "XXX"}, headers=headers).status_code == 422
    assert client.post("/api/finance/categories", json={"name": "Книги"}).status_code == 403
    custom = client.post("/api/finance/categories", json={"name": "Книги"}, headers=headers)
    assert custom.status_code == 201
    assert client.post("/api/finance/categories", json={"name": " книги "}, headers=headers).status_code == 409
    renamed = client.patch(f'/api/finance/categories/{custom.json()["id"]}', json={"name": "Чтение"}, headers=headers)
    assert renamed.json()["name"] == "Чтение"
    assert client.post("/api/finance/expenses", json=expense(categories[0]["id"])).status_code == 403
    saved = client.post("/api/finance/expenses", json=expense(custom.json()["id"]), headers=headers).json()
    other_headers, other_categories = setup_finance(client, mailbox, "other@example.com")
    assert set(item["id"] for item in categories).isdisjoint(item["id"] for item in other_categories)
    assert client.get("/api/finance/settings").json()["currency"] == "KZT"
    assert client.get("/api/finance/expenses?start=2026-02-01&end=2026-02-28&currency=KZT").json()["total"] == 0
    assert client.post("/api/finance/expenses", json=expense(custom.json()["id"]), headers=other_headers).status_code == 404
    assert client.patch(f'/api/finance/categories/{custom.json()["id"]}', json={"name": "Чужое"}, headers=other_headers).status_code == 404
    for method, suffix, body in [("PATCH", "", {"amount": "20.00", "currency": "KZT", "category_id": other_categories[0]["id"], "date": "2026-02-28", "note": ""}), ("DELETE", "", None), ("POST", "/restore", None)]:
        assert client.request(method, f'/api/finance/expenses/{saved["id"]}{suffix}', json=body, headers=other_headers).status_code == 404


def test_expense_retry_edit_search_delete_restore_and_paging(client: TestClient, mailbox: Mailbox):
    headers, categories = setup_finance(client, mailbox)
    payload = expense(categories[0]["id"])
    first = client.post("/api/finance/expenses", json=payload, headers=headers)
    assert first.status_code == 201
    item = first.json()
    assert item["amount"] == "10.10" and item["note"] == "Продукты домой"
    assert client.post("/api/finance/expenses", json=payload, headers=headers).json()["id"] == item["id"]
    assert client.post("/api/finance/expenses", json={**payload, "amount": "11.00"}, headers=headers).status_code == 409
    update = {key: value for key, value in payload.items() if key != "create_key"}
    changed = client.patch(f'/api/finance/expenses/{item["id"]}', json={**update, "amount": "20.20", "note": "Молоко"}, headers=headers)
    assert changed.json()["amount"] == "20.20"
    assert client.post("/api/finance/expenses", json=payload, headers=headers).json()["id"] == item["id"]
    base = "/api/finance/expenses?start=2026-02-01&end=2026-02-28&currency=KZT"
    assert client.get(base + "&q=МОЛОКО").json()["items"][0]["id"] == item["id"]
    assert client.get(base + "&q=нет").json()["total"] == 0
    second = client.post("/api/finance/expenses", json=expense(categories[1]["id"], create_key="second", amount="0.10", note="Чай"), headers=headers).json()
    assert client.get(base + "&limit=1").json()["total"] == 2
    assert len(client.get(base + "&limit=1&offset=1").json()["items"]) == 1
    assert client.get(base + f'&category_id={categories[0]["id"]}').json()["total"] == 1
    assert client.get("/api/finance/summary?month=2026-02&currency=KZT").json()["month_total"] == "20.30"
    assert client.delete(f'/api/finance/expenses/{item["id"]}', headers=headers).status_code == 204
    assert client.get(base).json()["total"] == 1
    assert client.get(base + "&deleted=true").json()["items"][0]["id"] == item["id"]
    assert client.get("/api/finance/summary?month=2026-02&currency=KZT").json()["month_total"] == "0.10"
    assert client.post(f'/api/finance/expenses/{item["id"]}/restore', headers=headers).status_code == 200
    assert client.get(base).json()["total"] == 2
    assert second["id"] != item["id"]


def test_summary_separates_currency_and_uses_user_local_day_and_week(client: TestClient, mailbox: Mailbox, monkeypatch):
    headers, categories = setup_finance(client, mailbox)
    from app.routes import finance

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 3, 1, 20, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(finance, "datetime", Clock)
    for index, (day, amount, currency) in enumerate([("2026-02-28", "10.10", "KZT"), ("2026-03-01", "20.20", "KZT"), ("2026-03-02", "30.30", "KZT"), ("2026-03-02", "99.99", "USD")]):
        assert client.post("/api/finance/expenses", json=expense(categories[0]["id"], date=day, amount=amount, currency=currency, create_key=str(index)), headers=headers).status_code == 201
    summary = client.get("/api/finance/summary?month=2026-03&currency=KZT").json()
    assert summary["today"] == "2026-03-02"
    assert summary["today_total"] == "30.30"
    assert summary["week_start"] == "2026-03-02" and summary["week_total"] == "30.30"
    assert summary["month_total"] == "50.50"
    assert summary["categories"][0]["amount"] == "50.50"
    assert client.get("/api/finance/summary?month=2026-03&currency=USD").json()["month_total"] == "99.99"
    client.patch("/api/finance/settings", json={"currency": "USD"}, headers=headers)
    assert client.get("/api/finance/summary?month=2026-03&currency=KZT").json()["month_total"] == "50.50"
    client.patch("/api/profile", json={"timezone": "America/Los_Angeles"}, headers=headers)
    summary = client.get("/api/finance/summary?month=2026-03&currency=KZT").json()
    assert summary["today"] == "2026-03-01" and summary["today_total"] == "20.20"
    assert summary["week_start"] == "2026-02-23" and summary["week_total"] == "30.30"


def test_finance_rejects_invalid_amounts_dates_and_filters(client: TestClient, mailbox: Mailbox):
    headers, categories = setup_finance(client, mailbox)
    for amount in ["0", "-1", "1.001", "NaN", "Infinity", "10000000000.00"]:
        assert client.post("/api/finance/expenses", json=expense(categories[0]["id"], amount=amount), headers=headers).status_code == 422
    for change in [{"date": "9999-01-01"}, {"currency": "XYZ"}, {"category_id": "missing"}, {"create_key": ""}]:
        assert client.post("/api/finance/expenses", json=expense(categories[0]["id"], **change), headers=headers).status_code in [404, 422]
    assert client.get("/api/finance/summary?month=2026-13&currency=KZT").status_code == 422
    assert client.get("/api/finance/expenses?start=2026-03-01&end=2026-02-01&currency=KZT").status_code == 422
    assert client.get("/api/finance/expenses?limit=0&currency=KZT").status_code == 422
