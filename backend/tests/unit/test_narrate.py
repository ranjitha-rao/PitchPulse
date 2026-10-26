import pytest

from pitchpulse.narrate import allowed_numbers, numbers_in, recap_facts, render, render_recap, validate

from ..conftest import first


def goal_facts(**extra):
    base = [
        {"id": "scorer", "value": "Samir Haddad"}, {"id": "team", "value": "Harbourside FC"},
        {"id": "score_home", "value": 1}, {"id": "score_away", "value": 2}, {"id": "minute", "value": 64},
        {"id": "xg", "value": 0.29}, {"id": "shot_speed", "value": 100},
        {"id": "wp_before", "value": 1}, {"id": "wp_after", "value": 6},
    ]
    return base + [{"id": k, "value": v} for k, v in extra.items()]


def test_optional_fragments_follow_the_facts():
    plain = render("goal", goal_facts(), "casual", "en")
    assert plain.startswith("GOAL! Samir Haddad scores for Harbourside FC, 1-2.")
    assert "Set up by" not in plain and "comeback" not in plain
    assisted = render("goal", goal_facts(assister="Daniel Okafor", storyline="comeback"), "casual", "en")
    assert "Set up by Daniel Okafor." in assisted and "The comeback is on." in assisted
    done = render("goal", goal_facts(storyline="comeback", comeback_from="0-2"), "casual", "en")
    assert "turned 0-2 into a lead" in done and "The comeback is on." not in done


def test_rhythm_direction_and_localised_words():
    facts = [{"id": "tempo_then", "value": 10.0}, {"id": "tempo_now", "value": 15.0},
             {"id": "change", "value": 50}, {"id": "chaos", "value": 40.0}]
    assert render("rhythm_shift", facts, "casual", "en") == "The game has sped up."
    facts[2]["value"] = -30
    assert render("rhythm_shift", facts, "casual", "en") == "The game has slowed right down."
    chance = [{"id": "player", "value": "Noah Fischer"}, {"id": "outcome", "value": "off_target"}]
    assert render("big_chance", chance, "casual", "es").endswith("fuera.")


def test_numbers_in_handles_decimals_commas_and_arabic_digits():
    assert numbers_in("xG 0.29 at 100 km/h") == [0.29, 100.0]
    assert numbers_in("xG 0,29") == [0.29]
    assert numbers_in("سرعة ١٠٠ كم/س") == [100.0]
    assert numbers_in("gap -29.1") == [-29.1]


def test_validator_accepts_grounded_and_rejects_invented_numbers():
    facts = [{"id": "xg", "value": 0.29}, {"id": "shot_speed", "value": 100}, {"id": "gap", "value": -29.1}]
    assert validate("A 100 km/h strike from a 0.29 xG chance", facts) == (True, [])
    assert validate("A 29% chance", facts)[0]
    assert validate("The gap is 29.1", facts)[0]
    ok, bad = validate("A 112 km/h strike from 25 yards", facts)
    assert not ok and bad == [112.0, 25.0]


def test_allowed_numbers_ignore_booleans_and_read_strings():
    allowed = allowed_numbers([{"id": "is_record", "value": True}, {"id": "from", "value": "0-2"}])
    assert 1.0 not in allowed and {0.0, 2.0} <= allowed


def test_engine_captions_are_grounded_in_every_language(moments):
    for mo in moments:
        facts = mo.facts + [{"id": "minute", "value": mo.minute}]
        for lang in ("en", "es", "ar"):
            for voice in ("casual", "analyst"):
                text = render(mo.type, mo.facts, voice, lang)
                assert text
                assert validate(text, facts)[0], (mo.type, lang, voice, text)


@pytest.mark.parametrize("lang, word", [("en", "came back from 0-2"), ("es", "remontó"), ("ar", "عاد من تأخر")])
def test_full_time_recap_tells_the_comeback(engine, lang, word):
    facts = recap_facts(engine)
    recap = render_recap(facts, lang)
    assert word in recap["text"]
    assert recap["lines"][0].startswith("Harbourside FC 3-2 Northgate Albion")
    assert facts["player_of_match"]["name"] == "Daniel Okafor"
    flat = [{"id": str(i), "value": v} for i, v in enumerate(_leaves(facts))]
    assert validate(recap["text"], flat)[0]


def test_half_time_recap_has_no_full_time_claims(engine):
    facts = recap_facts(engine, half=True)
    assert "comeback" not in facts and "win_prob_low" not in facts
    text = render_recap(facts, "en", half=True)["text"]
    assert "Player of the match" not in text


def test_first_goal_caption_in_spanish(moments):
    g = first(moments, "goal")
    assert render("goal", g.facts, "casual", "es").startswith("¡GOL! Noah Fischer marca para Northgate Albion")


def _leaves(d):
    for v in d.values():
        if isinstance(v, dict):
            yield from _leaves(v)
        elif isinstance(v, list):
            yield ", ".join(map(str, v))
        else:
            yield v
