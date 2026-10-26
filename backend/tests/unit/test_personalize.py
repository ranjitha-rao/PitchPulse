from pitchpulse.engine import MIN, Moment
from pitchpulse.personalize import SLOTS, Profile, build_cue, player_card_cue, relevance


def mo(type_="line_breaker", team="hfc", player="hfc_08", importance=50, related=None, clock=30 * MIN, **facts):
    f = [{"id": k, "value": v} for k, v in facts.items()] or [{"id": "x", "value": 1}]
    return Moment(f"m_{type_}", type_, clock, team, player, importance, f, [f[0]["id"]], None, related or [])


def test_profile_update_defaults_and_clears():
    p = Profile()
    p.update(mode="player")
    assert p.player == "hfc_08"
    p.update(club="nga", player="nga_10")
    assert (p.club, p.player) == ("nga", "nga_10")
    p.update(club="", lang="ar")
    assert p.club is None and p.lang == "ar" and p.mode == "player"
    p.update(mode=None)
    assert p.mode == "player"


def test_casual_hides_technical_moments_analyst_shows_them():
    rhythm = mo("rhythm_shift", team=None, player=None, importance=45)
    assert relevance(rhythm, Profile(mode="casual")) is None
    assert relevance(rhythm, Profile(mode="analyst")) == 45


def test_casual_only_shows_record_sprints_and_strong_passes():
    assert relevance(mo("sprint", is_record=False), Profile(mode="casual")) is None
    assert relevance(mo("sprint", is_record=True), Profile(mode="casual")) is not None
    assert relevance(mo(importance=40), Profile(mode="casual")) is None
    assert relevance(mo(importance=49), Profile(mode="casual")) is not None


def test_player_focus_only_follows_the_player_plus_goals_and_cards():
    p = Profile(mode="player", player="hfc_08")
    assert relevance(mo(player="hfc_10"), p) is None
    assert relevance(mo(player="hfc_10", related=["hfc_08"]), p) is not None
    assert relevance(mo("goal", player="nga_09", team="nga"), p) is not None
    assert relevance(mo("card", player="nga_06", team="nga"), p) is not None


def test_favourite_club_and_player_raise_priority():
    base = relevance(mo(team="nga", player="nga_10"), Profile(mode="analyst"))
    assert relevance(mo(team="nga", player="nga_10"), Profile(mode="analyst", club="nga")) == base + 15
    assert relevance(mo(team="nga", player="nga_10"), Profile(mode="analyst", player="nga_10")) == base + 25


def test_rate_limit_per_mode_but_goals_always_pass():
    p = Profile(mode="casual", last_cue_ms=29 * MIN)
    assert relevance(mo("big_chance", clock=30 * MIN), p) is None
    assert relevance(mo("big_chance", clock=34 * MIN), p) is not None
    assert relevance(mo("goal", clock=30 * MIN), p) is not None
    a = Profile(mode="analyst", last_cue_ms=int(29.5 * MIN))
    assert relevance(mo("rhythm_shift", clock=30 * MIN), a) is None


def test_cue_contract(moments):
    goal = next(m for m in moments if m.type == "goal")
    cue = build_cue(goal, Profile(mode="analyst", lang="ar"), ["en", "es", "ar"])
    assert cue["slot"] == SLOTS["goal"][0] == "banner" and cue["version"] == 1 and cue["source"] == "template"
    assert cue["clock_in_ms"] == goal.clock_ms and 0 <= cue["priority"] <= 100
    assert set(cue["text"]) == {"en", "es", "ar"} and cue["dir"]["ar"] == "rtl" and cue["dir"]["en"] == "ltr"
    assert set(cue["variants"]) == {"casual", "analyst"}
    assert cue["text"]["en"] == cue["variants"]["analyst"]["en"]
    assert cue["data"] == {f["id"]: f["value"] for f in goal.facts}
    assert cue["explain"]["drivers"] == goal.drivers


def test_player_card_cue(engine):
    p = Profile(mode="player", player="hfc_08")
    cue = player_card_cue(engine, p, ["en", "es"])
    assert cue["slot"] == "player_card" and cue["name"] == "Daniel Okafor"
    assert str(cue["data"]["passes"]) in cue["text"]["en"]
