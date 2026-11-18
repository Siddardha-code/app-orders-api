from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


class FakeRepo:
    def __init__(self):
        self.orders = {}
        self.next_id = 1
        self.healthy = True

    def create(self, item, quantity):
        order = {
            "id": self.next_id,
            "item": item,
            "quantity": quantity,
            "created_at": datetime.now(timezone.utc),
        }
        self.orders[self.next_id] = order
        self.next_id += 1
        return order

    def get(self, order_id):
        return self.orders.get(order_id)

    def list_orders(self, limit=50):
        return list(self.orders.values())[:limit]

    def ping(self):
        if not self.healthy:
            raise RuntimeError("db down")
        return True


@pytest.fixture
def repo():
    return FakeRepo()


@pytest.fixture
def client(repo):
    with TestClient(create_app(repo)) as c:
        yield c


def test_healthz(client):
    assert client.get("/healthz").status_code == 200


def test_readyz_ok(client):
    assert client.get("/readyz").status_code == 200


def test_readyz_unavailable(client, repo):
    repo.healthy = False
    assert client.get("/readyz").status_code == 503


def test_create_and_get(client):
    r = client.post("/orders", json={"item": "book", "quantity": 2})
    assert r.status_code == 201
    order_id = r.json()["id"]
    g = client.get(f"/orders/{order_id}")
    assert g.status_code == 200
    assert g.json()["item"] == "book"


def test_list_orders(client):
    client.post("/orders", json={"item": "pen", "quantity": 1})
    client.post("/orders", json={"item": "ink", "quantity": 3})
    r = client.get("/orders")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_rejects_invalid_quantity(client):
    r = client.post("/orders", json={"item": "book", "quantity": 0})
    assert r.status_code == 422


def test_missing_order_returns_404(client):
    assert client.get("/orders/999").status_code == 404


def test_metrics_use_route_template(client):
    r = client.post("/orders", json={"item": "book", "quantity": 1})
    order_id = r.json()["id"]
    client.get(f"/orders/{order_id}")
    body = client.get("/metrics").text
    assert 'path="/orders/{order_id}"' in body
    assert f'path="/orders/{order_id}"' not in body
    assert "http_request_duration_seconds_bucket" in body
