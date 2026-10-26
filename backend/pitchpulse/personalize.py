"""Personalization: decides which Moments reach which viewer, and builds overlay cues."""

from dataclasses import dataclass, field

from .engine import MIN, Moment
from .i18n import RTL, voice
from .narrate import render
from .roster import MATCH_META, PLAYERS

ALWAYS = {"goal", "card"}
CASUAL_TYPES = {"goal", "card", "big_chance", "milestone", "sprint", "line_breaker", "press_fade", "control_swing"}
# Minimum match time between non-goal cues, per mode.
GAP_MS = {"casual": 4 * MIN, "analyst": 1 * MIN, "player": 2 * MIN}

SLOTS = {
    "goal": ("banner", 9000), "card": ("lower_third", 7000),
    "big_chance": ("player_tag", 6000), "line_breaker": ("player_tag", 6000),
    "sprint": ("player_tag", 5000), "milestone": ("lower_third", 7000),
    "press_fade": ("stat_bug", 8000), "press_surge": ("stat_bug", 8000),
    "control_swing": ("stat_bug", 8000), "rhythm_shift": ("stat_bug", 7000),
    "player_card": ("player_card", 9000),
}


@dataclass
class Profile:
    mode: str = "casual"  # casual | analyst | player
    club: str | None = None
    player: str | None = None
    lang: str = "en"
    last_cue_ms: int = field(default=-10 * MIN)

    def update(self, **kw) -> None:
        for k in ("mode", "lang"):
            if kw.get(k):
                setattr(self, k, kw[k])
        for k in ("club", "player"):
            if k in kw:
                setattr(self, k, kw[k] or None)
        if self.mode == "player" and not self.player:
            self.player = "hfc_08"


def involves(mo: Moment, pid: str | None) -> bool:
    return bool(pid) and (mo.player_id == pid or pid in mo.related_players)


def relevance(mo: Moment, p: Profile) -> float | None:
    """Priority of a moment for this viewer, or None when it should not be shown."""
    if p.mode == "casual":
        if mo.type not in CASUAL_TYPES:
            return None
        if mo.type == "sprint" and not mo.fact("is_record"):
            return None
        if mo.type == "line_breaker" and mo.importance < 47:
            return None
        if mo.type in ("press_fade", "control_swing") and not mo.storyline and mo.importance < 55:
            return None
    if p.mode == "player" and mo.type not in ALWAYS and not involves(mo, p.player):
        return None
    score = mo.importance
    if p.club and mo.team_id == p.club:
        score += 15
    if involves(mo, p.player):
        score += 25
    if mo.type not in ALWAYS and not involves(mo, p.player) and mo.clock_ms - p.last_cue_ms < GAP_MS[p.mode]:
        return None
    return score


def build_cue(mo: Moment, p: Profile, langs: list[str]) -> dict:
    slot, duration = SLOTS[mo.type]
    v = voice(p.mode)
    return {
        "cue_id": f"cue_{mo.id}",
        "version": 1,
        "match_id": MATCH_META["match_id"],
        "clock_in_ms": mo.clock_ms,
        "minute": mo.minute,
        "duration_ms": duration,
        "slot": slot,
        "template": mo.type,
        "priority": round(min(100, relevance(mo, p) or mo.importance)),
        "mode": p.mode,
        "team_id": mo.team_id,
        "player_id": mo.player_id,
        "data": {f["id"]: f["value"] for f in mo.facts},
        "text": {lang: render(mo.type, mo.facts, v, lang) for lang in langs},
        "variants": {vv: {lang: render(mo.type, mo.facts, vv, lang) for lang in langs} for vv in ("casual", "analyst")},
        "dir": {lang: "rtl" if lang in RTL else "ltr" for lang in langs},
        "explain": {"facts": mo.facts, "drivers": mo.drivers, "storyline": mo.storyline},
        "source": "template",
    }


def player_card_cue(engine, p: Profile, langs: list[str]) -> dict:
    card = engine.player_card(p.player)
    card["top_speed"] = card.pop("top_speed_kmh")
    facts = [{"id": k, "value": v} for k, v in card.items() if v is not None]
    v = voice(p.mode)
    return {
        "cue_id": f"cue_pc_{p.player}_{engine.clock // MIN}",
        "version": 1,
        "match_id": MATCH_META["match_id"],
        "clock_in_ms": engine.clock,
        "minute": engine.clock // MIN + 1,
        "duration_ms": SLOTS["player_card"][1],
        "slot": "player_card",
        "template": "player_card",
        "priority": 60,
        "mode": p.mode,
        "team_id": p.player.split("_")[0],
        "player_id": p.player,
        "data": card,
        "text": {lang: render("player_card", facts, v, lang) for lang in langs},
        "dir": {lang: "rtl" if lang in RTL else "ltr" for lang in langs},
        "explain": {"facts": facts, "drivers": ["line_breakers", "passes_complete"], "storyline": f"player_{p.player}"},
        "source": "template",
        "name": PLAYERS[p.player].name,
    }
