import { useEffect, useState } from "react";
import { ControlChaos, PressureChart, WinProbChart, XgChart } from "./Charts";
import { Overlays, cueText } from "./Overlays";
import { Pitch } from "./Pitch";
import { Studio } from "./Studio";
import type { Cue, Lang, Meta, Mode, TeamId } from "./types";
import { useMatch } from "./useMatch";

const MODES: { id: Mode; label: string; hint: string }[] = [
  { id: "casual", label: "Casual", hint: "The big moments, in plain words" },
  { id: "analyst", label: "Analyst", hint: "Every pattern, numbers first" },
  { id: "player", label: "Player focus", hint: "Follow one player all match" },
];
const LANGS: { id: Lang; label: string }[] = [
  { id: "en", label: "English" },
  { id: "es", label: "Español" },
  { id: "ar", label: "العربية" },
];
const SPEEDS = [5, 10, 20, 40];

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [view, setView] = useState<"fan" | "studio">("fan");
  const feed = useMatch();
  const { profile, send } = feed;

  useEffect(() => {
    fetch("/api/meta").then((r) => r.json()).then(setMeta);
  }, []);

  if (!meta) return <div className="loading">Loading PitchPulse…</div>;

  const setProfile = (patch: Partial<typeof profile>) => send({ type: "profile", ...patch });
  const ft = feed.recaps.find((r) => !r.half);
  const ht = feed.recaps.find((r) => r.half);
  const shownRecap = ft ?? ht;
  const rtl = profile.lang === "ar";

  return (
    <div className="app">
      <header>
        <div className="brand">
          <span className="logo">◉</span> PitchPulse
          <span className="sub">Synthetic Match Insights Engine</span>
        </div>
        <nav>
          <button className={view === "fan" ? "on" : ""} onClick={() => setView("fan")}>Fan view</button>
          <button className={view === "studio" ? "on" : ""} onClick={() => setView("studio")}>Studio view</button>
        </nav>
        <div className={`conn ${feed.connected ? "ok" : ""}`}>
          {feed.connected ? "Live" : "Connecting…"}
          {feed.modelCaptions ? " · AI captions on" : " · template captions"}
        </div>
      </header>

      <section className="controls">
        <div className="seg">
          {MODES.map((m) => (
            <button key={m.id} title={m.hint} className={profile.mode === m.id ? "on" : ""}
                    onClick={() => setProfile({ mode: m.id, player: m.id === "player" ? profile.player ?? "hfc_08" : profile.player })}>
              {m.label}
            </button>
          ))}
        </div>
        <label>
          Club
          <select value={profile.club ?? ""} onChange={(e) => setProfile({ club: (e.target.value || null) as TeamId | null })}>
            <option value="">No favourite</option>
            {Object.values(meta.teams).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </label>
        <label>
          Player
          <select value={profile.player ?? ""} onChange={(e) => setProfile({ player: e.target.value || null })}>
            <option value="">None</option>
            {Object.values(meta.teams).map((t) => (
              <optgroup key={t.id} label={t.name}>
                {t.players.map((p) => <option key={p.id} value={p.id}>{p.number} {p.name}</option>)}
              </optgroup>
            ))}
          </select>
        </label>
        <div className="seg">
          {LANGS.map((l) => (
            <button key={l.id} className={profile.lang === l.id ? "on" : ""} onClick={() => setProfile({ lang: l.id })}>
              {l.label}
            </button>
          ))}
        </div>
        <div className="seg">
          {SPEEDS.map((s) => (
            <button key={s} className={feed.speed === s ? "on" : ""} onClick={() => send({ type: "speed", value: s })}>{s}x</button>
          ))}
        </div>
        <div className="seg">
          <button onClick={() => send({ type: feed.playing ? "pause" : "resume" })}>{feed.playing ? "Pause" : "Play"}</button>
          <button onClick={() => send({ type: "restart" })}>Restart</button>
          {[30, 60, 75, 87].map((m) => (
            <button key={m} onClick={() => send({ type: "seek", minute: m })}>{m}'</button>
          ))}
        </div>
      </section>

      {view === "fan" ? (
        <main className="fan">
          <div className="stage">
            <Pitch meta={meta} ball={feed.ball} focus={profile.player} highlightTeam={profile.club} />
            <Overlays meta={meta} ball={feed.ball} cues={feed.cues} state={feed.state} clockMs={feed.clockMs} lang={profile.lang} mode={profile.mode} />
          </div>
          <aside className="side">
            {profile.mode === "analyst" ? (
              <AnalystPanel meta={meta} feed={feed} />
            ) : (
              <FeedPanel meta={meta} cues={feed.cues} lang={profile.lang} mode={profile.mode} player={profile.player} />
            )}
          </aside>
        </main>
      ) : (
        <Studio meta={meta} cues={feed.cues} lang={profile.lang} />
      )}

      {shownRecap && (
        <section className="recap" dir={rtl ? "rtl" : "ltr"}>
          <h2>{shownRecap.recap[profile.lang].title}</h2>
          {shownRecap.recap[profile.lang].lines.map((l, i) => <p key={i}>{l}</p>)}
        </section>
      )}
    </div>
  );
}

function AnalystPanel({ meta, feed }: { meta: Meta; feed: ReturnType<typeof useMatch> }) {
  const r = feed.state?.rolling;
  return (
    <div className="analyst">
      <h3>Control vs Chaos <small>last 12 minutes</small></h3>
      <ControlChaos meta={meta} timeline={feed.timeline} />
      {r && (
        <div className="kpis">
          <Kpi label={`${meta.teams.hfc.short} possession (10')`} value={`${r.possession_home}%`} />
          <Kpi label="Field tilt" value={`${r.field_tilt_home}% ${meta.teams.hfc.short}`} />
          <Kpi label="Tempo" value={`${r.tempo}/min`} />
          <Kpi label="Chaos" value={`${r.chaos}`} />
        </div>
      )}
      <h3>Win probability</h3>
      <WinProbChart meta={meta} timeline={feed.timeline} />
      <h3>Pressure index <small>pressures per 10 opposition passes, 10' window</small></h3>
      <PressureChart meta={meta} timeline={feed.timeline} />
      <h3>Expected goals</h3>
      <XgChart meta={meta} timeline={feed.timeline} />
      <Legend meta={meta} />
    </div>
  );
}

function Legend({ meta }: { meta: Meta }) {
  return (
    <div className="legend">
      {Object.values(meta.teams).map((t) => (
        <span key={t.id}><i style={{ background: t.color }} />{t.name}</span>
      ))}
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="kpi">
      <div className="kpi-v">{value}</div>
      <div className="kpi-l">{label}</div>
    </div>
  );
}

function FeedPanel({ meta, cues, lang, mode, player }: { meta: Meta; cues: Cue[]; lang: Lang; mode: Mode; player: string | null }) {
  const focus = player ? Object.values(meta.teams).flatMap((t) => t.players).find((p) => p.id === player) : null;
  return (
    <div className="feedpanel">
      <h3>{mode === "player" && focus ? `Following ${focus.name}` : "Live story"}</h3>
      {cues.length === 0 && <p className="muted">Moments will appear here as the match unfolds.</p>}
      <ul className="feed">
        {cues.slice(0, 30).map((c) => {
          const { text, dir } = cueText(c, lang, mode);
          return (
            <li key={c.cue_id} dir={dir} className={`t-${c.template}`}>
              <span className="min" style={{ background: c.team_id ? meta.teams[c.team_id].color : "#475569" }}>{c.minute}'</span>
              <span>{text}</span>
              {c.source === "model" && <span className="ai-badge inline">AI</span>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
