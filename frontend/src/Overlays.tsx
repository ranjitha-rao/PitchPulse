import { useEffect, useState } from "react";
import { playerPositions } from "./Pitch";
import type { Ball } from "./useMatch";
import type { Cue, Lang, MatchState, Meta, Mode } from "./types";

const VIEW_W = 111;
const VIEW_H = 74;

/** Caption in the viewer's language and voice. Model captions (version 2) win over templates. */
export function cueText(cue: Cue, lang: Lang, mode?: Mode): { text: string; dir: "rtl" | "ltr" } {
  const voice = mode === "analyst" ? "analyst" : "casual";
  const sameVoice = !mode || (cue.mode === "analyst" ? "analyst" : "casual") === voice;
  const source = cue.source === "model" && sameVoice ? cue.text : cue.variants?.[voice] ?? cue.text;
  const text = source[lang] ?? cue.text[lang] ?? cue.text.en ?? "";
  return { text, dir: source[lang] || cue.text[lang] ? cue.dir[lang] ?? "ltr" : "ltr" };
}

function useNow(ms = 250) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), ms);
    return () => window.clearInterval(t);
  }, [ms]);
  return now;
}

function clock(ms: number) {
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

interface Props {
  meta: Meta;
  ball: Ball;
  cues: Cue[];
  state: MatchState | null;
  clockMs: number;
  lang: Lang;
  mode: Mode;
}

export function Overlays({ meta, ball, cues, state, clockMs, lang, mode }: Props) {
  const now = useNow();
  const active = cues.filter((c) => now - (c.receivedAt ?? 0) < Math.min(9000, Math.max(5000, c.duration_ms)));
  const bySlot = (slot: Cue["slot"]) => active.find((c) => c.slot === slot);
  const score = state?.score ?? { hfc: 0, nga: 0 };
  const wp = state?.win_prob ?? { home: 0.38, draw: 0.27, away: 0.35 };
  const { hfc, nga } = meta.teams;

  const banner = bySlot("banner");
  const lower = bySlot("lower_third");
  const tag = bySlot("player_tag");
  const bug = bySlot("stat_bug");
  const card = bySlot("player_card");
  const pos = playerPositions(meta, ball);
  const tagPos = tag?.player_id ? pos[tag.player_id] : null;

  return (
    <div className="overlays">
      <div className="score-bug">
        <div className="sb-row">
          <span className="sb-team" style={{ background: hfc.color }}>{hfc.short}</span>
          <span className="sb-score">{score.hfc} – {score.nga}</span>
          <span className="sb-team" style={{ background: nga.color }}>{nga.short}</span>
          <span className="sb-clock">{clock(clockMs)}</span>
        </div>
        <div className="wp-bar" title="Live win probability">
          <span style={{ width: `${wp.home * 100}%`, background: hfc.color }} />
          <span style={{ width: `${wp.draw * 100}%`, background: "#64748b" }} />
          <span style={{ width: `${wp.away * 100}%`, background: nga.color }} />
        </div>
        <div className="wp-labels">
          <span>{Math.round(wp.home * 100)}%</span>
          <span>Win probability</span>
          <span>{Math.round(wp.away * 100)}%</span>
        </div>
      </div>

      {banner && (
        <div key={banner.cue_id} className="ov banner" dir={cueText(banner, lang, mode).dir}
             style={{ borderColor: meta.teams[banner.team_id ?? "hfc"].color }}>
          <div className="ov-kicker" dir="ltr">{String(banner.data.team ?? "")} · {banner.minute}'</div>
          <div className="ov-text">{cueText(banner, lang, mode).text}</div>
          {banner.source === "model" && <span className="ai-badge">AI</span>}
        </div>
      )}

      {bug && (
        <div key={bug.cue_id} className="ov stat-bug" dir={cueText(bug, lang, mode).dir}>
          <div className="ov-kicker" dir="ltr">{bug.template.replace("_", " ")} · {bug.minute}'</div>
          <div className="ov-text">{cueText(bug, lang, mode).text}</div>
          {bug.source === "model" && <span className="ai-badge">AI</span>}
        </div>
      )}

      {tag && tagPos && (
        <div key={tag.cue_id} className="ov player-tag" dir={cueText(tag, lang, mode).dir}
             style={{ left: `${((tagPos[0] + 3) / VIEW_W) * 100}%`, top: `${((tagPos[1] + 3) / VIEW_H) * 100}%`,
                      borderColor: meta.teams[tag.team_id ?? "hfc"].color }}>
          <div className="ov-text">{cueText(tag, lang, mode).text}</div>
          {tag.source === "model" && <span className="ai-badge">AI</span>}
        </div>
      )}

      {card && (
        <div key={card.cue_id} className="ov player-card" dir={cueText(card, lang, mode).dir}>
          <div className="ov-kicker" dir="ltr">Player focus · {card.minute}'</div>
          <div className="pc-name">{card.name}</div>
          <div className="pc-stats">
            <Stat label="Passes" value={`${card.data.passes_complete}/${card.data.passes}`} />
            <Stat label="Line-breakers" value={String(card.data.line_breakers)} />
            <Stat label="Top speed" value={`${card.data.top_speed} km/h`} />
            <Stat label="Rating" value={String(card.data.rating)} />
          </div>
          <div className="ov-text small">{cueText(card, lang, mode).text}</div>
        </div>
      )}

      {lower && (
        <div key={lower.cue_id} className="ov lower-third" dir={cueText(lower, lang, mode).dir}>
          <div className="ov-kicker" dir="ltr">{lower.template.replace("_", " ")} · {lower.minute}'</div>
          <div className="ov-text">{cueText(lower, lang, mode).text}</div>
          {lower.source === "model" && <span className="ai-badge">AI</span>}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="pc-stat">
      <div className="pc-value">{value}</div>
      <div className="pc-label">{label}</div>
    </div>
  );
}
