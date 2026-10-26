"""The newsroom: four agents that turn engine moments into on-air captions.

  Analyst      reads each moment with the engine's tools (match state, rolling metrics) and writes a
               brief: what happened, what drove it, and the story it belongs to.
  Producer     decides, for each viewer, which briefs go on air, in which slot and at what priority.
  Narrator     writes the caption from the brief's fact pack: templates instantly, and Azure OpenAI
               when it is configured.
  FactChecker  checks every number in a caption against the fact pack. A rejected draft goes back to
               the Narrator with the numbers it could not trace; after MAX_DRAFTS the template stays.

Numbers come from code; words come from the model. Every step is recorded on the cue as `trace`,
which the Studio view shows next to the facts.
"""

from dataclasses import dataclass, field

from .engine import Moment
from .i18n import voice
from .narrate import ModelNarrator, caption_facts, render, validate
from .personalize import ALWAYS, SLOTS, Profile, build_cue, relevance
from .roster import TEAMS

AGENTS = [
    {"id": "analyst", "name": "Analyst", "role": "Reads each moment with the engine's tools and writes a brief"},
    {"id": "producer", "name": "Producer", "role": "Picks what goes on air for each viewer, and where"},
    {"id": "narrator", "name": "Narrator", "role": "Writes the caption from the facts (Azure OpenAI or templates)"},
    {"id": "fact_checker", "name": "Fact-checker", "role": "Rejects any caption with a number it can't trace"},
]


def step(agent: str, action: str, detail: str, ok: bool | None = None) -> dict:
    return {"agent": agent, "action": action, "detail": detail, "ok": ok}


@dataclass
class Brief:
    moment: Moment
    angle: str
    context: dict
    trace: list[dict] = field(default_factory=list)


class Analyst:
    """Turns raw moments into briefs, using the engine as its tools."""

    def brief(self, mo: Moment, engine) -> Brief:
        state = engine.state()
        labels = {f["id"]: f.get("label") or f["id"] for f in mo.facts}
        drivers = ", ".join(str(labels.get(d, d)) for d in mo.drivers) or "no single driver"
        angle = f"{mo.type.replace('_', ' ')} at {mo.minute}', driven by {drivers}"
        if mo.storyline:
            angle += f"; part of the '{mo.storyline}' story"
        rolling = state["rolling"] or {}
        context = {"score": state["score"], "win_prob": state["win_prob"], "chaos": rolling.get("chaos"),
                   "control_diff": rolling.get("control_diff")}
        score = "-".join(str(state["score"][t]) for t in TEAMS)
        tools = f"Called match_state (score {score})"
        if rolling:
            tools += f" and rolling_metrics (chaos {rolling['chaos']}, control swing {rolling['control_diff']})"
        detail = f"{tools}. Angle: {angle}. Newsworthiness {round(mo.importance)}/100."
        return Brief(mo, angle, context, [step("Analyst", "brief", detail)])


class Producer:
    """Ranks briefs for one viewer and books the winners into overlay slots."""

    def select(self, briefs: list[Brief], profile: Profile, limit: int = 2) -> list[Brief]:
        """The briefs to put on air this tick, best first. Owns the per-mode rate limit (profile.last_cue_ms)."""
        candidates = sorted(((relevance(b.moment, profile), b) for b in briefs),
                            key=lambda r: -(r[0] if r[0] is not None else -1))
        picked = []
        for _, b in candidates:
            score = relevance(b.moment, profile)  # re-scored: an earlier pick may have used up the gap
            if score is None or len(picked) == limit:
                continue
            why = [f"{profile.mode} viewer"]
            if profile.club and b.moment.team_id == profile.club:
                why.append(f"favours {TEAMS[profile.club].short}")
            if profile.player and (b.moment.player_id == profile.player or profile.player in b.moment.related_players):
                why.append("involves the followed player")
            slot = SLOTS[b.moment.type][0]
            b.trace.append(step("Producer", "book", f"On air in the {slot} slot at priority {round(min(100, score))} "
                                f"({', '.join(why)}) out of {len(briefs)} moment(s) this tick."))
            if b.moment.type not in ALWAYS:
                profile.last_cue_ms = b.moment.clock_ms
            picked.append(b)
        return picked


class Narrator:
    """Writes captions: a template version instantly, and a model version when available."""

    def __init__(self, model: ModelNarrator):
        self.model = model

    def template(self, b: Brief, profile: Profile) -> str:
        return render(b.moment.type, b.moment.facts, voice(profile.mode), profile.lang)

    async def draft(self, b: Brief, profile: Profile, feedback: list[float] | None = None) -> dict | None:
        return await self.model.draft(b.moment.as_dict(), voice(profile.mode), profile.lang, profile.player, feedback)


class FactChecker:
    """Every number in a caption must trace back to a fact in the brief."""

    def check(self, text: str, b: Brief) -> tuple[bool, list[float]]:
        return validate(text, caption_facts(b.moment.as_dict()))


class Newsroom:
    """Orchestrates the four agents for one viewer session."""

    MAX_DRAFTS = 2

    def __init__(self, model: ModelNarrator):
        self.model = model
        self.analyst = Analyst()
        self.producer = Producer()
        self.narrator = Narrator(model)
        self.checker = FactChecker()

    def on_air(self, moments: list[Moment], engine, profile: Profile, langs: list[str]) -> list[tuple[dict, Brief]]:
        """Version 1 cues for this tick: briefed, booked, template-narrated and fact-checked."""
        briefs = [self.analyst.brief(mo, engine) for mo in moments]
        out = []
        for b in self.producer.select(briefs, profile):
            cue = build_cue(b.moment, profile, langs)
            text = cue["text"][profile.lang]
            b.trace.append(step("Narrator", "template", f"Instant template caption in {profile.lang} "
                                f"({voice(profile.mode)} voice)."))
            ok, bad = self.checker.check(text, b)
            b.trace.append(step("Fact-checker", "check", "Every number traced to a fact." if ok
                                else f"Untraced numbers: {bad}.", ok))
            cue["trace"] = list(b.trace)
            out.append((cue, b))
        return out

    async def rewrite(self, cue: dict, b: Brief, profile: Profile) -> dict | None:
        """Version 2: model drafts, each checked; a rejection goes back to the Narrator with feedback.

        Returns the version 2 cue, or the version 1 cue with the rejections added to its trace.
        """
        if not self.model.enabled:
            return None
        trace = list(cue["trace"])
        feedback = None
        for attempt in range(1, self.MAX_DRAFTS + 1):
            out = await self.narrator.draft(b, profile, feedback)
            if not out or "text" not in out:
                reason = (out or {}).get("error", "no reply")
                trace.append(step("Narrator", f"draft {attempt}", f"Azure OpenAI gave no usable draft: {reason}.", False))
                break
            trace.append(step("Narrator", f"draft {attempt}", f"Azure OpenAI draft: “{out['text']}”"))
            ok, bad = self.checker.check(out["text"], b)
            if ok:
                trace.append(step("Fact-checker", "approve", "Every number traced to a fact. Version 2 goes on air.", True))
                return {**cue, "version": 2, "source": "model", "text": {**cue["text"], profile.lang: out["text"]},
                        "cited": out["cited"], "trace": trace}
            feedback = bad
            trace.append(step("Fact-checker", "reject", f"Numbers {', '.join(f'{n:g}' for n in bad)} are not in "
                              "the facts. Sent back to the Narrator.", False))
        trace.append(step("Fact-checker", "fallback", "No grounded draft. The template caption stays on air.", False))
        return {**cue, "trace": trace}
