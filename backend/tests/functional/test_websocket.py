from .conftest import Socket

MIN = 60_000


def test_connect_sends_status_with_profile(socket):
    with socket("mode=analyst&club=nga&lang=ar&speed=10") as ws:
        s = Socket(ws)
        status, _ = s.until(lambda m: m["type"] == "status")
        assert status["profile"] == {"mode": "analyst", "club": "nga", "player": None, "lang": "ar"}
        assert status["speed"] == 10 and status["playing"] is True


def test_seek_to_the_end_streams_goals_and_recap(socket):
    with socket("mode=analyst&lang=es&speed=60") as ws:
        s = Socket(ws)
        s.send(type="seek", minute=88)
        recap, seen = s.until(lambda m: m["type"] == "recap" and not m["half"])
        cues = [m["cue"] for m in seen if m["type"] == "cue"]
        events = [m["event"] for m in seen if m["type"] == "event"]
        # A kickoff event or two may go out before the seek lands; nothing in between is replayed.
        assert events and not any(MIN <= e["clock_ms"] < 88 * MIN for e in events)
        goal = next(c for c in cues if c["template"] == "goal")
        assert goal["data"]["score_home"] == 3 and set(goal["text"]) == {"en", "es", "ar"}
        assert [st["agent"] for st in goal["trace"]] == ["Analyst", "Producer", "Narrator", "Fact-checker"]
        assert "remont" in recap["recap"]["es"]["text"]
        assert recap["timeline"] and recap["facts"]["home_goals"] == 3
        states = [m for m in seen if m["type"] == "state"]
        assert states and states[-1]["state"]["score"] == {"hfc": 3, "nga": 2}


def test_backward_seek_restarts_and_fast_forwards(socket):
    with socket() as ws:
        s = Socket(ws)
        s.send(type="seek", minute=60)
        s.until(lambda m: m["type"] == "event" and m["event"]["clock_ms"] >= 60 * MIN)
        s.send(type="seek", minute=20)
        s.until(lambda m: m["type"] == "reset")
        ev, _ = s.until(lambda m: m["type"] == "event")
        assert 20 * MIN <= ev["event"]["clock_ms"] < 22 * MIN


def test_profile_speed_and_pause_controls(socket):
    with socket() as ws:
        s = Socket(ws)
        s.until(lambda m: m["type"] == "status")
        s.send(type="profile", mode="player", lang="ar")
        st, _ = s.until(lambda m: m["type"] == "status")
        assert st["profile"]["mode"] == "player" and st["profile"]["player"] == "hfc_08" and st["profile"]["lang"] == "ar"
        s.send(type="speed", value=500)
        st, _ = s.until(lambda m: m["type"] == "status")
        assert st["speed"] == 60
        s.send(type="pause")
        st, _ = s.until(lambda m: m["type"] == "status")
        assert st["playing"] is False
        s.send(type="resume")
        st, _ = s.until(lambda m: m["type"] == "status")
        assert st["playing"] is True


def test_player_focus_gets_player_cards_and_only_relevant_cues(socket):
    with socket("mode=player&player_id=hfc_08&speed=60") as ws:
        s = Socket(ws)
        s.send(type="seek", minute=55)
        _, seen = s.until(lambda m: m["type"] == "cue" and m["cue"]["template"] == "player_card")
        _, more = s.until(lambda m: m["type"] == "cue" and m["cue"]["template"] == "goal")
        cues = [m["cue"] for m in seen + more if m["type"] == "cue"]
        for c in cues:
            assert c["template"] in ("goal", "card", "player_card") or c["player_id"] == "hfc_08" \
                or "hfc_08" in str(c["data"].values()) or "Daniel Okafor" in c["data"].values()
