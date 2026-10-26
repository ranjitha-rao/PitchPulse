from collections import Counter

from pitchpulse.engine import MIN, MatchEngine

from ..conftest import first


def test_engine_finds_the_story(engine, moments):
    kinds = {m.type for m in moments}
    assert {"goal", "line_breaker", "press_fade", "control_swing", "milestone", "card", "big_chance", "sprint"} <= kinds
    assert engine.storylines["comeback"] == {**engine.storylines["comeback"], "team_id": "hfc", "status": "complete", "from": "0-2"}
    assert engine.storylines["press"]["team_id"] == "nga" and engine.storylines["press"]["status"] == "faded"
    assert engine.storylines["press"]["faded_to"] < engine.storylines["press"]["peak"]


def test_winner_swings_win_probability(moments):
    goals = [m for m in moments if m.type == "goal"]
    assert len(goals) == 5
    winner = goals[-1]
    assert winner.fact("wp_before") < 20 and winner.fact("wp_after") > 90
    assert winner.fact("assister") == "Daniel Okafor"
    assert winner.fact("comeback_from") == "0-2"
    assert winner.importance == max(m.importance for m in moments)


def test_every_moment_has_valid_drivers_and_unique_id(moments):
    assert len({m.id for m in moments}) == len(moments)
    for m in moments:
        fact_ids = [f["id"] for f in m.facts]
        assert len(fact_ids) == len(set(fact_ids))
        assert m.drivers and set(m.drivers) <= set(fact_ids), m.id


def test_team_and_player_totals_agree(engine, events):
    for t in ("hfc", "nga"):
        passes = [e for e in events if e["type"] == "pass" and e["team_id"] == t]
        assert engine.team_stats[t]["passes"] == len(passes)
        assert sum(s.passes for pid, s in engine.players.items() if pid.startswith(t)) == len(passes)
        assert engine.team_stats[t]["goals"] == engine.score[t]
    assert engine.score == {"hfc": 3, "nga": 2}
    assert sum(s.assists for s in engine.players.values()) == 5


def test_rolling_indices_stay_in_range(engine):
    assert 90 <= len(engine.timeline) <= 95
    for p in engine.timeline:
        assert -100 <= p["control_diff"] <= 100
        assert 0 <= p["chaos"] <= 100
        assert 0 <= p["field_tilt_home"] <= 100
        assert abs(sum(p["win_prob"].values()) - 1) < 0.01


def test_cooldowns_stop_moment_spam(moments):
    lbs = [m for m in moments if m.type == "line_breaker"]
    for team in ("hfc", "nga"):
        times = [m.clock_ms for m in lbs if m.team_id == team]
        assert all(b - a >= 6 * MIN for a, b in zip(times, times[1:]))
    per_type = Counter(m.type for m in moments)
    assert per_type["line_breaker"] < 40


def test_milestone_fires_once_on_first_touch(moments):
    ms = [m for m in moments if m.type == "milestone"]
    assert len(ms) == 1 and ms[0].fact("apps") == 100 and ms[0].player_id == "hfc_08"


def test_player_of_the_match_and_cards(engine):
    assert engine.player_of_match() == "hfc_08"
    card = engine.player_card("hfc_08")
    assert card["assists"] == 2
    assert 0 < card["pass_accuracy"] <= 100
    assert card["rating"] <= 10


def test_state_before_any_event():
    e = MatchEngine()
    s = e.state()
    assert s["score"] == {"hfc": 0, "nga": 0} and s["rolling"] is None
    assert abs(sum(s["win_prob"].values()) - 1) < 0.01


def test_first_helper(moments):
    assert first(moments, "goal").team_id == "nga"
