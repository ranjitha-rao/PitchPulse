# PitchPulse: Synthetic Match Insights Engine

[![CI](https://github.com/ranjitha-rao/PitchPulse/actions/workflows/ci.yml/badge.svg)](https://github.com/ranjitha-rao/PitchPulse/actions/workflows/ci.yml)

PitchPulse turns a stream of synthetic football events into explained, timed, personalized match intelligence for studio and streaming use.

**Numbers come from code; words come from the model.** Every stat is computed deterministically. Captions are written from a fact pack, and a validator checks every number in a caption against those facts before it reaches the screen.

The match is fictional: Harbourside FC vs Northgate Albion. No real Premier League data or names are used.

## The five stages

| Stage | What PitchPulse does | Where |
| --- | --- | --- |
| Ingest | A seeded simulator emits passes, carries, shots, tackles, interceptions, pressure events, possession changes, fouls, cards and match metadata. The server replays them on a match clock at 5x to 40x. | `backend/pitchpulse/simulator.py`, `backend/server.py` |
| Interpret | Pass distance, accuracy and difficulty (0 to 100), ball and shot speed, xG, sprints, a pressure index, field tilt, tempo, a **Control vs Chaos** index and live win probability | `backend/pitchpulse/metrics.py`, `engine.py` |
| Explain | Moments (goals, big chances, line-breaking passes, sprint records, pressure surges and fades, control swings, rhythm shifts, milestones, cards) carry a fact pack with **drivers**. Storylines such as "the press fades" and "the comeback" persist across the match. | `engine.py`, `narrate.py` |
| Render | Every insight leaves as an **overlay cue**: timed JSON with slot, priority, template data, text per language and the facts behind it. The React app draws the cues over an animated 2D pitch. | `personalize.py`, `frontend/src` |
| Personalize | Casual, Analyst and Player focus modes; favourite club; any player to follow; English, Spanish and Arabic (right-to-left). Viewers can switch mode or language mid-match. | `personalize.py`, `i18n.py` |

There's also a **Studio view**, a producer console. A producer can approve or hold each cue, see the "why" (its facts, with drivers highlighted), follow the agent trace and inspect the raw cue JSON.

## The agent newsroom

Between the engine and the screen, four agents work as a newsroom (`backend/pitchpulse/agents.py`):

| Agent | Job | How |
| --- | --- | --- |
| Analyst | Reads each moment and writes a brief: what happened, what drove it, which story it belongs to | Calls the engine's tools (match state, rolling metrics) |
| Producer | Decides, per viewer, what goes on air, in which overlay slot, at what priority | Ranks briefs by the viewer's mode, club and player, and keeps each mode's rate limit |
| Narrator | Writes the caption from the brief's fact pack | Templates instantly (version 1); Azure OpenAI in the viewer's voice and language (version 2) |
| Fact-checker | Checks every number in a caption against the fact pack | Approves, or rejects and sends the untraced numbers back to the Narrator for a rewrite (up to 2 drafts); otherwise the template stays on air |

The Narrator and Fact-checker form a generate-and-critique loop. Every step is recorded on the cue as `trace`, and the Studio view shows it next to the facts, so a producer can see why each caption was written and who checked it.

```
engine moments ──► Analyst ──► Producer ──► Narrator ──► Fact-checker ──► on air
                   (brief)     (book slot)    ▲   (draft)      │
                                              └──── reject + feedback
```

Half-time and full-time **recaps** are built from the storylines, in all three languages.

## Run it locally

You need Python 3.11+ and Node 20+. No Azure account is required.

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -q                     # unit + functional tests
uvicorn server:app --port 8000

# frontend (second terminal)
cd frontend
npm install
npm run dev                   # open http://localhost:5173
```

To serve everything from one port, run `npm run build` in `frontend`, then open http://localhost:8000.

### Optional: AI captions with Azure OpenAI

Copy `.env.example`, fill in your Azure OpenAI endpoint, key and deployment, and export the variables before starting uvicorn. With these set, each cue is sent twice:

1. **Version 1**, a template caption, arrives instantly.
2. **Version 2**, the model's caption in the viewer's voice and language, follows shortly after.

Version 2 is only sent if every number in it is backed by the fact pack. Otherwise the template caption stays on screen. Model captions show an **AI** badge.

## Tests

| Suite | What it covers | Run |
| --- | --- | --- |
| Unit (`backend/tests/unit`) | Metrics, simulator, engine story and totals, caption grounding validator, personalization rules, translation coverage, the agent newsroom (briefs, booking, the reject-and-rewrite loop) | `pytest tests/unit` |
| Functional (`backend/tests/functional`) | REST API, WebSocket replay (seek, pause, speed, profile changes, recap), and AI captions with a fake model: grounded ones ship as version 2, invented numbers are rejected | `pytest tests/functional` |
| Browser (`backend/tests/e2e`) | Playwright against the built app: fan view, Analyst in Arabic (right-to-left), Player focus, full-time recap, Studio approve, "why" and agent trace | `npm run build` in `frontend`, then `pip install -r requirements-dev.txt`, `playwright install chromium`, `pytest -m e2e` |

GitHub Actions runs all three suites on every push and pull request.

## Demo script (3 minutes)

1. Start at **60'** in Casual. Northgate lead 2-0 and Harbourside's win probability is about 1%.
2. Switch to **Analyst**. The Control vs Chaos dot crosses into Harbourside's half as Northgate's press fades (see the pressure chart).
3. At 64', Okafor's line-breaking pass (difficulty 90/100, 6 opponents bypassed) sets up Haddad.
4. Switch to **Player focus** on Okafor, then switch the language to **Arabic**, then **Spanish**.
5. Jump to **87'**. The winner moves win probability from 2% to 99%, and the full-time recap appears.
6. Open **Studio view**, approve a cue and walk through its "why" and the agent trace.

## Deploy to Azure

The `Dockerfile` builds one container with the API and the web app.

```bash
az login
az containerapp up --name pitchpulse --resource-group pitchpulse-rg --location westeurope \
  --source . --ingress external --target-port 8000 \
  --env-vars AZURE_OPENAI_ENDPOINT=... AZURE_OPENAI_API_KEY=... AZURE_OPENAI_DEPLOYMENT=...
```

The production architecture in the design doc swaps the local stand-ins for managed Azure services:

| Local stand-in | Production service |
| --- | --- |
| In-process replay | Azure Event Hubs (`match-events`, `match-tracking`) |
| WebSocket in FastAPI | Azure Web PubSub, one group per match and mode |
| In-memory state | Azure Cosmos DB (match state, moments, fan profiles) |

Azure OpenAI is used directly in both setups, with Azure AI Content Safety screening captions in production.

## Synthetic data

`python -m pitchpulse.export --seeds 7 11 23 --out ../data` writes matches as JSON Lines. `data/match_seed7.jsonl` is the demo match.

The simulator models four things:

- player attributes (pace, passing, finishing, pressing)
- a possession-chain model over the pitch
- pressure from each team's pressing intensity, which fades for Northgate after the hour
- fatigue

**Story seeds** script the goals and the card so there is always a story to explain. Everything between them is sampled from a seeded RNG.

## Standards and responsible AI

How PitchPulse lines up with the standards and rules that apply to broadcast graphics, football data and AI-generated content.

| Area | Standard or rule | What PitchPulse does |
| --- | --- | --- |
| Timing | SMPTE ST 12 timecode; SCTE-35/104 insertion markers | Every cue is timed on the match clock (`clock_in_ms`, `duration_ms`), so a playout system can map it to timecode or trigger it from a marker |
| Timed text | W3C WebVTT (also TTML/IMSC, CEA-608/708) | `GET /api/captions.vtt?mode=&lang=&club=&player_id=` exports a viewer's cues as WebVTT for any HTML5 or streaming player. There's also a download button in Studio view. |
| Football data | No universal event standard (vendor formats; open tools such as kloppy and SPADL); FIFA EPTS for tracking quality; IFAB Laws of the Game for event definitions | Fully synthetic data with fictional clubs and players. The event schema follows common vendor fields (type, team, player, x/y in metres, outcome, qualifiers) so it can be mapped onto real feeds. |
| AI transparency | EU AI Act transparency obligations for AI-generated content | Model-written captions carry `source: "model"` and an **AI** badge on screen; template captions are labelled `template` |
| Responsible AI | Microsoft Responsible AI Standard; Azure AI Content Safety | The model only explains facts computed in code, and a validator rejects any caption whose numbers can't be traced to a fact. Content Safety screening is part of the production design. |
| Privacy | GDPR / UK GDPR | No personal data is stored. A fan profile (mode, club, player, language) is held in memory for the live connection only and is never saved. |
| Gambling | Gambling advertising rules (e.g. UK) | Win probability is shown as match context only, with no odds, prices or betting prompts |
| Accessibility and language | WCAG 2.2; Unicode bidirectional text (UAX #9); BCP 47 language tags | Arabic renders right to left, language codes are BCP 47 (`en`, `es`, `ar`), and captions are also available as WebVTT |

These references are a starting point. Check the current text of each standard before relying on it.

## Known limits

- Player dots are placed from formation slots shifted toward the ball. They are not full tracking data.
- Auto-eventing from video is not built.
- The win probability model is a simple Poisson model on score, time left and recent xG share. It is not calibrated on real matches.

## Layout

```
backend/   simulator, engine, narrative, personalization, FastAPI server, tests
frontend/  React + TypeScript app (Vite)
data/      exported synthetic match
```
