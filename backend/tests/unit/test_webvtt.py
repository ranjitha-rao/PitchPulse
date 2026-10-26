import re

from pitchpulse.personalize import Profile
from pitchpulse.webvtt import timestamp, to_webvtt

CUE_TIME = re.compile(r"^(\d\d:\d\d:\d\d\.\d{3}) --> (\d\d:\d\d:\d\d\.\d{3})$")


def test_timestamp_format():
    assert timestamp(0) == "00:00:00.000"
    assert timestamp(5_400_123) == "01:30:00.123"
    assert timestamp(61_005) == "00:01:01.005"


def parse(vtt):
    blocks = [b.split("\n") for b in vtt.strip().split("\n\n")]
    assert blocks[0] == ["WEBVTT"] and blocks[1][0].startswith("NOTE")
    return [(b[0], *CUE_TIME.match(b[1]).groups(), "\n".join(b[2:])) for b in blocks[2:]]


def test_webvtt_is_well_formed_and_ordered(moments):
    cues = parse(to_webvtt(moments, Profile(mode="analyst")))
    assert len(cues) > 20
    starts = [c[1] for c in cues]
    assert starts == sorted(starts)
    assert all(start < end and text and "-->" not in text for _, start, end, text in cues)
    assert len({c[0] for c in cues}) == len(cues)


def test_webvtt_follows_the_viewer_profile(moments):
    casual = parse(to_webvtt(moments, Profile(mode="casual")))
    analyst = parse(to_webvtt(moments, Profile(mode="analyst")))
    assert len(casual) < len(analyst)
    assert sum("GOAL!" in c[3] for c in casual) == 5
    spanish = parse(to_webvtt(moments, Profile(mode="casual", lang="es")))
    assert sum("¡GOL!" in c[3] for c in spanish) == 5


def test_webvtt_export_does_not_depend_on_previous_calls(moments):
    p = Profile(mode="casual")
    assert to_webvtt(moments, p) == to_webvtt(moments, p)
