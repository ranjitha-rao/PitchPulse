import string

import pytest

from pitchpulse.i18n import LANGS, RECAP, T
from pitchpulse.personalize import SLOTS


def placeholders(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_every_cue_template_exists_in_every_language_and_voice():
    for lang in LANGS:
        assert set(T[lang]) == set(SLOTS), lang
        for kind, voices in T[lang].items():
            assert set(voices) == {"casual", "analyst"}, (lang, kind)


@pytest.mark.parametrize("lang", [lang for lang in LANGS if lang != "en"])
def test_translations_use_the_same_facts_as_english(lang):
    for kind, voices in T["en"].items():
        for voice, parts in voices.items():
            en = set().union(*(placeholders(t) for _, t in parts))
            other = set().union(*(placeholders(t) for _, t in T[lang][kind][voice]))
            assert en == other, (lang, kind, voice)
            assert [c for c, _ in parts] == [c for c, _ in T[lang][kind][voice]], (lang, kind, voice)


@pytest.mark.parametrize("lang", LANGS)
def test_recap_templates_match_english(lang):
    assert set(RECAP[lang]) == set(RECAP["en"])
    for key, text in RECAP["en"].items():
        assert placeholders(text) == placeholders(RECAP[lang][key]), (lang, key)
