"""Synthetic match generator.

Play is simulated as a possession chain in each team's attacking frame and
emitted as events in absolute pitch coordinates (home attacks towards x=105).
Story seeds script the goals and the card so the demo always has a comeback
to explain; everything between them is sampled from a seeded RNG.
"""

import math
import random
from dataclasses import dataclass

from . import metrics as m
from .roster import AWAY, HOME, MATCH_META, PLAYERS, TEAMS, Player, opponent

MATCH_END_MS = 93 * 60_000
HALF_MS = 45 * 60_000


@dataclass(frozen=True)
class GoalSeed:
    minute: float
    team: str
    scorer: str
    assister: str
    style: str  # "through_ball" | "sprint_cross" | "turnover"


@dataclass(frozen=True)
class CardSeed:
    minute: float
    player: str
    fouled: str
    card: str


COMEBACK_SEEDS = {
    "goals": [
        GoalSeed(12, "nga", "nga_09", "nga_10", "through_ball"),
        GoalSeed(34, "nga", "nga_07", "nga_08", "turnover"),
        GoalSeed(63, "hfc", "hfc_09", "hfc_08", "through_ball"),
        GoalSeed(78, "hfc", "hfc_10", "hfc_07", "sprint_cross"),
        GoalSeed(89, "hfc", "hfc_09", "hfc_08", "through_ball"),
    ],
    "cards": [CardSeed(58, "nga_06", "hfc_08", "yellow")],
}


def press_intensity(team: str, minute: float) -> float:
    """How hard a team presses. Northgate's press fades after the hour (story seed)."""
    if team == "nga":
        if minute < 55:
            return 0.85
        if minute < 72:
            return 0.85 - 0.5 * (minute - 55) / 17
        return 0.35
    return 0.45 if minute < 60 else 0.62


def form(team: str, minute: float) -> tuple[float, float]:
    """(pass-completion bonus, shot threat multiplier). Story seed: Northgate tire after the hour."""
    late = minute >= 60
    if team == "nga":
        return (-0.06, 0.45) if late else (0.0, 1.0)
    return (0.06, 1.5) if late else (-0.01, 0.7)


def attacking_intent(team: str, minute: float, score: dict[str, int]) -> float:
    behind = score[team] < score[opponent(team)]
    ahead = score[team] > score[opponent(team)]
    intent = 1.0
    if behind and minute > 55:
        intent = 1.5
    elif ahead:
        intent = 0.8
    return intent


