import { useCallback, useEffect, useRef, useState } from "react";
import type { Cue, Lang, MatchEvent, MatchState, Profile, Recap, TeamId, TimelinePoint } from "./types";

export interface Ball {
  xy: [number, number];
  team: TeamId | null;
  carrier: string | null;
}

export interface MatchFeed {
  connected: boolean;
  playing: boolean;
  speed: number;
  profile: Profile;
  clockMs: number;
  ball: Ball;
  state: MatchState | null;
  timeline: TimelinePoint[];
  cues: Cue[];
  recaps: { half: boolean; recap: Record<Lang, Recap> }[];
  lastEvent: MatchEvent | null;
  modelCaptions: boolean;
  send: (msg: Record<string, unknown>) => void;
}

const DEFAULT_PROFILE: Profile = { mode: "casual", club: null, player: null, lang: "en" };

export function useMatch(): MatchFeed {
  const ws = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(20);
  const [profile, setProfile] = useState<Profile>(DEFAULT_PROFILE);
  const [clockMs, setClockMs] = useState(0);
  const [ball, setBall] = useState<Ball>({ xy: [52.5, 34], team: "hfc", carrier: "hfc_09" });
  const [state, setState] = useState<MatchState | null>(null);
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]);
  const [cues, setCues] = useState<Cue[]>([]);
  const [recaps, setRecaps] = useState<MatchFeed["recaps"]>([]);
  const [lastEvent, setLastEvent] = useState<MatchEvent | null>(null);
  const [modelCaptions, setModelCaptions] = useState(false);

  useEffect(() => {
    let closed = false;
    let retry: number | undefined;
    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      const sock = new WebSocket(`${proto}://${location.host}/ws/match?speed=20`);
      ws.current = sock;
      sock.onopen = () => setConnected(true);
      sock.onclose = () => {
        setConnected(false);
        if (!closed) retry = window.setTimeout(connect, 1500);
      };
      sock.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        switch (msg.type) {
          case "status":
            setPlaying(msg.playing);
            setSpeed(msg.speed);
            setProfile(msg.profile);
            setModelCaptions(msg.model_captions);
            break;
          case "reset":
            setCues([]);
            setTimeline([]);
            setRecaps([]);
            setState(null);
            setClockMs(0);
            break;
          case "event": {
            const ev: MatchEvent = msg.event;
            setClockMs(ev.clock_ms);
            setLastEvent(ev);
            const xy = ev.end_xy ?? ev.start_xy;
            if (xy && ev.team_id) {
              const carrier =
                ev.type === "pass" ? (ev.outcome === "complete" ? ev.receiver_id ?? null : null) : ev.player_id;
              const team = ev.type === "pressure" || ev.type === "tackle" || ev.type === "interception" || ev.type === "foul"
                ? null
                : ev.team_id;
              setBall((b) => ({ xy, team: team ?? b.team, carrier: carrier ?? (team ? null : b.carrier) }));
            }
            break;
          }
          case "state":
            setState(msg.state);
            if (msg.timeline) setTimeline(msg.timeline);
            else if (msg.point)
              setTimeline((t) => (t.length && t[t.length - 1].minute === msg.point.minute ? t : [...t, msg.point]));
            break;
          case "cue": {
            const cue: Cue = { ...msg.cue, receivedAt: Date.now() };
            setCues((cs) => {
              const i = cs.findIndex((c) => c.cue_id === cue.cue_id);
              if (i >= 0) {
                const next = cs.slice();
                next[i] = { ...cue, receivedAt: cs[i].receivedAt };
                return next;
              }
              return [cue, ...cs].slice(0, 200);
            });
            break;
          }
          case "recap":
            setRecaps((r) => [...r.filter((x) => x.half !== msg.half), { half: msg.half, recap: msg.recap }]);
            if (msg.timeline) setTimeline(msg.timeline);
            break;
        }
      };
    };
    connect();
    return () => {
      closed = true;
      window.clearTimeout(retry);
      ws.current?.close();
    };
  }, []);

  const send = useCallback((msg: Record<string, unknown>) => {
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify(msg));
  }, []);

  return { connected, playing, speed, profile, clockMs, ball, state, timeline, cues, recaps, lastEvent, modelCaptions, send };
}
