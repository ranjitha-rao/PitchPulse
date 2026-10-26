"""Narrative layer: template captions, optional model captions, and the grounding validator.

Template captions are instant and always faithful. When Azure OpenAI is
configured, a model caption is generated from the same fact pack and only
shipped if every number in it can be traced back to a fact.
"""

import json
import os
import re

import httpx

from .i18n import RECAP, T, WORDS
from .roster import AWAY, HOME, PLAYERS, TEAMS

NUM = re.compile(r"-?\d+(?:[.,]\d+)?")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789.")


def _context(facts: list[dict], lang: str) -> dict:
    ctx = {f["id"]: f["value"] for f in facts}
    if "outcome" in ctx:
        ctx["outcome_l"] = WORDS[lang].get(ctx["outcome"], ctx["outcome"])
    if "card" in ctx:
        ctx["card_l"] = WORDS[lang].get(ctx["card"], ctx["card"])
    if "change" in ctx:
        ctx["up"] = ctx["change"] > 0
    return ctx


def _holds(cond: str, ctx: dict) -> bool:
    if cond.startswith("!"):
        return not ctx.get(cond[1:])
    return bool(ctx.get(cond))


def render(kind: str, facts: list[dict], voice: str, lang: str) -> str:
    ctx = _context(facts, lang)
    parts = T[lang][kind][voice]
    return "".join(text.format(**ctx) for conds, text in parts if all(_holds(c, ctx) for c in conds))


# ---- grounding ----------------------------------------------------------
def numbers_in(text: str) -> list[float]:
    text = text.translate(ARABIC_DIGITS)
    out = []
    for tok in NUM.findall(text):
        try:
            out.append(float(tok.replace(",", ".")))
        except ValueError:
            pass
    return out


def allowed_numbers(facts: list[dict]) -> set[float]:
    allowed: set[float] = set()
    for f in facts:
        v = f["value"]
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            allowed |= {float(v), abs(float(v)), round(float(v)), round(abs(float(v)))}
            if isinstance(v, float) and v < 1:
                allowed.add(round(v * 100))  # 0.29 xG may be phrased as 29%
        elif isinstance(v, str):
            allowed |= set(numbers_in(v)) | {abs(n) for n in numbers_in(v)}
    # Numbers that are part of the rendering vocabulary rather than claims.
    allowed |= {10.0, 100.0}
    return allowed


def validate(text: str, facts: list[dict]) -> tuple[bool, list[float]]:
    """True when every number in the text is backed by a fact in the pack."""
    allowed = allowed_numbers(facts)
    bad = [n for n in numbers_in(text) if n not in allowed and abs(n) not in allowed]
    return (not bad, bad)


# ---- optional model captions --------------------------------------------
LANG_NAMES = {"en": "English", "es": "Spanish", "ar": "Arabic"}
VOICE_RULES = {
    "casual": "Write for a casual fan: one or two short, vivid sentences, at most 160 characters, "
              "plain words, at most two numbers.",
    "analyst": "Write for a data-hungry analyst: precise and compact, at most 240 characters, "
               "lead with the metrics that explain the moment.",
}


class ModelNarrator:
    """Azure OpenAI chat completions. Disabled unless the environment configures it."""

    def __init__(self):
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
        self.key = os.getenv("AZURE_OPENAI_API_KEY", "")
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
        self.enabled = bool(self.endpoint and self.key and self.deployment)
        self.client = httpx.AsyncClient(timeout=12) if self.enabled else None

    async def _chat(self, system: str, user: str) -> dict | None:
        url = f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions?api-version={self.api_version}"
        body = {
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.6,
            "max_tokens": 300,
            "response_format": {"type": "json_object"},
        }
        try:
            r = await self.client.post(url, headers={"api-key": self.key}, json=body)
            r.raise_for_status()
            return json.loads(r.json()["choices"][0]["message"]["content"])
        except (httpx.HTTPError, KeyError, ValueError):
            return None

    async def caption(self, moment: dict, voice: str, lang: str, focus: str | None = None) -> dict | None:
        if not self.enabled:
            return None
        system = (
            "You are a football broadcast graphics writer. You explain why a moment matters, "
            "using ONLY the facts provided. Never invent numbers, names or events. Every number you "
            "write must appear in the facts. " + VOICE_RULES[voice] +
            f" Write natively in {LANG_NAMES[lang]}, using natural football vocabulary for that language. "
            'Reply as JSON: {"text": "...", "cited": ["fact_id", ...]}.'
        )
        payload = {
            "moment_type": moment["type"], "minute": moment["minute"],
            "teams": {HOME.id: HOME.name, AWAY.id: AWAY.name},
            "facts": moment["facts"], "key_drivers": moment["drivers"],
            "storyline": moment.get("storyline"),
        }
        if focus:
            payload["viewer_follows_player"] = PLAYERS[focus].name
        out = await self._chat(system, json.dumps(payload, ensure_ascii=False))
        if not out or not isinstance(out.get("text"), str):
            return None
        ok, bad = validate(out["text"], moment["facts"] + [{"id": "minute", "value": moment["minute"]}])
        if not ok:
            return None
        return {"text": out["text"].strip(), "cited": out.get("cited", [])}

    async def recap(self, recap: dict, lang: str) -> str | None:
        if not self.enabled:
            return None
        system = (
            "You write a 4-6 sentence football match recap for a streaming app, using ONLY the facts "
            f"given. Every number must appear in the facts. Write natively in {LANG_NAMES[lang]}. "
            'Reply as JSON: {"text": "..."}.'
        )
        out = await self._chat(system, json.dumps(recap["facts"], ensure_ascii=False))
        if not out or not isinstance(out.get("text"), str):
            return None
        facts = [{"id": k, "value": v} for k, v in _flatten(recap["facts"]).items()]
        ok, _ = validate(out["text"], facts)
        return out["text"].strip() if ok else None


