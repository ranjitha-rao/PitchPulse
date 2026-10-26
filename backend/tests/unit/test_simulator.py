from collections import Counter

from pitchpulse.metrics import PITCH_L, PITCH_W
from pitchpulse.roster import PLAYERS
from pitchpulse.simulator import Simulator, generate_match, press_intensity


def test_same_seed_same_match_and_different_seed_different_match(events):
    assert generate_match(seed=7) == events
    assert generate_match(seed=8) != events


def test_events_are_well_formed(events):
    ids = [e["event_id"] for e in events]
    assert len(ids) == len(set(ids))
    clocks = [e["clock_ms"] for e in events]
    assert clocks == sorted(clocks)
    for e in events:
        if e["player_id"]:
            assert e["player_id"] in PLAYERS
            assert e["player_id"].startswith(e["team_id"])
        for key in ("start_xy", "end_xy"):
            if key in e:
                x, y = e[key]
                assert -1 <= x <= PITCH_L + 1 and -1 <= y <= PITCH_W + 1


def test_seeded_story_plays_out(events):
    goals = [e for e in events if e["type"] == "goal"]
    assert [g["team_id"] for g in goals] == ["nga", "nga", "hfc", "hfc", "hfc"]
    assert [g["clock_ms"] // 60000 for g in goals] == [12, 34, 63, 78, 89]
    assert goals[-1]["qualifiers"]["score"] == {"hfc": 3, "nga": 2}
    assert events[-1]["type"] == "period_end" and events[-1]["qualifiers"]["final"]
    cards = [e for e in events if e["type"] == "card"]
    assert [(c["player_id"], c["qualifiers"]["card"]) for c in cards] == [("nga_06", "yellow")]


def test_event_mix_is_football_realistic(events):
    counts = Counter(e["type"] for e in events)
    assert 800 <= counts["pass"] <= 1300
    assert 15 <= counts["shot"] <= 40
    passes = [e for e in events if e["type"] == "pass"]
    completion = sum(e["outcome"] == "complete" for e in passes) / len(passes)
    assert 0.7 <= completion <= 0.9
    for p in passes:
        assert 0 <= p["qualifiers"]["difficulty"] <= 100
        assert (p["outcome"] == "complete") == ("receiver_id" in p)


def test_halftime_switches_kickoff_and_period(events):
    starts = [e for e in events if e["type"] == "period_start"]
    assert [(s["period"], s["team_id"]) for s in starts] == [(1, "hfc"), (2, "nga")]
    assert 45 * 60000 <= starts[1]["clock_ms"] < 46 * 60000
    first_half_end = next(e for e in events if e["type"] == "period_end")
    assert first_half_end["clock_ms"] <= starts[1]["clock_ms"]


def test_northgate_press_fades_after_the_hour():
    assert press_intensity("nga", 30) > press_intensity("nga", 80)
    assert press_intensity("hfc", 30) < press_intensity("hfc", 80)


def test_custom_seeds_change_the_story():
    sim = Simulator(seed=3, seeds={"goals": [], "cards": []})
    evs = sim.run()
    assert not any(e["type"] in ("goal", "card") for e in evs)
