import { useState } from "react";
import { cueText } from "./Overlays";
import type { Cue, Lang, Meta } from "./types";

type Decision = "approved" | "held";

export function Studio({ meta, cues, lang }: { meta: Meta; cues: Cue[]; lang: Lang }) {
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const cue = cues.find((c) => c.cue_id === selected) ?? cues[0];
  const decide = (id: string, d: Decision) => setDecisions((x) => ({ ...x, [id]: d }));

  return (
    <main className="studio">
      <section className="queue">
        <h3>Cue queue <small>{cues.length} cues · newest first</small></h3>
        <table>
          <thead>
            <tr><th>Min</th><th>Slot</th><th>Template</th><th>Caption</th><th>Pri</th><th>Src</th><th>Producer</th></tr>
          </thead>
          <tbody>
            {cues.map((c) => {
              const { text, dir } = cueText(c, lang);
              const d = decisions[c.cue_id];
              return (
                <tr key={c.cue_id} className={`${cue?.cue_id === c.cue_id ? "sel" : ""} ${d ?? ""}`} onClick={() => setSelected(c.cue_id)}>
                  <td>{c.minute}'</td>
                  <td>{c.slot}</td>
                  <td>
                    <span className="dot" style={{ background: c.team_id ? meta.teams[c.team_id].color : "#64748b" }} />
                    {c.template}
                  </td>
                  <td dir={dir} className="cap">{text}</td>
                  <td>{c.priority}</td>
                  <td>{c.source === "model" ? `AI v${c.version}` : `tpl v${c.version}`}</td>
                  <td className="acts" onClick={(e) => e.stopPropagation()}>
                    <button className={d === "approved" ? "on" : ""} onClick={() => decide(c.cue_id, "approved")}>Approve</button>
                    <button className={d === "held" ? "on hold" : ""} onClick={() => decide(c.cue_id, "held")}>Hold</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
      <section className="why">
        {cue ? (
          <>
            <h3>Why this cue? <small>{cue.template} · {cue.minute}'</small></h3>
            <p className="why-caption" dir={cueText(cue, lang).dir}>{cueText(cue, lang).text}</p>
            <table className="facts">
              <tbody>
                {cue.explain.facts.map((f) => (
                  <tr key={f.id} className={cue.explain.drivers.includes(f.id) ? "driver" : ""}>
                    <td>{f.label ?? f.id}</td>
                    <td>{String(f.value)}{f.unit ? (/^[%/]/.test(f.unit) ? f.unit : ` ${f.unit}`) : ""}</td>
                    <td className="fid">{f.id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="muted">
              Highlighted rows are the drivers: the facts that caused this moment. Every number in the caption is
              checked against this list before it goes to air.
              {cue.explain.storyline && <> Storyline: <b>{cue.explain.storyline}</b>.</>}
            </p>
            <details>
              <summary>Overlay cue JSON (renderer contract)</summary>
              <pre>{JSON.stringify({ ...cue, receivedAt: undefined }, null, 2)}</pre>
            </details>
          </>
        ) : (
          <p className="muted">Cues will appear as soon as the match produces moments.</p>
        )}
      </section>
    </main>
  );
}
