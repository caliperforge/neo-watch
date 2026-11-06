import json
from dataclasses import dataclass, field
from datetime import datetime
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError

import pytest

from neowatch import poll
from neowatch.record import from_mpc

FIXTURES = Path(__file__).parent / "fixtures"
BODY = (FIXTURES / "neocp.json").read_bytes()
ROWS = json.loads(BODY)
PREVIOUS = json.loads((FIXTURES / "previous.json").read_text())


@dataclass
class Response:
    body: bytes
    status: int = 200
    headers: dict = field(default_factory=dict)

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass


def status(code):
    return HTTPError(poll.URL, code, "", Message(), None)


@pytest.fixture
def serve(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    requests = []

    def serve(outcome, previous=(), saved=None):
        if previous:
            poll.LATEST.parent.mkdir()
            poll.LATEST.write_text(json.dumps(previous))
        if saved is not None:
            poll.HEADERS.parent.mkdir(exist_ok=True)
            poll.HEADERS.write_text(json.dumps(saved))

        def urlopen(request, timeout):
            requests.append((request, timeout))
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        monkeypatch.setattr(poll, "urlopen", urlopen)
        return requests

    return serve


def test_replay_writes_each_kind_once(serve):
    serve(Response(BODY, headers={"ETag": '"e2"'}), PREVIOUS)
    poll.main()
    (history,) = poll.HISTORY.iterdir()
    events = [json.loads(line) for line in history.read_text().splitlines()]
    at = datetime.fromisoformat(events[0]["at"])
    assert history.name == f"{at:%Y-%m}.jsonl"
    assert [(e["event"], e["record"]) for e in events] == [
        ("updated", from_mpc(ROWS[1], at)),
        ("appeared", from_mpc(ROWS[-1], at)),
        ("vanished", from_mpc(PREVIOUS[-1], at)),
    ]
    assert json.loads(poll.LATEST.read_text()) == ROWS
    assert json.loads(poll.HEADERS.read_text()) == {"ETag": '"e2"'}


@pytest.mark.parametrize("outcome", [Response(BODY), status(304)], ids=["unchanged", "304"])
def test_no_events_append_nothing(serve, outcome):
    serve(outcome, ROWS)
    poll.main()
    assert not poll.HISTORY.exists()


@pytest.mark.parametrize(
    "outcome, error",
    [
        (status(500), HTTPError),
        (Response(BODY, status=203), RuntimeError),
        (TimeoutError(), TimeoutError),
        (Response(b"<html>"), json.JSONDecodeError),
    ],
    ids=["500", "203", "timeout", "not-json"],
)
def test_refused_fetch_writes_nothing(serve, outcome, error):
    serve(outcome, PREVIOUS, {"ETag": '"e1"'})
    poll.HISTORY.mkdir()
    (poll.HISTORY / "2026-11.jsonl").write_text('{"event": "appeared"}\n')
    before = {path: path.read_bytes() for path in Path().rglob("*") if path.is_file()}
    with pytest.raises(error):
        poll.main()
    assert {path: path.read_bytes() for path in Path().rglob("*") if path.is_file()} == before


@pytest.mark.parametrize(
    "saved, sent",
    [
        ({}, {}),
        ({"ETag": '"e1"'}, {"If-none-match": '"e1"'}),
        ({"Last-Modified": "Fri, 06 Nov 2026 16:00:00 GMT"}, {"If-modified-since": "Fri, 06 Nov 2026 16:00:00 GMT"}),
        (
            {"ETag": '"e1"', "Last-Modified": "Fri, 06 Nov 2026 16:00:00 GMT"},
            {"If-none-match": '"e1"', "If-modified-since": "Fri, 06 Nov 2026 16:00:00 GMT"},
        ),
    ],
    ids=["none", "etag", "last-modified", "both"],
)
def test_sends_saved_validators(serve, saved, sent):
    requests = serve(status(304), saved=saved)
    poll.main()
    ((request, timeout),) = requests
    assert timeout == 30
    assert dict(request.header_items()) == {"User-agent": poll.USER_AGENT, **sent}


@pytest.mark.live
def test_live_fetch():
    fetched = poll.fetch({})
    assert fetched is not None
    rows, _ = fetched
    assert rows and all(ROWS[0].keys() <= row.keys() for row in rows)
