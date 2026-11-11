import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from neowatch import mpc, outcomes, poll
from tests.test_poll import Response, status

FIXTURES = Path(__file__).parent / "fixtures" / "mpc"
PAGES = {
    mpc.PREVIOUS: (FIXTURES / "previous.html").read_bytes(),
    mpc.MPECS: (FIXTURES / "mpecs.html").read_bytes(),
}
OBSERVED = (FIXTURES / "observations.txt").read_bytes()
NOW = datetime(2026, 11, 11, 12, tzinfo=UTC)
EVENTS = [
    ("2026-11-08T00:00:00Z", "vanished", "SarSza7"),
    ("2026-11-08T00:00:00Z", "vanished", "P22s0Hl"),
    ("2026-11-08T06:00:00Z", "vanished", "CEZPZH2"),
    ("2026-11-08T12:00:00Z", "vanished", "ZZZ0001"),
    ("2026-11-11T00:00:00Z", "vanished", "CF021R2"),
]


def line(id, outcome, source, url, vanished_at):
    resolved_at = None if source is None else "2026-11-11T12:00:00Z"
    return (
        json.dumps(
            {
                "id": id,
                "outcome": outcome,
                "stations": [],
                "source": source,
                "url": url,
                "vanished_at": vanished_at,
                "resolved_at": resolved_at,
            }
        )
        + "\n"
    )


@pytest.fixture
def serve(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    requests = []

    def serve(events, failures=None):
        outcomes.HISTORY.mkdir()
        with (outcomes.HISTORY / "2026-11.jsonl").open("w") as history:
            for at, event, id in events:
                history.write(json.dumps({"at": at, "event": event, "record": {"id": id}}) + "\n")

        def urlopen(request, timeout):
            requests.append((request, timeout))
            result = (failures or {}).get(request.full_url, Response(PAGES.get(request.full_url, OBSERVED)))
            if isinstance(result, Exception):
                raise result
            return result

        monkeypatch.setattr(mpc, "urlopen", urlopen)
        return requests

    return serve


def test_each_outcome_from_saved_pages(serve):
    serve(EVENTS)
    assert outcomes.decide(NOW) == [
        line("P22s0Hl", "not_neo", "mpc-previous", mpc.PREVIOUS, "2026-11-08T00:00:00Z"),
        line(
            "SarSza7",
            "confirmed_neo",
            "mpc-mpec",
            "https://www.minorplanetcenter.net/mpec/K26/K26VN8.html",
            "2026-11-08T00:00:00Z",
        ),
        line("CEZPZH2", "lost", "mpc-previous", mpc.PREVIOUS, "2026-11-08T06:00:00Z"),
        line("ZZZ0001", "unresolved", None, None, "2026-11-08T12:00:00Z"),
        line("CF021R2", "unresolved", None, None, "2026-11-11T00:00:00Z"),
    ]


def test_vanished_and_back_counts_once_with_final_fate(serve):
    serve(
        [
            ("2026-11-07T00:00:00Z", "appeared", "CEZPZH2"),
            ("2026-11-08T00:00:00Z", "vanished", "CEZPZH2"),
            ("2026-11-08T06:00:00Z", "appeared", "CEZPZH2"),
            ("2026-11-08T12:00:00Z", "vanished", "P22s0Hl"),
            ("2026-11-09T00:00:00Z", "vanished", "CEZPZH2"),
            ("2026-11-09T06:00:00Z", "appeared", "P22s0Hl"),
            ("2026-11-09T12:00:00Z", "updated", "P22s0Hl"),
            ("2026-11-09T12:00:00Z", "appeared", "SarSza7"),
        ]
    )
    assert outcomes.decide(NOW) == [line("CEZPZH2", "lost", "mpc-previous", mpc.PREVIOUS, "2026-11-09T00:00:00Z")]


def test_second_run_writes_same_file_and_skips_decided(serve):
    requests = serve(EVENTS)
    outcomes.OUTCOMES.parent.mkdir()
    outcomes.OUTCOMES.write_text("".join(outcomes.decide(NOW)))
    requests.clear()
    assert "".join(outcomes.decide(NOW)) == outcomes.OUTCOMES.read_text()
    assert [request.full_url for request, _ in requests] == [
        mpc.PREVIOUS,
        mpc.MPECS,
        mpc.OBSERVATIONS.format("ZZZ0001"),
        mpc.OBSERVATIONS.format("CF021R2"),
    ]


def test_requests_carry_user_agent_one_per_source_plus_one_per_object(serve):
    requests = serve(EVENTS)
    outcomes.decide(NOW)
    assert [request.full_url for request, _ in requests] == [
        mpc.PREVIOUS,
        mpc.MPECS,
        *(mpc.OBSERVATIONS.format(id) for _, _, id in EVENTS),
    ]
    assert {(request.get_header("User-agent"), timeout) for request, timeout in requests} == {(poll.USER_AGENT, 30)}


@pytest.mark.parametrize("url", [mpc.PREVIOUS, mpc.MPECS, mpc.OBSERVATIONS.format("SarSza7")])
@pytest.mark.parametrize(
    "failure, error",
    [(status(500), HTTPError), (Response(b"", status=203), RuntimeError), (URLError("down"), URLError)],
    ids=["500", "203", "URLError"],
)
def test_failed_source_leaves_outcomes_unchanged(serve, url, failure, error):
    serve(EVENTS, {url: failure})
    outcomes.OUTCOMES.parent.mkdir()
    outcomes.OUTCOMES.write_text('{"id": "CF021R2", "outcome": "unresolved"}\n')
    before = outcomes.OUTCOMES.read_bytes()
    with pytest.raises(error):
        outcomes.main()
    assert outcomes.OUTCOMES.read_bytes() == before