class Simulator:
    def __init__(self, seed: int = 7, seeds: dict | None = None):
        self.rng = random.Random(seed)
        self.seeds = seeds or COMEBACK_SEEDS
        self.events: list[dict] = []
        self.clock = 0.0  # ms
        self.period = 1
        self.score = {HOME.id: 0, AWAY.id: 0}
        self.possession_id = 0
        self.team = HOME.id
        self.carrier = HOME.player("hfc_09").id
        self.ax, self.ay = 52.5, 34.0
        self.pending_goals = list(self.seeds["goals"])
        self.pending_cards = list(self.seeds["cards"])

    # ---- helpers -----------------------------------------------------
    @property
    def minute(self) -> float:
        return self.clock / 60_000

    def _emit(self, type_: str, team: str | None, player: str | None, **kw) -> dict:
        start = kw.pop("start", None)
        end = kw.pop("end", None)
        ev = {
            "event_id": f"evt_{len(self.events):05d}",
            "match_id": MATCH_META["match_id"],
            "clock_ms": int(self.clock),
            "period": self.period,
            "type": type_,
            "team_id": team,
            "player_id": player,
            "possession_id": f"p_{self.possession_id:03d}",
        }
        if start is not None:
            ev["start_xy"] = [round(v, 1) for v in m.absolute(team, *start)]
        if end is not None:
            ev["end_xy"] = [round(v, 1) for v in m.absolute(team, *end)]
        ev.update({k: v for k, v in kw.items() if v is not None})
        self.events.append(ev)
        return ev

    def _advance(self, seconds: float) -> None:
        self.clock += seconds * 1000

    def _positions(self, team: str) -> dict[str, tuple[float, float]]:
        """Approximate positions of a team's players in its own attacking frame."""
        own_ball_ax = self.ax if team == self.team else m.PITCH_L - self.ax
        shift = (own_ball_ax - 50) * 0.5
        out = {}
        for p in TEAMS[team].players:
            if p.position == "GK":
                out[p.id] = (p.slot[0], p.slot[1])
            else:
                out[p.id] = (min(100, max(8, p.slot[0] + shift)), p.slot[1])
        return out

    def _defenders_in_attack_frame(self) -> dict[str, tuple[float, float]]:
        opp = opponent(self.team)
        return {pid: (m.PITCH_L - x, m.PITCH_W - y) for pid, (x, y) in self._positions(opp).items()}

    def _nearest_defender(self, point: tuple[float, float], outfield: bool = True) -> str:
        defs = self._defenders_in_attack_frame()
        cands = [(m.distance(point, pos), pid) for pid, pos in defs.items()
                 if not (outfield and PLAYERS[pid].position == "GK")]
        cands.sort()
        top = cands[:3]
        return self.rng.choices([c[1] for c in top], weights=[3, 2, 1][: len(top)])[0]

    def _change_possession(self, new_carrier: str, ax: float, ay: float, reason: str) -> None:
        self.team = opponent(self.team)
        self.carrier = new_carrier
        self.ax, self.ay = ax, ay
        self.possession_id += 1
        self._advance(self.rng.uniform(0.6, 1.4))
        self._emit("possession_change", self.team, new_carrier, start=(ax, ay), qualifiers={"reason": reason})

    def _turnover_at(self, ax: float, ay: float, reason: str) -> None:
        """Opponent wins the ball at (ax, ay) in the current attacking frame."""
        winner = self._nearest_defender((ax, ay))
        self._change_possession(winner, m.PITCH_L - ax, m.PITCH_W - ay, reason)

    def _pressure(self) -> dict:
        minute = self.minute
        opp = opponent(self.team)
        intensity = press_intensity(opp, minute)
        chance = intensity * (0.55 if self.ax < 52 else 0.35)
        if self.rng.random() >= chance:
            return {"under": False, "pressers": [], "dist_m": None}
        pressers = 1 if self.rng.random() < 0.7 else 2
        presser_ids = []
        for _ in range(pressers):
            pid = self._nearest_defender((self.ax, self.ay))
            if pid not in presser_ids:
                presser_ids.append(pid)
        dist = round(self.rng.uniform(0.8, 3.0), 1)
        self._emit("pressure", opp, presser_ids[0], start=None,
                   qualifiers={"on_player": self.carrier, "pressers": presser_ids, "dist_m": dist},
                   end=None)
        # Pressure event location is the ball location, in the presser's frame.
        self.events[-1]["start_xy"] = [round(v, 1) for v in m.absolute(self.team, self.ax, self.ay)]
        return {"under": True, "pressers": presser_ids, "dist_m": dist}

    # ---- actions -------------------------------------------------------
    def _choose_receiver(self, intent: float, forced: str | None = None) -> tuple[str, tuple[float, float]]:
        pos = self._positions(self.team)
        if forced:
            return forced, pos[forced]
        cands, weights = [], []
        for pid, (x, y) in pos.items():
            if pid == self.carrier:
                continue
            d = m.distance((self.ax, self.ay), (x, y))
            fwd = x - self.ax
            w = math.exp(-d / 17) * (1 + intent * max(fwd, 0) / 18)
            if PLAYERS[pid].position == "GK":
                w *= 0.15 if self.ax < 40 else 0.01
            cands.append(pid)
            weights.append(w)
        rid = self.rng.choices(cands, weights=weights)[0]
        return rid, pos[rid]

    def _bypassed(self, start_ax: float, end_ax: float) -> int:
        if end_ax <= start_ax:
            return 0
        return sum(
            1 for pid, (x, _) in self._defenders_in_attack_frame().items()
            if PLAYERS[pid].position != "GK" and start_ax < x < end_ax
        )

    def _pass(self, pressure: dict, intent: float, forced_to: str | None = None,
              force_complete: bool = False, end_override: tuple[float, float] | None = None,
              through_ball: bool | None = None) -> bool:
        passer = PLAYERS[self.carrier]
        rid, (rx, ry) = self._choose_receiver(intent, forced_to)
        if end_override:
            ex, ey = end_override
        else:
            ex = min(103, max(2, rx + self.rng.gauss(0, 3)))
            ey = min(67, max(1, ry + self.rng.gauss(0, 3)))
        start = (self.ax, self.ay)
        dist = m.distance(start, (ex, ey))
        fwd = ex - self.ax
        bypassed = self._bypassed(self.ax, ex)
        tb = through_ball if through_ball is not None else (fwd > 15 and bypassed >= 2 and self.rng.random() < 0.5)
        difficulty = m.pass_difficulty(dist, len(pressure["pressers"]), fwd, bypassed, tb)
        p_success = (0.97 - 0.008 * max(0, difficulty - 15) + (passer.passing - 75) / 300
                     + form(self.team, self.minute)[0])
        success = force_complete or self.rng.random() < p_success
        ball_speed = round(25 + dist * 1.6 + self.rng.uniform(0, 8), 1)
        flight = dist / (ball_speed / 3.6)
        self._emit(
            "pass", self.team, passer.id, receiver_id=rid if success else None,
            start=start, end=(ex, ey), outcome="complete" if success else "incomplete",
            pressure=pressure, ball_speed_kmh=ball_speed,
            qualifiers={"distance_m": round(dist, 1), "forward_m": round(fwd, 1), "bypassed": bypassed,
                        "through_ball": tb, "difficulty": difficulty, "intended_receiver": rid},
        )
        self._advance(flight + self.rng.uniform(1.0, 2.6))
        self.ax, self.ay = ex, ey
        if success:
            self.carrier = rid
            return True
        if self.rng.random() < 0.55:
            winner = self._nearest_defender((ex, ey))
            self._emit("interception", opponent(self.team), winner, start=None, end=None)
            self.events[-1]["start_xy"] = [round(v, 1) for v in m.absolute(self.team, ex, ey)]
            self._change_possession(winner, m.PITCH_L - ex, m.PITCH_W - ey, "interception")
        else:
            if self.rng.random() < 0.3:
                self._advance(self.rng.uniform(8, 18))  # out of play, throw-in
            self._turnover_at(ex, ey, "loose_ball")
        return False

    def _carry(self, pressure: dict, intent: float, length: float | None = None,
               speed: float | None = None, force: bool = False) -> bool:
        p = PLAYERS[self.carrier]
        length = length or self.rng.uniform(4, 14) * (0.8 + 0.3 * intent)
        heading = self.rng.gauss(0, 0.5)
        ex = min(101, self.ax + length * math.cos(heading))
        ey = min(66, max(2, self.ay + length * math.sin(heading)))
        speed = speed or round(min(36, 11 + p.pace * 0.2 + self.rng.gauss(0, 2.5)), 1)
        start = (self.ax, self.ay)
        dist = m.distance(start, (ex, ey))
        if pressure["under"] and not force and self.rng.random() < 0.3:
            tackler = pressure["pressers"][0]
            self._advance(self.rng.uniform(1, 3))
            self._emit("tackle", opponent(self.team), tackler, outcome="won",
                       qualifiers={"on_player": p.id})
            self.events[-1]["start_xy"] = [round(v, 1) for v in m.absolute(self.team, self.ax, self.ay)]
            if self.rng.random() < 0.15:
                self._foul(tackler, p.id)
                return True
            self._change_possession(tackler, m.PITCH_L - self.ax, m.PITCH_W - self.ay, "tackle")
            return False
        self._emit("carry", self.team, p.id, start=start, end=(ex, ey), pressure=pressure,
                   qualifiers={"distance_m": round(dist, 1), "speed_kmh": speed, "sprint": speed >= 30})
        self._advance(dist / (speed / 3.6))
        self.ax, self.ay = ex, ey
        return True

    def _foul(self, by: str, on: str, card: str | None = None) -> None:
        team = opponent(self.team)
        self._emit("foul", team, by, qualifiers={"on_player": on})
        self.events[-1]["start_xy"] = [round(v, 1) for v in m.absolute(self.team, self.ax, self.ay)]
        if card:
            self._advance(20)
            self._emit("card", team, by, qualifiers={"card": card, "on_player": on})
        self._advance(self.rng.uniform(20, 40))

    def _shot(self, pressure: dict, goal: bool = False, head: bool = False) -> None:
        p = PLAYERS[self.carrier]
        body = "head" if head else ("right_foot" if self.rng.random() < 0.7 else "left_foot")
        xg = m.expected_goals(self.ax, self.ay, body, pressure["under"])
        speed = round(min(122, 52 + p.finishing * 0.5 + self.rng.uniform(-8, 12)) * (0.75 if head else 1), 1)
        dist, _ = m.shot_geometry(self.ax, self.ay)
        if goal:
            outcome = "goal"
            end = (105, min(37, max(31, self.ay + self.rng.uniform(-2, 2))))
        else:
            outcome = self.rng.choices(["saved", "blocked", "off_target"], weights=[0.35, 0.3, 0.35])[0]
            end = (105, self.ay + self.rng.uniform(-6, 6)) if outcome != "blocked" else (self.ax + 2, self.ay)
        self._emit("shot", self.team, p.id, start=(self.ax, self.ay), end=end, outcome=outcome,
                   pressure=pressure, ball_speed_kmh=speed,
                   qualifiers={"xg": xg, "body_part": body, "distance_m": round(dist, 1)})
        self._advance(1.2)
        if goal:
            self.score[self.team] += 1
            self._emit("goal", self.team, p.id,
                       qualifiers={"score": dict(self.score), "xg": xg, "shot_speed_kmh": speed})
            self._advance(self.rng.uniform(55, 75))
            conceding = opponent(self.team)
            striker = next(pl.id for pl in TEAMS[conceding].players if pl.position == "ST")
            self.team = conceding
            self.carrier = striker
            self.ax, self.ay = 52.5, 34.0
            self.possession_id += 1
            self._emit("kickoff", conceding, striker, start=(52.5, 34.0))
            return
        self._advance(self.rng.uniform(20, 40))
        keeper = next(pl.id for pl in TEAMS[opponent(self.team)].players if pl.position == "GK")
        self._change_possession(keeper, 6, 34, "shot_" + outcome)

    # ---- scripted moments --------------------------------------------
    def _play_goal_seed(self, s: GoalSeed) -> None:
        if self.team != s.team:
            if s.style == "turnover":
                # Win the ball high up the pitch from a pressed defender.
                victim = "hfc_08"
                self.ax, self.ay = 38, 30
                self.carrier = victim
                self._emit("pressure", s.team, s.assister,
                           qualifiers={"on_player": victim, "pressers": [s.assister], "dist_m": 1.1})
                self.events[-1]["start_xy"] = [round(v, 1) for v in m.absolute(self.team, 38, 30)]
                self._advance(1.5)
                self._emit("tackle", s.team, s.assister, outcome="won", qualifiers={"on_player": victim})
                self.events[-1]["start_xy"] = [round(v, 1) for v in m.absolute(self.team, 38, 30)]
                self._change_possession(s.assister, m.PITCH_L - 38, m.PITCH_W - 30, "tackle")
            else:
                keeper = next(pl.id for pl in TEAMS[self.team].players if pl.position == "GK")
                self._change_possession(s.assister, 48, 40, "interception")
                _ = keeper
        no_pressure = {"under": False, "pressers": [], "dist_m": None}
        self.carrier = s.assister
        if s.style == "sprint_cross":
            self.ax, self.ay = 58, 58
            self._carry(no_pressure, 1.0, length=29, speed=33.4, force=True)
            self._pass(no_pressure, 1.0, forced_to=s.scorer, force_complete=True,
                       end_override=(94, 33), through_ball=False)
            self._shot(no_pressure, goal=True)
        elif s.style == "turnover":
            self._pass(no_pressure, 1.0, forced_to=s.scorer, force_complete=True,
                       end_override=(90, 46), through_ball=False)
            self._carry(no_pressure, 1.0, length=4, speed=24, force=True)
            self._shot(no_pressure, goal=True)
        else:
            self.ax, self.ay = 50, 40
            self._pass(no_pressure, 1.0, forced_to=s.scorer, force_complete=True,
                       end_override=(91, 32), through_ball=True)
            self._carry(no_pressure, 1.0, length=5, speed=30.5, force=True)
            self._shot(no_pressure, goal=True)

    # ---- main loop -----------------------------------------------------
    def run(self) -> list[dict]:
        self.possession_id = 1
        self._emit("period_start", HOME.id, self.carrier, start=(52.5, 34.0), qualifiers={"meta": MATCH_META})
        while self.clock < MATCH_END_MS:
            if self.period == 1 and self.clock >= HALF_MS:
                self._emit("period_end", None, None, qualifiers={"score": dict(self.score)})
                self.period = 2
                self.team = AWAY.id
                self.carrier = "nga_09"
                self.ax, self.ay = 52.5, 34.0
                self.possession_id += 1
                self._emit("period_start", AWAY.id, "nga_09", start=(52.5, 34.0))
                continue
            if self.pending_goals and self.minute >= self.pending_goals[0].minute:
                self._play_goal_seed(self.pending_goals.pop(0))
                continue
            if self.pending_cards and self.minute >= self.pending_cards[0].minute:
                c = self.pending_cards.pop(0)
                if self.team != PLAYERS[c.fouled].id.split("_")[0]:
                    self._change_possession(c.fouled, 55, 30, "interception")
                self.carrier = c.fouled
                self._foul(c.player, c.fouled, card=c.card)
                continue
            self._step()
        self._emit("period_end", None, None, qualifiers={"score": dict(self.score), "final": True})
        return self.events

    def _step(self) -> None:
        intent = attacking_intent(self.team, self.minute, self.score)
        pressure = self._pressure()
        if pressure["under"]:
            self._advance(0.4)
        central = abs(self.ay - m.GOAL_Y)
        p_shot = 0.0
        if self.ax > 83 and central < 18:
            p_shot = 0.15
        elif self.ax > 72 and central < 22:
            p_shot = 0.035
        p_shot *= form(self.team, self.minute)[1]
        r = self.rng.random()
        carrier: Player = PLAYERS[self.carrier]
        p_carry = 0.3 if carrier.position in ("RW", "LW") else 0.16
        if carrier.position == "GK":
            p_carry, p_shot = 0.0, 0.0
        if r < p_shot:
            self._shot(pressure)
        elif r < p_shot + p_carry:
            self._carry(pressure, intent)
        else:
            if pressure["under"] and self.rng.random() < 0.025:
                self._foul(pressure["pressers"][0], self.carrier)
                return
            self._pass(pressure, intent)


def generate_match(seed: int = 7) -> list[dict]:
    return Simulator(seed=seed).run()
