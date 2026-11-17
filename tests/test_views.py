import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from neowatch import mpc, outcomes, poll, views
from tests.test_outcomes import NOW, line

FIXTURES = Path(__file__).parent / "fixtures"
EVENTS = [
    ("2026-11-09T22:00:00Z", "appeared", "A11Jiap"),
    ("2026-11-09T23:00:00Z", "vanished", "SarSza7"),
    ("2026-11-10T01:00:00Z", "appeared", "L7ra0Bq"),
    ("2026-11-10T03:00:00Z", "vanished", "P22s0Hl"),
    ("2026-11-10T03:00:00Z", "appeared", "ATL6c2n"),
    ("2026-11-10T09:00:00Z", "updated", "L7ra0Bq"),
]
DECIDED = [
    line("CEZPZH2", "lost", "mpc-previous", mpc.PREVIOUS, "2026-11-01T00:00:00Z"),
    line("SarSza7", "confirmed_neo", "mpc-mpec", None, "2026-11-09T23:00:00Z"),
    line("P22s0Hl", "unresolved", None, None, "2026-11-10T03:00:00Z"),
]


@pytest.fixture
def empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def inputs(empty):
    poll.LATEST.parent.mkdir()
    poll.LATEST.write_text((FIXTURES / "neocp.json").read_text())
    poll.HISTORY.mkdir()
    with (poll.HISTORY / "2026-11.jsonl").open("w") as history:
        for at, event, id in EVENTS:
            history.write(json.dumps({"at": at, "event": event, "record": {"id": id}}) + "\n")
    outcomes.OUTCOMES.parent.mkdir()
    outcomes.OUTCOMES.write_text("".join(DECIDED))


def test_build_matches_golden(inputs):
    assert views.build(NOW) == json.loads((FIXTURES / "views.json").read_text())


def test_empty_history_gives_zero_counts(empty):
    built = views.build(NOW)
    zero = dict.fromkeys(views.FATES, 0)
    assert (built["days"], built["polled_at"]) == ([], None)
    assert built["outcomes"] == {"all_time": zero, "last_7_days": zero}


def test_build_makes_no_network_call(inputs, monkeypatch):
    def urlopen(*args, **kwargs):
        pytest.fail("build fetched")

    monkeypatch.setattr(poll, "urlopen", urlopen)
    monkeypatch.setattr(mpc, "urlopen", urlopen)
    assert views.build(NOW)["tonight"]


def test_repo_views_under_200_kb(monkeypatch):
    monkeypatch.chdir(Path(__file__).parent.parent)
    assert len(json.dumps(views.build(datetime.now(UTC))).encode()) < 200 * 1024
