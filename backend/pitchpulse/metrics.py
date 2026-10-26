"""Deterministic football metrics. The language model never computes any of these."""

import math

PITCH_L, PITCH_W = 105.0, 68.0
GOAL_Y = PITCH_W / 2


def attack_frame(team_id: str, x: float, y: float) -> tuple[float, float]:
    """Absolute pitch coordinates (home attacks towards x=105) to the team's attacking frame."""
    if team_id == "hfc":
        return x, y
    return PITCH_L - x, PITCH_W - y


def absolute(team_id: str, ax: float, ay: float) -> tuple[float, float]:
    # The mirror is its own inverse.
    return attack_frame(team_id, ax, ay)


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _sigmoid(z: float) -> float:
    return 1 / (1 + math.exp(-z))


def pass_difficulty(
    dist_m: float,
    pressers: int,
    forward_m: float,
    bypassed: int,
    through_ball: bool,
) -> int:
    """0 (trivial) to 100 (exceptional). Logistic blend of what makes a pass hard."""
    z = (
        -3.0
        + 0.045 * dist_m
        + 0.7 * pressers
        + 0.02 * max(forward_m, 0)
        + 0.3 * bypassed
        + (0.7 if through_ball else 0)
    )
    return round(100 * _sigmoid(z))


def shot_geometry(ax: float, ay: float) -> tuple[float, float]:
    """Distance (m) to goal centre and the visible goal angle (radians), attacking frame."""
    dx = PITCH_L - ax
    dy = ay - GOAL_Y
    dist = math.hypot(dx, dy)
    # Angle subtended by the 7.32 m goal mouth.
    half = 3.66
    a1 = math.atan2(dy - half, dx)
    a2 = math.atan2(dy + half, dx)
    return dist, abs(a2 - a1)


def expected_goals(ax: float, ay: float, body_part: str, under_pressure: bool) -> float:
    dist, angle = shot_geometry(ax, ay)
    z = -1.1 - 0.11 * dist + 1.6 * angle
    if body_part == "head":
        z -= 0.7
    if under_pressure:
        z -= 0.35
    return round(_sigmoid(z), 2)


def _poisson(k: int, lam: float) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def win_probability(
    home_goals: int,
    away_goals: int,
    minute: float,
    home_share: float,
    base_rate: float = 1.6,
) -> dict[str, float]:
    """Home win / draw / away win from the score, time left and recent dominance.

    home_share is the home side's share of recent xG (0..1), which tilts the
    remaining goal rates. Remaining goals per side are Poisson.
    """
    remaining = max(0.0, (90 - minute) / 90)
    lam_h = base_rate * (0.7 + 0.6 * home_share) * remaining
    lam_a = base_rate * (0.7 + 0.6 * (1 - home_share)) * remaining
    gd = home_goals - away_goals
    p = {"home": 0.0, "draw": 0.0, "away": 0.0}
    for i in range(11):
        pi = _poisson(i, lam_h)
        for j in range(11):
            pij = pi * _poisson(j, lam_a)
            final = gd + i - j
            p["home" if final > 0 else "draw" if final == 0 else "away"] += pij
    total = sum(p.values())
    return {k: round(v / total, 3) for k, v in p.items()}


def kmh(metres: float, seconds: float) -> float:
    return round(metres / seconds * 3.6, 1) if seconds > 0 else 0.0
