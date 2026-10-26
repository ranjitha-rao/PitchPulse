import type { Ball } from "./useMatch";
import type { Meta, TeamId } from "./types";

const L = 105;
const W = 68;

function attackFrame(team: TeamId, x: number, y: number): [number, number] {
  return team === "hfc" ? [x, y] : [L - x, W - y];
}

export function playerPositions(meta: Meta, ball: Ball): Record<string, [number, number]> {
  const out: Record<string, [number, number]> = {};
  for (const team of Object.values(meta.teams)) {
    const [bax] = attackFrame(team.id, ball.xy[0], ball.xy[1]);
    const shift = (bax - 50) * 0.5;
    // Defending players sit a little goal-side so the two shapes do not overlap.
    const defending = ball.team !== null && ball.team !== team.id;
    for (const p of team.players) {
      const ax = p.position === "GK" ? p.slot[0] : Math.min(100, Math.max(8, p.slot[0] + shift - (defending ? 3 : 0)));
      const ay = p.position === "GK" ? p.slot[1] : p.slot[1] + (defending ? 2.5 : 0);
      out[p.id] = attackFrame(team.id, ax, ay);
    }
  }
  if (ball.carrier && out[ball.carrier]) out[ball.carrier] = [ball.xy[0] - 0.9, ball.xy[1] - 0.9];
  return out;
}

interface Props {
  meta: Meta;
  ball: Ball;
  focus: string | null;
  highlightTeam: TeamId | null;
}

export function Pitch({ meta, ball, focus, highlightTeam }: Props) {
  const pos = playerPositions(meta, ball);
  const line = { stroke: "rgba(255,255,255,0.55)", strokeWidth: 0.3, fill: "none" };
  return (
    <svg className="pitch" viewBox={`-3 -3 ${L + 6} ${W + 6}`} role="img" aria-label="Animated match view">
      <defs>
        <pattern id="stripes" width="10.5" height="68" patternUnits="userSpaceOnUse">
          <rect width="10.5" height="68" fill="#1f7a3f" />
          <rect width="5.25" height="68" fill="#22854a" />
        </pattern>
      </defs>
      <rect x={-3} y={-3} width={L + 6} height={W + 6} fill="#1b6e38" />
      <rect x={0} y={0} width={L} height={W} fill="url(#stripes)" />
      <rect x={0} y={0} width={L} height={W} {...line} />
      <line x1={L / 2} y1={0} x2={L / 2} y2={W} {...line} />
      <circle cx={L / 2} cy={W / 2} r={9.15} {...line} />
      <circle cx={L / 2} cy={W / 2} r={0.4} fill="rgba(255,255,255,0.7)" />
      <rect x={0} y={13.84} width={16.5} height={40.32} {...line} />
      <rect x={L - 16.5} y={13.84} width={16.5} height={40.32} {...line} />
      <rect x={0} y={24.84} width={5.5} height={18.32} {...line} />
      <rect x={L - 5.5} y={24.84} width={5.5} height={18.32} {...line} />
      <rect x={-1.5} y={30.34} width={1.5} height={7.32} {...line} />
      <rect x={L} y={30.34} width={1.5} height={7.32} {...line} />
      {Object.values(meta.teams).map((team) =>
        team.players.map((p) => {
          const [x, y] = pos[p.id];
          const isFocus = focus === p.id;
          const dim = highlightTeam && highlightTeam !== team.id;
          return (
            <g key={p.id} className="player" style={{ transform: `translate(${x}px, ${y}px)`, opacity: dim ? 0.55 : 1 }}>
              {isFocus && <circle r={3} fill="none" stroke="#facc15" strokeWidth={0.5} className="focus-ring" />}
              <circle r={1.7} fill={team.color} stroke={isFocus ? "#facc15" : "white"} strokeWidth={isFocus ? 0.5 : 0.3} />
              <text y={0.62} textAnchor="middle" fontSize={1.6} fontWeight={700} fill="white">
                {p.number}
              </text>
            </g>
          );
        }),
      )}
      <g className="ball" style={{ transform: `translate(${ball.xy[0]}px, ${ball.xy[1]}px)` }}>
        <circle r={0.9} fill="white" stroke="#111" strokeWidth={0.2} />
      </g>
    </svg>
  );
}
