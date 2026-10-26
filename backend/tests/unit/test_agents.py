import asyncio

from pitchpulse.agents import AGENTS, Analyst, Newsroom, Producer
from pitchpulse.engine import MIN
from pitchpulse.narrate import ModelNarrator
from pitchpulse.personalize import Profile

from ..conftest import first
from .test_personalize import mo


class ScriptedModel(ModelNarrator):
    """A model that replies with the next scripted draft and records the prompts it saw."""

    def __init__(self, *replies):
        super().__init__()
        self.enabled = True
        self.replies = list(replies)
        self.systems = []

    async def _chat(self, system, user):
        self.systems.append(system)
        return self.replies.pop(0) if self.replies else None


def run(coro):
    return asyncio.run(coro)


def test_four_agents_are_described():
    assert [a["name"] for a in AGENTS] == ["Analyst", "Producer", "Narrator", "Fact-checker"]


def test_analyst_brief_names_drivers_and_storyline(moments, engine):
    goal = next(m for m in moments if m.type == "goal" and m.storyline)
    b = Analyst().brief(goal, engine)
    assert f"at {goal.minute}'" in b.angle and goal.storyline in b.angle
    assert b.context["score"] == engine.score
    assert b.trace[0]["agent"] == "Analyst" and "match_state" in b.trace[0]["detail"]


def test_producer_books_best_first_and_keeps_the_rate_limit(engine):
    a = Analyst()
    p = Profile(mode="casual")
    low = mo("line_breaker", importance=50, clock=30 * MIN)
    high = mo("big_chance", importance=70, clock=30 * MIN)
    picked = Producer().select([a.brief(low, engine), a.brief(high, engine)], p)
    # Both are relevant on their own, but booking the first uses up the casual gap.
    assert [b.moment.type for b in picked] == ["big_chance"]
    assert p.last_cue_ms == 30 * MIN
    assert picked[0].trace[-1]["agent"] == "Producer"


def test_producer_always_books_goals(engine):
    p = Profile(mode="casual", last_cue_ms=30 * MIN)
    picked = Producer().select([Analyst().brief(mo("goal", importance=90, clock=31 * MIN), engine)], p)
    assert len(picked) == 1 and p.last_cue_ms == 30 * MIN


def test_on_air_cue_carries_the_full_trace(moments, engine):
    cue, brief = Newsroom(ModelNarrator()).on_air([first(moments, "goal")], engine, Profile(), ["en"])[0]
    assert [s["agent"] for s in cue["trace"]] == ["Analyst", "Producer", "Narrator", "Fact-checker"]
    assert cue["trace"][-1]["ok"] is True
    assert cue["version"] == 1 and brief.moment.type == "goal"


def test_rejected_draft_goes_back_to_the_narrator_with_feedback(moments, engine):
    model = ScriptedModel({"text": "A 999 km/h strike!"}, {"text": "What a strike!", "cited": []})
    room = Newsroom(model)
    cue, brief = room.on_air([first(moments, "goal")], engine, Profile(), ["en"])[0]
    v2 = run(room.rewrite(cue, brief, Profile()))
    assert v2["version"] == 2 and v2["source"] == "model" and v2["text"]["en"] == "What a strike!"
    actions = [(s["agent"], s["action"]) for s in v2["trace"][4:]]
    assert actions == [("Narrator", "draft 1"), ("Fact-checker", "reject"),
                       ("Narrator", "draft 2"), ("Fact-checker", "approve")]
    assert "999" not in model.systems[0] and "999" in model.systems[1]


def test_template_stays_when_every_draft_is_rejected(moments, engine):
    room = Newsroom(ScriptedModel({"text": "999!"}, {"text": "888!"}))
    cue, brief = room.on_air([first(moments, "goal")], engine, Profile(), ["en"])[0]
    out = run(room.rewrite(cue, brief, Profile()))
    assert out["version"] == 1 and out["source"] == "template" and out["text"] == cue["text"]
    assert out["trace"][-1]["action"] == "fallback"


def test_no_rewrite_without_a_model(moments, engine):
    room = Newsroom(ModelNarrator())
    cue, brief = room.on_air([first(moments, "goal")], engine, Profile(), ["en"])[0]
    assert run(room.rewrite(cue, brief, Profile())) is None
