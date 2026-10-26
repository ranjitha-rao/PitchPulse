"""Export personalized cues as WebVTT, so any standard HTML5 or streaming player can show them."""

from .engine import Moment
from .i18n import voice
from .narrate import render
from .personalize import SLOTS, Profile, relevance


def timestamp(ms: int) -> str:
    h, rem = divmod(int(ms), 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms_ = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms_:03d}"


def to_webvtt(moments: list[Moment], profile: Profile) -> str:
    """Cues for one viewer profile, timed on the match clock (00:00:00.000 = kickoff)."""
    lines = ["WEBVTT", "", "NOTE PitchPulse synthetic match captions. Times are match-clock time from kickoff.", ""]
    profile.last_cue_ms = -10 * 60_000
    v = voice(profile.mode)
    for mo in moments:
        if relevance(mo, profile) is None:
            continue
        if mo.type not in ("goal", "card"):
            profile.last_cue_ms = mo.clock_ms
        start = mo.clock_ms
        end = start + SLOTS[mo.type][1]
        text = render(mo.type, mo.facts, v, profile.lang).replace("-->", "->")
        lines += [f"{mo.id}", f"{timestamp(start)} --> {timestamp(end)}", text, ""]
    return "\n".join(lines)
