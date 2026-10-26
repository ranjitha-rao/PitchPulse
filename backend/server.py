"""PitchPulse API: replays a synthetic match over a WebSocket as events, match state and overlay cues.

Run: uvicorn server:app --reload   (from the backend folder)
"""

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from pitchpulse.engine import MIN, MatchEngine
from pitchpulse.i18n import LANGS, UI_MODES, voice
from pitchpulse.narrate import ModelNarrator, recap_facts, render_recap
from pitchpulse.personalize import Profile, build_cue, player_card_cue, relevance
from pitchpulse.roster import MATCH_META, TEAMS
from pitchpulse.simulator import HALF_MS, generate_match
from pitchpulse.webvtt import to_webvtt

EVENTS = generate_match(seed=7)
narrator = ModelNarrator()

app = FastAPI(title="PitchPulse")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def full_match_engine() -> MatchEngine:
    e = MatchEngine()
    for ev in EVENTS:
        e.ingest(ev)
    return e


FULL = full_match_engine()


@app.get("/api/meta")
def meta():
    return {
        "match": MATCH_META,
        "teams": {
            t.id: {"id": t.id, "name": t.name, "short": t.short, "formation": t.formation, "color": t.color,
                   "players": [{"id": p.id, "name": p.name, "short": p.short, "number": p.number,
                                "position": p.position, "slot": p.slot} for p in t.players]}
            for t in TEAMS.values()
        },
        "langs": LANGS,
        "modes": UI_MODES,
        "model_captions": narrator.enabled,
        "event_count": len(EVENTS),
    }


@app.get("/api/events")
def events(limit: int = 0):
    """The synthetic event dataset, for download or inspection."""
    return EVENTS[:limit] if limit else EVENTS


@app.get("/api/recap")
async def recap(lang: str = "en"):
    facts = recap_facts(FULL)
    out = render_recap(facts, lang)
    model = await narrator.recap({"facts": facts}, lang)
    return {**out, "model_text": model, "facts": facts}


@app.get("/api/captions.vtt", response_class=PlainTextResponse)
def captions(mode: str = "casual", lang: str = "en", club: str = "", player_id: str = ""):
    """The match's cues for one viewer profile as WebVTT."""
    profile = Profile()
    profile.update(mode=mode, lang=lang, club=club, player=player_id)
    return PlainTextResponse(to_webvtt(FULL.moments, profile), media_type="text/vtt; charset=utf-8",
                             headers={"Content-Disposition": f'inline; filename="pitchpulse-{mode}-{lang}.vtt"'})


@app.get("/api/moments")
def moments():
    return [m.as_dict() for m in FULL.moments]


class Session:
    def __init__(self, ws: WebSocket, profile: Profile, speed: float):
        self.ws = ws
        self.profile = profile
        self.speed = speed
        self.playing = True
        self.seek_to: int | None = None
        self.restart = False
        self.lock = asyncio.Lock()

    async def send(self, msg: dict) -> None:
        async with self.lock:
            await self.ws.send_text(json.dumps(msg, ensure_ascii=False))

    def langs(self) -> list[str]:
        # Template captions are cheap, so every cue carries all languages and a viewer can switch mid-match.
        return list(LANGS)

    async def status(self) -> None:
        p = self.profile
        await self.send({"type": "status", "playing": self.playing, "speed": self.speed,
                         "profile": {"mode": p.mode, "club": p.club, "player": p.player, "lang": p.lang},
                         "model_captions": narrator.enabled})

    async def upgrade(self, cue: dict, moment: dict) -> None:
        """Send version 2 of a cue with a grounded model caption, if the model is configured."""
        lang = self.profile.lang
        out = await narrator.caption(moment, voice(self.profile.mode), lang, self.profile.player)
        if out:
            cue = {**cue, "version": 2, "source": "model",
                   "text": {**cue["text"], lang: out["text"]}, "cited": out["cited"]}
            await self.send({"type": "cue", "cue": cue})