def _flatten(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out |= _flatten(v, f"{prefix}{k}.")
        elif isinstance(v, list):
            out[f"{prefix}{k}"] = ", ".join(map(str, v))
        else:
            out[f"{prefix}{k}"] = v
    return out


# ---- recaps -------------------------------------------------------------
def recap_facts(engine, half: bool = False) -> dict:
    s = engine.score
    facts: dict = {
        "home": HOME.name, "away": AWAY.name, "home_goals": s[HOME.id], "away_goals": s[AWAY.id],
        "xg": {HOME.id: round(engine.team_stats[HOME.id]["xg"], 2), AWAY.id: round(engine.team_stats[AWAY.id]["xg"], 2)},
        "scorers": [f"{PLAYERS[mo.player_id].name} {mo.minute}'" for mo in engine.moments if mo.type == "goal"],
    }
    cb = engine.storylines.get("comeback")
    if cb and cb["status"] == "complete" and not half:
        late = sum(1 for mo in engine.moments if mo.type == "goal" and mo.team_id == cb["team_id"] and mo.minute > 60)
        facts["comeback"] = {"team": TEAMS[cb["team_id"]].name, "from": cb["from"], "goals_after_60": late}
    press = engine.storylines.get("press")
    if press and press.get("status") == "faded":
        facts["press"] = {"team": TEAMS[press["team_id"]].name, "peak": press["peak"], "now": press["faded_to"],
                          "faded_at": press["faded_at"]}
    if engine.timeline and not half:
        winner = HOME.id if s[HOME.id] > s[AWAY.id] else AWAY.id if s[AWAY.id] > s[HOME.id] else None
        if winner:
            side = "home" if winner == HOME.id else "away"
            low = min(engine.timeline, key=lambda r: r["win_prob"][side])
            facts["win_prob_low"] = {"team": TEAMS[winner].name, "pct": round(100 * low["win_prob"][side]),
                                     "minute": int(low["minute"])}
    pom = engine.player_of_match()
    card = engine.player_card(pom)
    facts["player_of_match"] = {"name": card["name"], "team": TEAMS[pom.split('_')[0]].name,
                                "assists": card["assists"], "goals": card["goals"],
                                "line_breakers": card["line_breakers"], "passes_complete": card["passes_complete"]}
    r = engine.records
    if r["sprint"] and r["shot_speed"]:
        facts["records"] = {"sprint": PLAYERS[r["sprint"]["player_id"]].name, "sprint_kmh": r["sprint"]["value"],
                            "shot": PLAYERS[r["shot_speed"]["player_id"]].name, "shot_kmh": round(r["shot_speed"]["value"])}
    return facts


def render_recap(facts: dict, lang: str, half: bool = False) -> dict:
    R = RECAP[lang]
    lines = [R["score"].format(home=facts["home"], away=facts["away"], hg=facts["home_goals"], ag=facts["away_goals"])]
    if half:
        hg, ag = facts["home_goals"], facts["away_goals"]
        if hg == ag:
            lines.append(R["level"])
        else:
            lead = facts["home"] if hg > ag else facts["away"]
            lines.append(R["lead"].format(team=lead, scorers=", ".join(facts["scorers"])))
    if "comeback" in facts:
        lines.append(R["comeback"].format(team=facts["comeback"]["team"], from_score=facts["comeback"]["from"],
                                          n=facts["comeback"]["goals_after_60"]))
    if "press" in facts:
        p = facts["press"]
        lines.append(R["press"].format(team=p["team"], peak=p["peak"], now=p["now"], faded_at=p["faded_at"]))
    if "win_prob_low" in facts:
        w = facts["win_prob_low"]
        lines.append(R["wp"].format(team=w["team"], low=w["pct"], low_min=w["minute"]))
    lines.append(R["xg"].format(home=facts["home"], away=facts["away"], hxg=facts["xg"][HOME.id], axg=facts["xg"][AWAY.id]))
    if not half:
        p = facts["player_of_match"]
        lines.append(R["pom"].format(name=p["name"], team=p["team"], assists=p["assists"],
                                     line_breakers=p["line_breakers"], passes_complete=p["passes_complete"]))
        if "records" in facts:
            rr = facts["records"]
            lines.append(R["fastest"].format(sprint_name=rr["sprint"], sprint_speed=rr["sprint_kmh"],
                                             shot_name=rr["shot"], shot_speed=rr["shot_kmh"]))
    return {"title": R["title_ht" if half else "title_ft"], "lines": lines, "text": " ".join(lines)}
