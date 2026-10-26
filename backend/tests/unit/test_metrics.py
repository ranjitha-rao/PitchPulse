import pytest

from pitchpulse import metrics as m


def test_attack_frame_mirrors_the_away_side_and_round_trips():
    assert m.attack_frame("hfc", 10, 20) == (10, 20)
    assert m.attack_frame("nga", 10, 20) == (95, 48)
    for team in ("hfc", "nga"):
        assert m.absolute(team, *m.attack_frame(team, 33.3, 12.1)) == pytest.approx((33.3, 12.1))


def test_pass_difficulty_is_bounded():
    assert 0 <= m.pass_difficulty(0, 0, 0, 0, False) <= 100
    assert 0 <= m.pass_difficulty(110, 3, 100, 10, True) <= 100


@pytest.mark.parametrize("field, low, high", [
    ("dist_m", 10, 40),
    ("pressers", 0, 2),
    ("forward_m", 0, 30),
    ("bypassed", 0, 5),
    ("through_ball", False, True),
])
def test_pass_difficulty_rises_with_each_factor(field, low, high):
    base = {"dist_m": 15, "pressers": 0, "forward_m": 5, "bypassed": 1, "through_ball": False}
    assert m.pass_difficulty(**{**base, field: high}) > m.pass_difficulty(**{**base, field: low})


def test_pass_difficulty_separates_safe_and_line_breaking_passes():
    assert m.pass_difficulty(8, 0, 0, 0, False) < 15
    assert m.pass_difficulty(40, 1, 35, 5, True) > 75


def test_expected_goals_follows_shot_quality():
    close, far = m.expected_goals(99, 34, "right_foot", False), m.expected_goals(80, 34, "right_foot", False)
    assert 0 < far < close < 1
    assert m.expected_goals(95, 34, "head", False) < m.expected_goals(95, 34, "right_foot", False)
    assert m.expected_goals(95, 34, "right_foot", True) < m.expected_goals(95, 34, "right_foot", False)
    assert m.expected_goals(95, 5, "right_foot", False) < m.expected_goals(95, 34, "right_foot", False)


def test_shot_geometry_is_widest_in_front_of_goal():
    d_central, a_central = m.shot_geometry(94, 34)
    d_wide, a_wide = m.shot_geometry(94, 10)
    assert d_central == pytest.approx(11)
    assert a_central > a_wide and d_wide > d_central


@pytest.mark.parametrize("hg, ag, minute, share", [(0, 0, 0, 0.5), (1, 2, 60, 0.3), (3, 2, 89, 0.8), (0, 4, 20, 0.1)])
def test_win_probability_is_a_distribution(hg, ag, minute, share):
    wp = m.win_probability(hg, ag, minute, share)
    assert set(wp) == {"home", "draw", "away"}
    assert sum(wp.values()) == pytest.approx(1, abs=0.005)
    assert all(0 <= v <= 1 for v in wp.values())


def test_win_probability_responds_to_score_time_and_dominance():
    assert m.win_probability(1, 0, 90, 0.5) == {"home": 1.0, "draw": 0.0, "away": 0.0}
    kickoff = m.win_probability(0, 0, 0, 0.5)
    assert kickoff["home"] == pytest.approx(kickoff["away"])
    assert m.win_probability(0, 0, 0, 0.8)["home"] > kickoff["home"]
    assert m.win_probability(1, 0, 85, 0.5)["home"] > m.win_probability(1, 0, 30, 0.5)["home"]
    assert m.win_probability(0, 2, 85, 0.5)["away"] > 0.9


def test_kmh():
    assert m.kmh(10, 1) == 36.0
    assert m.kmh(10, 0) == 0.0
