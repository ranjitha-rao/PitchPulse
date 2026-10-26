import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pitchpulse.engine import MatchEngine  # noqa: E402
from pitchpulse.simulator import generate_match  # noqa: E402


@pytest.fixture(scope="session")
def events():
    return generate_match(seed=7)


@pytest.fixture(scope="session")
def played(events):
    """The demo match run through the engine: (engine, moments)."""
    engine = MatchEngine()
    moments = []
    for ev in events:
        moments += engine.ingest(ev)
    return engine, moments


@pytest.fixture(scope="session")
def engine(played):
    return played[0]


@pytest.fixture(scope="session")
def moments(played):
    return played[1]


def first(moments, kind):
    return next(m for m in moments if m.type == kind)
