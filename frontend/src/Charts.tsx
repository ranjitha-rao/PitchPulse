import type { Meta, TimelinePoint } from "./types";

interface Series {
  label: string;
  color: string;
  dashed?: boolean;
  values: [number, number][];
}

function LineChart({ series, yMax, height = 120, unit = "", markers = [] }: {
  series: Series[];
  yMax: number;
  height?: number;
  unit?: string;
  markers?: { minute: number; color: string }[];
}) {
  const W = 320;
  const H = height;
  const pad = { l: 28, r: 8, t: 8, b: 18 };
  const x = (m: number) => pad.l + (m / 93) * (W - pad.l - pad.r);
  const y = (v: number) => H - pad.b - (v / yMax) * (H - pad.t - pad.b);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart">
      {[0, 0.5, 1].map((f) => (
        <g key={f}>
          <line x1={pad.l} x2={W - pad.r} y1={y(f * yMax)} y2={y(f * yMax)} className="grid" />
          <text x={pad.l - 4} y={y(f * yMax) + 3} textAnchor="end" className="tick">
            {Math.round(f * yMax)}{unit}
          </text>
        </g>
      ))}
      {[0, 45, 90].map((m) => (
        <text key={m} x={x(m)} y={H - 4} textAnchor="middle" className="tick">{m}'</text>
      ))}
      {markers.map((mk, i) => (
        <line key={i} x1={x(mk.minute)} x2={x(mk.minute)} y1={pad.t} y2={H - pad.b} stroke={mk.color} strokeDasharray="2 2" opacity={0.7} />
      ))}
      {series.map((s) => (
        <polyline key={s.label} fill="none" stroke={s.color} strokeWidth={2} strokeDasharray={s.dashed ? "4 3" : undefined}
                  points={s.values.map(([m, v]) => `${x(m)},${y(Math.min(v, yMax))}`).join(" ")} />
      ))}
    </svg>
  );
}

function goalMarkers(meta: Meta, tl: TimelinePoint[]) {
  const out: { minute: number; color: string }[] = [];
  for (let i = 1; i < tl.length; i++) {
    for (const t of ["hfc", "nga"] as const) {
      if (tl[i].score[t] > tl[i - 1].score[t]) out.push({ minute: tl[i].minute, color: meta.teams[t].color });
    }
  }
  return out;
}

export function WinProbChart({ meta, timeline }: { meta: Meta; timeline: TimelinePoint[] }) {
  return (
    <LineChart
      yMax={100}
      unit="%"
      markers={goalMarkers(meta, timeline)}
      series={[
        { label: "home", color: meta.teams.hfc.color, values: timeline.map((p) => [p.minute, 100 * p.win_prob.home]) },
        { label: "draw", color: "#94a3b8", dashed: true, values: timeline.map((p) => [p.minute, 100 * p.win_prob.draw]) },
        { label: "away", color: meta.teams.nga.color, values: timeline.map((p) => [p.minute, 100 * p.win_prob.away]) },
      ]}
    />
  );
}

export function PressureChart({ meta, timeline }: { meta: Meta; timeline: TimelinePoint[] }) {
  const max = Math.max(6, ...timeline.flatMap((p) => [p.pressure_index.hfc, p.pressure_index.nga]));
  return (
    <LineChart
      yMax={Math.ceil(max)}
      series={[
        { label: "hfc", color: meta.teams.hfc.color, values: timeline.map((p) => [p.minute, p.pressure_index.hfc]) },
        { label: "nga", color: meta.teams.nga.color, values: timeline.map((p) => [p.minute, p.pressure_index.nga]) },
      ]}
    />
  );
}

export function XgChart({ meta, timeline }: { meta: Meta; timeline: TimelinePoint[] }) {
  const max = Math.max(1, ...timeline.flatMap((p) => [p.xg.hfc, p.xg.nga]));
  return (
    <LineChart
      yMax={Math.ceil(max)}
      markers={goalMarkers(meta, timeline)}
      series={[
        { label: "hfc", color: meta.teams.hfc.color, values: timeline.map((p) => [p.minute, p.xg.hfc]) },
        { label: "nga", color: meta.teams.nga.color, values: timeline.map((p) => [p.minute, p.xg.nga]) },
      ]}
    />
  );
}

export function ControlChaos({ meta, timeline }: { meta: Meta; timeline: TimelinePoint[] }) {
  const W = 320;
  const H = 210;
  const pad = 22;
  const x = (d: number) => W / 2 + (Math.max(-60, Math.min(60, d)) / 60) * (W / 2 - pad);
  const y = (c: number) => H - pad - (Math.min(100, c) / 100) * (H - 2 * pad);
  const trail = timeline.slice(-12);
  const cur = trail[trail.length - 1];
  const side = cur && cur.control_diff >= 0 ? meta.teams.hfc : meta.teams.nga;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart">
      <rect x={pad} y={pad} width={W / 2 - pad} height={H - 2 * pad} fill={meta.teams.nga.color} opacity={0.07} />
      <rect x={W / 2} y={pad} width={W / 2 - pad} height={H - 2 * pad} fill={meta.teams.hfc.color} opacity={0.07} />
      <line x1={W / 2} x2={W / 2} y1={pad} y2={H - pad} className="grid" />
      <line x1={pad} x2={W - pad} y1={y(50)} y2={y(50)} className="grid" />
      <text x={pad + 4} y={H - 6} className="tick">◀ {meta.teams.nga.short} in control</text>
      <text x={W - pad - 4} y={H - 6} textAnchor="end" className="tick">{meta.teams.hfc.short} in control ▶</text>
      <text x={W / 2} y={14} textAnchor="middle" className="tick">CHAOS</text>
      <text x={W / 2} y={y(0) - 4} textAnchor="middle" className="tick">calm</text>
      {trail.length > 1 && (
        <polyline fill="none" stroke="#94a3b8" strokeWidth={1.5} opacity={0.7}
                  points={trail.map((p) => `${x(p.control_diff)},${y(p.chaos)}`).join(" ")} />
      )}
      {trail.map((p, i) => (
        <circle key={p.minute} cx={x(p.control_diff)} cy={y(p.chaos)} r={2} fill="#94a3b8" opacity={(i + 1) / trail.length} />
      ))}
      {cur && (
        <g>
          <circle cx={x(cur.control_diff)} cy={y(cur.chaos)} r={7} fill={side.color} stroke="white" strokeWidth={2} />
          <text x={x(cur.control_diff)} y={y(cur.chaos) - 11} textAnchor="middle" className="tick strong">
            {Math.round(cur.minute)}'
          </text>
        </g>
      )}
    </svg>
  );
}
