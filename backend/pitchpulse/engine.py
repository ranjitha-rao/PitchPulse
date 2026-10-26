"""Match-state engine: turns the event stream into statistics, match states and Moments.

Everything here is deterministic. Each Moment carries a fact pack (ids, values,
units) that the narrative layer must stay faithful to.
"""

from collections import defaultdict
from dataclasses import dataclass, field

from . import metrics as m
from .roster import AWAY, HOME, PLAYERS, TEAMS, opponent

MIN = 60_000
TEAM_IDS = (HOME.id, AWAY.id)


@dataclass
class PlayerStats:
    touches: int = 0
    passes: int = 0
    passes_complete: int = 0
    difficulty_sum: int = 0
    line_breakers: int = 0
    shots: int = 0
    xg: float = 0.0
    goals: int = 0
    assists: int = 0
    sprints: int = 0
    top_speed_kmh: float = 0.0
    carry_m: float = 0.0
    tackles: int = 0
    interceptions: int = 0
    pressures: int = 0

    def as_dict(self) -> dict:
        d = self.__dict__.copy()
        d["pass_accuracy"] = round(100 * self.passes_complete / self.passes) if self.passes else None
        d["avg_difficulty"] = round(self.difficulty_sum / self.passes) if self.passes else None
        d["xg"] = round(self.xg, 2)
        d["carry_m"] = round(self.carry_m)
        return d

    def rating(self) -> float:
        raw = (6.0 + 1.0 * self.goals + 0.8 * self.assists + 0.15 * self.line_breakers
               + 0.005 * self.passes_complete + 0.05 * (self.tackles + self.interceptions)
               + 0.5 * self.xg + 0.03 * self.sprints)
        return min(10.0, raw)


@dataclass
class Moment:
    id: str
    type: str
    clock_ms: int
    team_id: str | None
    player_id: str | None
    importance: float
    facts: list[dict]
    drivers: list[str]
    storyline: str | None = None
    related_players: list[str] = field(default_factory=list)

    @property
    def minute(self) -> int:
        return self.clock_ms // MIN + 1

    def fact(self, fid: str):
        return next(f["value"] for f in self.facts if f["id"] == fid)

    def as_dict(self) -> dict:
        return {
            "id": self.id, "type": self.type, "clock_ms": self.clock_ms, "minute": self.minute,
            "team_id": self.team_id, "player_id": self.player_id, "importance": round(self.importance, 1),
            "facts": self.facts, "drivers": self.drivers, "storyline": self.storyline,
            "related_players": self.related_players,
        }


