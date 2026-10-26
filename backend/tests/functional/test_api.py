def test_meta_describes_the_match(client):
    meta = client.get("/api/meta").json()
    assert set(meta["teams"]) == {"hfc", "nga"}
    assert all(len(t["players"]) == 11 for t in meta["teams"].values())
    assert meta["langs"] == ["en", "es", "ar"] and meta["modes"] == ["casual", "analyst", "player"]
    assert meta["model_captions"] is False
    assert meta["event_count"] > 1000


def test_events_dataset(client):
    assert len(client.get("/api/events", params={"limit": 5}).json()) == 5
    full = client.get("/api/events").json()
    assert full[0]["type"] == "period_start" and full[-1]["type"] == "period_end"


def test_moments_feed(client):
    moments = client.get("/api/moments").json()
    assert sum(m["type"] == "goal" for m in moments) == 5
    assert all({"id", "facts", "drivers", "minute"} <= set(m) for m in moments)


def test_recap_in_each_language(client):
    for lang, word in (("en", "came back"), ("es", "remontó"), ("ar", "عاد")):
        r = client.get("/api/recap", params={"lang": lang}).json()
        assert word in r["text"] and r["model_text"] is None
        assert r["facts"]["home_goals"] == 3


def test_webvtt_captions_endpoint(client):
    r = client.get("/api/captions.vtt", params={"mode": "player", "player_id": "hfc_08", "lang": "ar"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/vtt")
    assert "pitchpulse-player-ar.vtt" in r.headers["content-disposition"]
    assert r.text.startswith("WEBVTT\n")
    assert "Daniel Okafor" in r.text and "هدف!" in r.text
