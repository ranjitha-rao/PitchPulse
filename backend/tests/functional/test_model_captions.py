"""Model captions are only shipped when every number in them is grounded."""

import asyncio

import pytest

import server
from pitchpulse.narrate import ModelNarrator

from .conftest import Socket


class FakeNarrator(ModelNarrator):
    def __init__(self, reply):
        super().__init__()
        self.enabled = True
        self.reply = reply
        self.calls = []

    async def _chat(self, system, user):
        self.calls.append((system, user))
        return self.reply(user)


def goal_moment():
    return {
        "type": "goal", "minute": 64, "storyline": "comeback", "drivers": ["wp_before", "wp_after"],
        "facts": [{"id": "scorer", "value": "Samir Haddad"}, {"id": "wp_before", "value": 1},
                  {"id": "wp_after", "value": 6}, {"id": "shot_speed", "value": 100}],
    }


def run(coro):
    return asyncio.run(coro)


def test_grounded_caption_is_accepted():
    n = FakeNarrator(lambda _: {"text": "Haddad smashes it in at 100 km/h in the 64th minute!", "cited": ["shot_speed"]})
    out = run(n.caption(goal_moment(), "casual", "en"))
    assert out == {"text": "Haddad smashes it in at 100 km/h in the 64th minute!", "cited": ["shot_speed"]}
    system, _ = n.calls[0]
    assert "ONLY the facts" in system and "English" in system


@pytest.mark.parametrize("reply", [
    {"text": "Haddad scores from 25 yards at 112 km/h!"},
    {"text": 42},
    {},
    None,
])
def test_ungrounded_or_broken_replies_are_rejected(reply):
    n = FakeNarrator(lambda _: reply)
    assert run(n.caption(goal_moment(), "analyst", "es")) is None


def test_prompt_names_language_and_followed_player():
    n = FakeNarrator(lambda _: {"text": "ok"})
    run(n.caption(goal_moment(), "casual", "ar", focus="hfc_08"))
    system, user = n.calls[0]
    assert "Arabic" in system and "Daniel Okafor" in user


def test_disabled_narrator_makes_no_calls():
    n = ModelNarrator()
    assert n.enabled is False
    assert run(n.caption(goal_moment(), "casual", "en")) is None


def test_websocket_upgrades_cues_to_version_2(socket, monkeypatch):
    fake = FakeNarrator(lambda _: {"text": "Grounded words only.", "cited": []})
    monkeypatch.setattr(server, "narrator", fake)
    with socket("mode=analyst&speed=60") as ws:
        s = Socket(ws)
        s.send(type="seek", minute=63)
        v2, seen = s.until(lambda m: m["type"] == "cue" and m["cue"]["version"] == 2)
        v1 = next(m["cue"] for m in seen if m["type"] == "cue" and m["cue"]["cue_id"] == v2["cue"]["cue_id"])
        assert v1["source"] == "template" and v2["cue"]["source"] == "model"
        assert v2["cue"]["text"]["en"] == "Grounded words only."
        assert v2["cue"]["trace"][-1] == {"agent": "Fact-checker", "action": "approve", "ok": True,
                                          "detail": "Every number traced to a fact. Version 2 goes on air."}


def test_websocket_keeps_template_when_model_invents_numbers(socket, monkeypatch):
    fake = FakeNarrator(lambda _: {"text": "A 999 km/h thunderbolt!"})
    monkeypatch.setattr(server, "narrator", fake)
    with socket("mode=analyst&speed=60") as ws:
        s = Socket(ws)
        s.send(type="seek", minute=63)
        _, seen = s.until(lambda m: m["type"] == "cue" and m["cue"]["template"] == "goal")
        _, more = s.until(lambda m: m["type"] == "event" and m["event"]["clock_ms"] >= 65 * 60_000)
        assert fake.calls
        assert all(m["cue"]["version"] == 1 for m in seen + more if m["type"] == "cue")
        rejected = [m["cue"] for m in seen + more if m["type"] == "cue" and m["cue"]["trace"][-1]["action"] == "fallback"]
        assert rejected and all(c["source"] == "template" for c in rejected)