class MatchEngine:
    def __init__(self):
        self.clock = 0
        self.period = 1
        self.score = {t: 0 for t in TEAM_IDS}
        self.team_stats = {t: defaultdict(float) for t in TEAM_IDS}
        self.players: dict[str, PlayerStats] = defaultdict(PlayerStats)
        self.log: list[dict] = []  # compact per-event records for rolling windows
        self.segments: list[list] = []  # possession segments [team, start_ms, end_ms]
        self.timeline: list[dict] = []
        self.moments: list[Moment] = []
        self.storylines: dict[str, dict] = {}
        self.records = {"shot_speed": None, "sprint": None, "pass_difficulty": None}
        self.last_minute_tick = 0
        self.cooldowns: dict[str, int] = {}
        self.last_pass_by_possession: dict[str, dict] = {}
        self.finished = False
        self.milestone_done = False
        self._wp_cache = self._wp()

    # ---- rolling windows ----------------------------------------------
    def _window(self, ms: int, end: int | None = None) -> list[dict]:
        end = self.clock if end is None else end
        lo = end - ms
        return [r for r in self.log if lo <= r["t"] <= end]

    def _possession_share(self, ms: int, end: int | None = None) -> dict[str, float]:
        end = self.clock if end is None else end
        lo = end - ms
        tot = {t: 0.0 for t in TEAM_IDS}
        for team, s, e in self.segments:
            e = end if e is None else e
            ov = min(e, end) - max(s, lo)
            if ov > 0:
                tot[team] += ov
        total = sum(tot.values()) or 1
        return {t: tot[t] / total for t in TEAM_IDS}

    def rolling(self, end: int | None = None) -> dict:
        """Rolling match-state indices at time `end` (defaults to now)."""
        end = self.clock if end is None else end
        w5 = self._window(5 * MIN, end)
        w10 = self._window(10 * MIN, end)
        w20 = self._window(20 * MIN, end)
        share5 = self._possession_share(5 * MIN, end)
        out: dict = {"control": {}, "pressure_index": {}, "completion": {}}
        for t in TEAM_IDS:
            passes = [r for r in w5 if r["k"] == "pass" and r["team"] == t]
            cmp_ = sum(r["ok"] for r in passes) / len(passes) if passes else 0.0
            poss = len({r["pos"] for r in w5 if r["team"] == t and r["k"] in ("pass", "carry", "shot")}) or 1
            seq = sum(r["ok"] for r in passes) / poss
            control = 100 * share5[t] * (0.5 + 0.5 * cmp_) * (0.6 + 0.4 * min(seq / 6, 1))
            out["control"][t] = round(control, 1)
            out["completion"][t] = round(100 * cmp_)
            opp_passes = sum(1 for r in w10 if r["k"] == "pass" and r["team"] == opponent(t))
            presses = sum(1 for r in w10 if r["k"] == "pressure" and r["team"] == t)
            out["pressure_index"][t] = round(10 * presses / opp_passes, 1) if opp_passes else 0.0
        mins5 = max(1, min(5, end / MIN))
        disorder = sum(1 for r in w5 if r["k"] in ("possession_change", "tackle", "foul")) \
            + 0.25 * sum(1 for r in w5 if r["k"] == "pressure")
        out["chaos"] = round(min(100.0, disorder / mins5 * 16), 1)
        out["control_diff"] = round(out["control"][HOME.id] - out["control"][AWAY.id], 1)
        f3 = {t: sum(1 for r in w10 if r["team"] == t and r.get("f3")) for t in TEAM_IDS}
        out["field_tilt_home"] = round(100 * f3[HOME.id] / (sum(f3.values()) or 1))
        out["tempo"] = round(sum(1 for r in w5 if r["k"] in ("pass", "carry", "shot")) / mins5, 1)
        xg = {t: sum(r.get("xg", 0) for r in w20 if r["team"] == t) for t in TEAM_IDS}
        out["xg_share_home"] = round((xg[HOME.id] + 0.3) / (xg[HOME.id] + xg[AWAY.id] + 0.6), 3)
        out["possession_home"] = round(100 * self._possession_share(10 * MIN, end)[HOME.id])
        return out

    def _wp(self, score: dict | None = None, minute: float | None = None) -> dict:
        score = score or self.score
        minute = min(90, self.clock / MIN) if minute is None else minute
        share = self.rolling()["xg_share_home"] if self.log else 0.5
        return m.win_probability(score[HOME.id], score[AWAY.id], minute, share)

    # ---- ingest ------------------------------------------------------
    def ingest(self, ev: dict) -> list[Moment]:
        self.clock = ev["clock_ms"]
        self.period = ev["period"]
        out: list[Moment] = []
        out += self._minute_ticks()
        t, pid, typ = ev.get("team_id"), ev.get("player_id"), ev["type"]
        q = ev.get("qualifiers", {})
        rec = {"t": self.clock, "k": typ, "team": t, "pos": ev.get("possession_id"), "ok": 0}
        if "start_xy" in ev and t:
            ax, _ = m.attack_frame(t, *ev["start_xy"])
            rec["f3"] = ax > 70 and typ in ("pass", "carry", "shot")

        # Possession segments follow whoever is on the ball.
        if t and typ in ("pass", "carry", "shot", "possession_change", "kickoff", "period_start"):
            if not self.segments or self.segments[-1][0] != t:
                if self.segments:
                    self.segments[-1][2] = self.clock
                self.segments.append([t, self.clock, None])

        if not self.milestone_done and pid == "hfc_08" and typ in ("pass", "carry"):
            self.milestone_done = True
            out.append(self._milestone_moment(pid))

        handler = getattr(self, f"_on_{typ}", None)
        if handler:
            rec_out = handler(ev, q, rec)
            if rec_out:
                out += rec_out
        self.log.append(rec)
        # Keep the log bounded to what any window needs.
        if len(self.log) > 4000:
            self.log = self.log[-3000:]
        self.moments += out
        return out

    # ---- per-type handlers -------------------------------------------
    def _touch(self, pid: str | None) -> None:
        if pid:
            self.players[pid].touches += 1

    def _on_pass(self, ev, q, rec):
        t, pid = ev["team_id"], ev["player_id"]
        ok = ev["outcome"] == "complete"
        rec["ok"] = int(ok)
        ps = self.players[pid]
        self._touch(pid)
        ps.passes += 1
        ps.passes_complete += ok
        ps.difficulty_sum += q["difficulty"]
        self.team_stats[t]["passes"] += 1
        self.team_stats[t]["passes_complete"] += ok
        self.last_pass_by_possession[ev["possession_id"]] = ev
        out = []
        if ok and q["difficulty"] >= 75 and q["forward_m"] >= 15 and q["bypassed"] >= 3:
            ps.line_breakers += 1
            if self._cool(f"lb_{t}", 6):
                out.append(self._line_breaker(ev, q))
        if ok and (self.records["pass_difficulty"] is None or q["difficulty"] > self.records["pass_difficulty"]["value"]):
            self.records["pass_difficulty"] = {"value": q["difficulty"], "player_id": pid, "clock_ms": self.clock}
        return out

    def _on_carry(self, ev, q, rec):
        pid = ev["player_id"]
        ps = self.players[pid]
        self._touch(pid)
        ps.carry_m += q["distance_m"]
        speed = q["speed_kmh"]
        ps.top_speed_kmh = max(ps.top_speed_kmh, speed)
        out = []
        if q["sprint"]:
            ps.sprints += 1
            prev = self.records["sprint"]
            is_record = prev is None or speed > prev["value"]
            if is_record:
                self.records["sprint"] = {"value": speed, "player_id": pid, "clock_ms": self.clock}
            if speed >= 32 and q["distance_m"] >= 8 and self._cool(f"sprint_{ev['team_id']}", 8):
                out.append(self._sprint(ev, q, is_record, prev))
        return out

    def _on_shot(self, ev, q, rec):
        t, pid = ev["team_id"], ev["player_id"]
        ps = self.players[pid]
        self._touch(pid)
        ps.shots += 1
        ps.xg += q["xg"]
        rec["xg"] = q["xg"]
        self.team_stats[t]["shots"] += 1
        self.team_stats[t]["xg"] += q["xg"]
        speed = ev.get("ball_speed_kmh", 0)
        if self.records["shot_speed"] is None or speed > self.records["shot_speed"]["value"]:
            self.records["shot_speed"] = {"value": speed, "player_id": pid, "clock_ms": self.clock}
        if ev["outcome"] != "goal" and q["xg"] >= 0.2:
            return [self._big_chance(ev, q)]
        return []

    def _on_goal(self, ev, q, rec):
        t, pid = ev["team_id"], ev["player_id"]
        before = self._wp_cache
        trailing_by = self.score[opponent(t)] - self.score[t]
        self.score = dict(q["score"])
        self.players[pid].goals += 1
        self.team_stats[t]["goals"] += 1
        after = self._wp()
        self._wp_cache = after
        assist = self.last_pass_by_possession.get(ev["possession_id"])
        if assist and assist["team_id"] == t and assist.get("receiver_id") == pid:
            self.players[assist["player_id"]].assists += 1
        else:
            assist = None
        return [self._goal(ev, q, before, after, assist, trailing_by)]

    def _on_pressure(self, ev, q, rec):
        self.players[ev["player_id"]].pressures += 1
        self.team_stats[ev["team_id"]]["pressures"] += 1
        return []

    def _on_tackle(self, ev, q, rec):
        self.players[ev["player_id"]].tackles += 1
        return []

    def _on_interception(self, ev, q, rec):
        self.players[ev["player_id"]].interceptions += 1
        return []

    def _on_card(self, ev, q, rec):
        t, pid = ev["team_id"], ev["player_id"]
        self.team_stats[t]["cards"] += 1
        tempo = self.rolling()["tempo"]
        facts = [
            self._f("card", "Card", q["card"]),
            self._f("player", "Player", PLAYERS[pid].name),
            self._f("fouled", "Fouled player", PLAYERS[q["on_player"]].name),
            self._f("minute", "Minute", self.clock // MIN + 1, "min"),
            self._f("tempo", "Tempo, last 5 min", tempo, "actions/min"),
        ]
        return [self._moment("card", t, pid, 45, facts, ["card", "fouled"], related=[q["on_player"]])]

    def _on_period_end(self, ev, q, rec):
        if self.segments:
            self.segments[-1][2] = self.clock
        if q.get("final"):
            self.finished = True
        self._snapshot()
        return []

    # ---- minute ticks: pattern moments -------------------------------
    def _minute_ticks(self) -> list[Moment]:
        out = []
        while self.clock >= (self.last_minute_tick + 1) * MIN:
            self.last_minute_tick += 1
            self._snapshot(self.last_minute_tick * MIN)
            out += self._patterns()
        return out

    def _snapshot(self, at: int | None = None) -> None:
        at = self.clock if at is None else at
        r = self.rolling(at)
        self._wp_cache = self._wp()
        self.timeline.append({
            "minute": round(at / MIN, 1),
            "win_prob": self._wp_cache,
            "control_diff": r["control_diff"],
            "chaos": r["chaos"],
            "pressure_index": r["pressure_index"],
            "field_tilt_home": r["field_tilt_home"],
            "tempo": r["tempo"],
            "xg": {t: round(self.team_stats[t]["xg"], 2) for t in TEAM_IDS},
            "score": dict(self.score),
        })

    def _tl(self, minutes_ago: int) -> dict | None:
        target = self.last_minute_tick - minutes_ago
        for s in reversed(self.timeline):
            if round(s["minute"]) == target:
                return s
        return None

    def _patterns(self) -> list[Moment]:
        out = []
        now = self.timeline[-1]
        minute = self.last_minute_tick
        if minute < 12:
            return out
        then10 = self._tl(10)
        then5 = self._tl(5)
        # Pressing surge or fade.
        if then10:
            for t in TEAM_IDS:
                a, b = then10["pressure_index"][t], now["pressure_index"][t]
                if a >= 3 and b <= a * 0.6 and self._cool(f"press_{t}", 15):
                    out.append(self._press_shift(t, a, b, "press_fade", now))
                elif b >= 3 and b >= max(a, 0.5) * 1.6 and self._cool(f"press_{t}", 15):
                    out.append(self._press_shift(t, a, b, "press_surge", now))
        # Control swing: who controls the match flips decisively.
        if then5 and minute >= 15:
            a, b = then5["control_diff"], now["control_diff"]
            if (a <= 0 < b or b < 0 <= a) and abs(b) >= 10 and abs(b - a) >= 15 and self._cool("control", 10):
                out.append(self._control_swing(a, b, now))
        # Rhythm shift: tempo changes sharply between consecutive 5-minute blocks.
        if then5 and minute >= 15:
            a, b = then5["tempo"], now["tempo"]
            if a > 0 and abs(b - a) / a >= 0.3 and self._cool("rhythm", 12):
                out.append(self._rhythm(a, b, now))
        # Opening storyline for the high press once it is established.
        if minute == 20 and "press" not in self.storylines:
            hi = max(TEAM_IDS, key=lambda t: now["pressure_index"][t])
            lo = opponent(hi)
            if now["pressure_index"][hi] >= 1.4 * max(now["pressure_index"][lo], 0.1):
                self.storylines["press"] = {"id": "press", "team_id": hi, "opened": minute,
                                            "status": "open", "peak": now["pressure_index"][hi]}
        return out

    # ---- moment builders ---------------------------------------------
    def _f(self, fid: str, label: str, value, unit: str | None = None) -> dict:
        f = {"id": fid, "label": label, "value": value}
        if unit:
            f["unit"] = unit
        return f

    def _cool(self, key: str, minutes: int) -> bool:
        last = self.cooldowns.get(key)
        if last is not None and self.clock - last < minutes * MIN:
            return False
        self.cooldowns[key] = self.clock
        return True

    def _moment(self, type_, team, pid, importance, facts, drivers, storyline=None, related=None) -> Moment:
        mid = f"mom_{len(self.moments) + 1:03d}_{type_}"
        # Avoid id collisions for several moments produced by one event.
        while any(x.id == mid for x in self.moments):
            mid += "b"
        mo = Moment(mid, type_, self.clock, team, pid, importance, facts, drivers, storyline, related or [])
        return mo

    def _milestone_moment(self, pid: str) -> Moment:
        p = PLAYERS[pid]
        apps = p.club_apps + 1
        self.storylines["player_" + pid] = {"id": "player_" + pid, "player_id": pid, "status": "open",
                                            "opened": self.clock // MIN + 1}
        facts = [self._f("player", "Player", p.name), self._f("apps", "Club appearances", apps),
                 self._f("club", "Club", TEAMS[pid.split('_')[0]].name)]
        return self._moment("milestone", pid.split("_")[0], pid, 35, facts, ["apps"], "player_" + pid)

    def _line_breaker(self, ev, q) -> Moment:
        pid = ev["player_id"]
        facts = [
            self._f("passer", "Passer", PLAYERS[pid].name),
            self._f("receiver", "Receiver", PLAYERS[ev["receiver_id"]].name),
            self._f("difficulty", "Pass difficulty", q["difficulty"], "/100"),
            self._f("distance", "Pass distance", round(q["distance_m"]), "m"),
            self._f("bypassed", "Opponents bypassed", q["bypassed"]),
            self._f("pressure", "Under pressure", bool(ev["pressure"]["under"])),
            self._f("ball_speed", "Ball speed", round(ev["ball_speed_kmh"]), "km/h"),
            self._f("avg_difficulty", "Match average pass difficulty",
                    round(sum(s.difficulty_sum for s in self.players.values())
                          / max(1, sum(s.passes for s in self.players.values()))), "/100"),
        ]
        return self._moment("line_breaker", ev["team_id"], pid, 30 + q["difficulty"] / 5, facts,
                            ["difficulty", "bypassed", "distance"], related=[ev["receiver_id"]])

    def _sprint(self, ev, q, is_record, prev) -> Moment:
        pid = ev["player_id"]
        facts = [
            self._f("player", "Player", PLAYERS[pid].name),
            self._f("speed", "Top speed", round(q["speed_kmh"], 1), "km/h"),
            self._f("distance", "Carry distance", round(q["distance_m"]), "m"),
            self._f("sprints", "Sprints this match", self.players[pid].sprints),
            self._f("is_record", "Fastest of the match so far", is_record),
        ]
        return self._moment("sprint", ev["team_id"], pid, 25 + (10 if is_record else 0), facts,
                            ["speed", "is_record"])

    def _big_chance(self, ev, q) -> Moment:
        pid = ev["player_id"]
        facts = [
            self._f("player", "Shooter", PLAYERS[pid].name),
            self._f("xg", "Chance quality (xG)", q["xg"]),
            self._f("distance", "Shot distance", round(q["distance_m"]), "m"),
            self._f("outcome", "Outcome", ev["outcome"]),
            self._f("shot_speed", "Shot speed", round(ev["ball_speed_kmh"]), "km/h"),
            self._f("team_xg", "Team xG so far", round(self.team_stats[ev["team_id"]]["xg"], 2)),
        ]
        return self._moment("big_chance", ev["team_id"], pid, 40 + q["xg"] * 60, facts,
                            ["xg", "distance", "outcome"])

    def _goal(self, ev, q, before, after, assist, trailing_by) -> Moment:
        t, pid = ev["team_id"], ev["player_id"]
        side = "home" if t == HOME.id else "away"
        wp_before, wp_after = round(100 * before[side]), round(100 * after[side])
        facts = [
            self._f("scorer", "Scorer", PLAYERS[pid].name),
            self._f("team", "Team", TEAMS[t].name),
            self._f("score_home", HOME.name, self.score[HOME.id]),
            self._f("score_away", AWAY.name, self.score[AWAY.id]),
            self._f("minute", "Minute", self.clock // MIN + 1, "min"),
            self._f("xg", "Chance quality (xG)", q["xg"]),
            self._f("shot_speed", "Shot speed", round(q["shot_speed_kmh"]), "km/h"),
            self._f("wp_before", "Win probability before", wp_before, "%"),
            self._f("wp_after", "Win probability after", wp_after, "%"),
        ]
        drivers = ["wp_before", "wp_after", "xg"]
        related = []
        if assist:
            aq = assist["qualifiers"]
            facts += [
                self._f("assister", "Assist", PLAYERS[assist["player_id"]].name),
                self._f("assist_difficulty", "Assist pass difficulty", aq["difficulty"], "/100"),
                self._f("assist_bypassed", "Opponents bypassed by the assist", aq["bypassed"]),
            ]
            drivers.insert(0, "assist_difficulty")
            related.append(assist["player_id"])
        storyline = None
        press = self.storylines.get("press")
        if press and press["team_id"] != t and press.get("status") == "faded":
            facts.append(self._f("press_now", f"{TEAMS[press['team_id']].short} pressure index now",
                                 self.rolling()["pressure_index"][press["team_id"]], "per 10 passes"))
            facts.append(self._f("press_peak", f"{TEAMS[press['team_id']].short} pressure index at its peak",
                                 press["peak"], "per 10 passes"))
            drivers.append("press_now")
        cb = self.storylines.get("comeback")
        if trailing_by >= 2 and cb is None:
            self.storylines["comeback"] = {"id": "comeback", "team_id": t, "status": "open",
                                           "opened": self.clock // MIN + 1, "from": f"0-{trailing_by}"}
            storyline = "comeback"
        elif cb and cb["team_id"] == t:
            storyline = "comeback"
            if self.score[t] > self.score[opponent(t)]:
                cb["status"] = "complete"
                facts.append(self._f("comeback_from", "Came back from", cb["from"]))
            elif self.score[t] == self.score[opponent(t)]:
                cb["status"] = "level"
        elif trailing_by <= -1 and self.score[t] - self.score[opponent(t)] >= 2:
            storyline = None
        swing = abs(wp_after - wp_before)
        if storyline:
            facts.append(self._f("storyline", "Storyline", storyline))
        return self._moment("goal", t, pid, 70 + swing, facts, drivers, storyline, related)

    def _press_shift(self, t, a, b, kind, now) -> Moment:
        press = self.storylines.get("press")
        storyline = None
        if press and press["team_id"] == t and kind == "press_fade":
            if press["status"] != "faded":
                press["status"] = "faded"
                press["faded_at"] = self.last_minute_tick
                press["faded_to"] = b
            storyline = "press"
        opp = opponent(t)
        facts = [
            self._f("team", "Pressing team", TEAMS[t].name),
            self._f("press_then", "Pressure index 10 min ago", a, "per 10 passes"),
            self._f("press_now", "Pressure index now", b, "per 10 passes"),
            self._f("opp_completion", f"{TEAMS[opp].short} pass completion, last 5 min",
                    self.rolling()["completion"][opp], "%"),
            self._f("field_tilt", f"{HOME.short} share of final-third touches", now["field_tilt_home"], "%"),
        ]
        imp = 35 + min(30, abs(b - a) * 4)
        return self._moment(kind, t, None, imp, facts, ["press_then", "press_now", "opp_completion"], storyline)

    def _control_swing(self, a, b, now) -> Moment:
        leader = HOME.id if b > 0 else AWAY.id
        r = self.rolling()
        facts = [
            self._f("team", "Team taking control", TEAMS[leader].name),
            self._f("control_then", f"Control gap ({HOME.short} minus {AWAY.short}) 5 min ago", a),
            self._f("control_now", f"Control gap ({HOME.short} minus {AWAY.short}) now", b),
            self._f("possession", f"{HOME.short} possession, last 10 min", r["possession_home"], "%"),
            self._f("completion", f"{TEAMS[leader].short} pass completion, last 5 min", r["completion"][leader], "%"),
            self._f("chaos", "Chaos index", now["chaos"], "/100"),
        ]
        return self._moment("control_swing", leader, None, 40 + abs(b - a) / 2, facts,
                            ["control_then", "control_now", "completion"])

    def _rhythm(self, a, b, now) -> Moment:
        facts = [
            self._f("tempo_then", "Tempo, previous 5 min", a, "actions/min"),
            self._f("tempo_now", "Tempo, last 5 min", b, "actions/min"),
            self._f("change", "Change", round(100 * (b - a) / a), "%"),
            self._f("chaos", "Chaos index", now["chaos"], "/100"),
        ]
        return self._moment("rhythm_shift", None, None, 28 + min(20, abs(b - a) * 3), facts,
                            ["tempo_then", "tempo_now", "change"])

    # ---- views -------------------------------------------------------
    def state(self) -> dict:
        r = self.rolling() if self.log else None
        return {
            "clock_ms": self.clock,
            "period": self.period,
            "score": self.score,
            "win_prob": self._wp_cache,
            "rolling": r,
            "teams": {t: {k: round(v, 2) for k, v in s.items()} for t, s in self.team_stats.items()},
            "records": self.records,
        }

    def player_card(self, pid: str) -> dict:
        return {"player_id": pid, "name": PLAYERS[pid].name, **self.players[pid].as_dict(),
                "rating": round(self.players[pid].rating(), 1)}

    def player_of_match(self) -> str:
        return max(self.players, key=lambda p: self.players[p].rating())
