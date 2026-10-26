import json

import pytest
from fastapi.testclient import TestClient

import server


@pytest.fixture(scope="module")
def client():
    return TestClient(server.app)


class Socket:
    """Small helper over the test WebSocket: read until a message matches."""

    def __init__(self, ws):
        self.ws = ws

    def send(self, **msg):
        self.ws.send_text(json.dumps(msg))

    def until(self, pred, limit=5000):
        seen = []
        for _ in range(limit):
            msg = json.loads(self.ws.receive_text())
            seen.append(msg)
            if pred(msg):
                return msg, seen
        raise AssertionError(f"condition not met in {limit} messages")


@pytest.fixture
def socket(client):
    def open_(query="speed=60"):
        return client.websocket_connect(f"/ws/match?{query}")
    return open_
