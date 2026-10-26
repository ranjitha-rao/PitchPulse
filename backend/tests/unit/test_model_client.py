"""The Azure OpenAI client against a fake HTTP transport: chat and reasoning models, retries, failure reasons."""

import asyncio
import json

import httpx
import pytest

from pitchpulse.agents import Newsroom
from pitchpulse.narrate import ModelNarrator
from pitchpulse.personalize import Profile

from ..conftest import first


def reply(text=None, finish="stop"):
    content = json.dumps({"text": text, "cited": []}) if text is not None else ""
    return httpx.Response(200, json={"choices": [{"message": {"content": content}, "finish_reason": finish}]})


def narrator(monkeypatch, deployment, *responses):
    """A narrator whose HTTP calls get the scripted responses in turn; returns (narrator, request bodies)."""
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", deployment)
    bodies, queue = [], list(responses)

    def handle(request):
        bodies.append(json.loads(request.content))
        return queue.pop(0)

    n = ModelNarrator()
    n.client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    return n, bodies


def run(coro):
    return asyncio.run(coro)


def moment():
    return {"type": "goal", "minute": 64, "facts": [{"id": "wp_after", "value": 7}], "drivers": [], "storyline": None}


def test_chat_model_gets_temperature(monkeypatch):
    n, bodies = narrator(monkeypatch, "gpt-4o-mini", reply("Goal!"))
    assert run(n.draft(moment(), "casual", "en"))["text"] == "Goal!"
    assert bodies[0]["temperature"] == 0.6 and bodies[0]["max_completion_tokens"] >= 1000
    assert "max_tokens" not in bodies[0]


@pytest.mark.parametrize("deployment", ["gpt-5-mini", "GPT-5", "o4-mini"])
def test_reasoning_models_get_no_temperature(monkeypatch, deployment):
    n, bodies = narrator(monkeypatch, deployment, reply("Goal!"))
    assert run(n.draft(moment(), "casual", "en"))["text"] == "Goal!"
    assert "temperature" not in bodies[0]


def test_temperature_dropped_when_the_service_rejects_it(monkeypatch):
    bad = httpx.Response(400, json={"error": {"message": "Unsupported value: 'temperature' does not support 0.6"}})
    n, bodies = narrator(monkeypatch, "my-model", bad, reply("Goal!"), reply("Again!"))
    assert run(n.draft(moment(), "casual", "en"))["text"] == "Goal!"
    assert "temperature" in bodies[0] and "temperature" not in bodies[1]
    run(n.draft(moment(), "casual", "en"))
    assert "temperature" not in bodies[2]


def test_rate_limit_waits_and_retries_once(monkeypatch):
    busy = httpx.Response(429, headers={"retry-after": "0"}, json={"error": {"message": "Too many requests"}})
    n, _ = narrator(monkeypatch, "gpt-5-mini", busy, reply("Goal!"))
    assert run(n.draft(moment(), "casual", "en"))["text"] == "Goal!"
    n, _ = narrator(monkeypatch, "gpt-5-mini", busy, busy)
    assert run(n.draft(moment(), "casual", "en"))["error"].startswith("rate limited (429)")


@pytest.mark.parametrize("response, reason", [
    (httpx.Response(404, json={"error": {"message": "DeploymentNotFound"}}), "deployment or endpoint not found (404)"),
    (httpx.Response(401, json={"error": {"message": "Access denied"}}), "key refused (401)"),
    (reply(finish="length"), "empty reply (finish_reason: length)"),
    (httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]}), "reply was not JSON"),
])
def test_failures_carry_a_reason(monkeypatch, response, reason):
    n, _ = narrator(monkeypatch, "gpt-5-mini", response)
    out = run(n.draft(moment(), "casual", "en"))
    assert reason in out["error"]
    assert run(narrator(monkeypatch, "gpt-5-mini", response)[0].caption(moment(), "casual", "en")) is None


def test_trace_shows_why_the_draft_failed(monkeypatch, moments, engine):
    n, _ = narrator(monkeypatch, "gpt-5-mini", httpx.Response(404, json={"error": {"message": "DeploymentNotFound"}}))
    room = Newsroom(n)
    cue, brief = room.on_air([first(moments, "goal")], engine, Profile(), ["en"])[0]
    out = run(room.rewrite(cue, brief, Profile()))
    assert out["version"] == 1
    assert "deployment or endpoint not found (404)" in out["trace"][-2]["detail"]
