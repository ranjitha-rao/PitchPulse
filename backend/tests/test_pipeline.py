import json

from fastapi.testclient import TestClient

from pitchpulse.engine import MatchEngine
from pitchpulse.metrics import expected_goals, pass_difficulty, win_probability
from pitchpulse.narrate import render, validate
from pitchpulse.personalize import Profile, relevance
from pitchpulse.simulator import generate_match


def run_match():
    events = generate_match(seed=7)
    engine = MatchEngine()
    moments = []
    for ev in events:
        moments += engine.ingest(ev)
    return events, engine, moments


def test_simulator_is_deterministic_and_plays_the_comeback():
    a, b = generate_match(seed=7), generate_match(seed=7)
    assert a == b
    goals = [e for e in a if e["type"] == "goal"]
    assert [g["team_id"] for g in goals] == ["nga", "nga", "hfc", "hfc", "hfc"]
    assert goals[-1]["qualifiers"]["score"] == {"hfc": 3, "nga": 2}
    passes = [e for e in a if e["type"] == "pass"]
    assert 800 <= len(passes) <= 1300
    completion = sum(e["outcome"] == "complete" for e in passes) / len(passes)
    assert 0.7 <= completion <= 0.9


def test_metrics_behave_sensibly():
    assert pass_difficulty(8, 0, 0, 0, False) < 15
    assert pass_difficulty(40, 1, 35, 5, True) > 75
    assert expected_goals(99, 34, "right_foot", False) > expected_goals(80, 34, "right_foot", False)
    wp = win_probability(0, 2, 85, 0.5)
    assert wp["away"] > 0.9 and abs(sum(wp.values()) - 1) < 0.01


def test_engine_finds_the_story():
    _, engine, moments = run_match()
    kinds = {m.type for m in moments}
    assert {"goal", "line_breaker", "press_fade", "control_swing", "milestone", "card"} <= kinds
    assert engine.storylines["comeback"]["status"] == "complete"
    assert engine.storylines["press"]["team_id"] == "nga"
    assert engine.storylines["press"]["status"] == "faded"
    winner = [m for m in moments if m.type == "goal"][-1]
    assert winner.fact("wp_after") > 90 and winner.fact("wp_before") < 20


def test_template_captions_are_grounded_in_every_language():
    _, _, moments = run_match()
    for mo in moments:
        facts = mo.facts + [{"id": "minute", "value": mo.minute}]
        for lang in ("en", "es", "ar"):
            for voice in ("casual", "analyst"):
                text = render(mo.type, mo.facts, voice, lang)
                assert text
                ok, bad = validate(text, facts)
                assert ok, (mo.type, lang, voice, text, bad)


def test_validator_rejects_invented_numbers():
    facts = [{"id": "xg", "value": 0.29}, {"id": "shot_speed", "value": 100}]
    assert validate("A 100 km/h strike from a 0.29 xG chance", facts)[0]
    assert not validate("A 112 km/h strike", facts)[0]
    assert validate("Disparo a ١٠٠ km/h", facts)[0]


def test_modes_show_different_moments():
    _, _, moments = run_match()

    def shown(profile):
        out = []
        for mo in moments:
            if relevance(mo, profile) is not None:
                out.append(mo)
                if mo.type not in ("goal", "card"):
                    profile.last_cue_ms = mo.clock_ms
        return out

    casual = shown(Profile(mode="casual"))
    analyst = shown(Profile(mode="analyst"))
    focus = shown(Profile(mode="player", player="hfc_08"))
    assert len(analyst) > len(casual)
    assert all(m.type in ("goal", "card") or m.player_id == "hfc_08" or "hfc_08" in m.related_players for m in focus)
    assert sum(m.type == "goal" for m in casual) == 5


def test_websocket_streams_cues_and_recap():
    from server import app

    client = TestClient(app)
    assert client.get("/api/meta").json()["teams"]["hfc"]["name"] == "Harbourside FC"
    with client.websocket_connect("/ws/match?mode=analyst&lang=es&speed=60") as ws:
        ws.send_text(json.dumps({"type": "seek", "minute": 88}))
        cues, recap = [], None
        for _ in range(3000):
            msg = json.loads(ws.receive_text())
            if msg["type"] == "cue":
                cues.append(msg["cue"])
            if msg["type"] == "recap" and not msg["half"]:
                recap = msg
                break
        assert any(c["template"] == "goal" and "es" in c["text"] for c in cues)
        assert recap and "remont" in recap["recap"]["es"]["text"]
