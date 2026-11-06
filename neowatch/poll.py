import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from neowatch.record import _iso, diff, from_mpc

URL = "https://www.minorplanetcenter.net/Extended_Files/neocp.json"
USER_AGENT = "caliperforge-neo-watch/0.1 (+https://github.com/caliperforge/neo-watch)"
LATEST = Path("state/latest.json")
HEADERS = Path("state/headers.json")
HISTORY = Path("history")
VALIDATORS = {"ETag": "If-None-Match", "Last-Modified": "If-Modified-Since"}


def fetch(saved: dict) -> tuple[list, dict] | None:
    headers = {"User-Agent": USER_AGENT}
    headers |= {sent: saved[name] for name, sent in VALIDATORS.items() if name in saved}
    try:
        with urlopen(Request(URL, headers=headers), timeout=30) as response:
            if response.status != 200:
                raise RuntimeError(f"{URL} answered {response.status}")
            rows = json.loads(response.read())
            got = {name: value for name in VALIDATORS if (value := response.headers.get(name))}
    except HTTPError as error:
        if error.code == 304:
            return None
        raise
    return rows, got


def main() -> None:
    previous = json.loads(LATEST.read_text()) if LATEST.exists() else []
    saved = json.loads(HEADERS.read_text()) if HEADERS.exists() else {}
    fetched = fetch(saved)
    if fetched is None:
        return
    rows, headers = fetched
    now = datetime.now(UTC)
    lines = [
        json.dumps({"at": _iso(now), "event": kind, "record": from_mpc(row, now)}) + "\n"
        for kind, row in diff(previous, rows)
    ]
    if lines:
        HISTORY.mkdir(exist_ok=True)
        with (HISTORY / f"{now:%Y-%m}.jsonl").open("a") as history:
            history.writelines(lines)
    LATEST.parent.mkdir(exist_ok=True)
    LATEST.write_text(json.dumps(rows))
    HEADERS.write_text(json.dumps(headers))


if __name__ == "__main__":
    main()