async def reader(s: Session) -> None:
    while True:
        msg = json.loads(await s.ws.receive_text())
        kind = msg.get("type")
        if kind == "profile":
            s.profile.update(**msg)
        elif kind == "speed":
            s.speed = max(0.5, min(60.0, float(msg["value"])))
        elif kind == "pause":
            s.playing = False
        elif kind == "resume":
            s.playing = True
        elif kind == "seek":
            s.seek_to = int(float(msg["minute"]) * MIN)
        elif kind == "restart":
            s.restart = True
        await s.status()


async def player(s: Session) -> None:
    while True:
        engine = MatchEngine()
        s.profile.last_cue_ms = -10 * MIN
        next_card_ms = 10 * MIN
        prev_clock = 0
        last_state_minute = -1
        await s.send({"type": "reset"})
        for ev in EVENTS:
            if s.restart:
                break
            if s.seek_to is not None and s.seek_to < ev["clock_ms"] and s.seek_to < prev_clock:
                # Backward seek: replay from the start, fast-forwarding to the target.
                break
            fast = s.seek_to is not None and ev["clock_ms"] < s.seek_to
            if not fast:
                if s.seek_to is not None:
                    s.seek_to = None
                    await s.send({"type": "state", "state": engine.state(), "timeline": engine.timeline})
                while not s.playing and not s.restart and s.seek_to is None:
                    await asyncio.sleep(0.1)
                wait = (ev["clock_ms"] - prev_clock) / 1000 / s.speed
                await asyncio.sleep(min(wait, 2.5))
            prev_clock = ev["clock_ms"]
            moments = engine.ingest(ev)
            if fast:
                continue
            await s.send({"type": "event", "event": ev})
            minute = ev["clock_ms"] // MIN
            if minute != last_state_minute or ev["type"] == "goal":
                last_state_minute = minute
                await s.send({"type": "state", "state": engine.state(),
                              "point": engine.timeline[-1] if engine.timeline else None})
            ranked = [(relevance(mo, s.profile), mo) for mo in moments]
            for score, mo in sorted((r for r in ranked if r[0] is not None), key=lambda r: -r[0])[:2]:
                cue = build_cue(mo, s.profile, s.langs())
                if mo.type not in ("goal", "card"):
                    s.profile.last_cue_ms = mo.clock_ms
                await s.send({"type": "cue", "cue": cue})
                if narrator.enabled:
                    asyncio.create_task(s.upgrade(cue, mo.as_dict()))
            if s.profile.mode == "player" and s.profile.player and ev["clock_ms"] >= next_card_ms:
                next_card_ms += 15 * MIN
                await s.send({"type": "cue", "cue": player_card_cue(engine, s.profile, s.langs())})
            if ev["type"] == "period_end":
                facts = recap_facts(engine, half=ev["clock_ms"] <= HALF_MS)
                recaps = {lang: render_recap(facts, lang, half=ev["clock_ms"] <= HALF_MS) for lang in LANGS}
                await s.send({"type": "recap", "half": ev["clock_ms"] <= HALF_MS, "recap": recaps,
                              "facts": facts, "timeline": engine.timeline})
        else:
            # Match finished: hold until the viewer restarts or seeks.
            while not s.restart and s.seek_to is None:
                await asyncio.sleep(0.2)
        s.restart = False


@app.websocket("/ws/match")
async def match_socket(ws: WebSocket, mode: str = "casual", club: str = "", player_id: str = "",
                       lang: str = "en", speed: float = 20):
    await ws.accept()
    profile = Profile()
    profile.update(mode=mode, club=club, player=player_id, lang=lang)
    s = Session(ws, profile, speed)
    await s.status()
    tasks = [asyncio.create_task(reader(s)), asyncio.create_task(player(s))]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        for t in done:
            if t.exception() and not isinstance(t.exception(), WebSocketDisconnect):
                raise t.exception()
    except WebSocketDisconnect:
        pass
    finally:
        for t in tasks:
            t.cancel()


DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/")
    def index():
        return FileResponse(DIST / "index.html")
