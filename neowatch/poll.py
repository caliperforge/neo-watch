import json
from datetime import UTC, datetime
from pathlib import Path
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from neowatch.record import _iso, diff, from_mpc

URL = "https://www.minorplanetcenter.net/Extended_Files/neocp.json"
USER_AGENT = "caliperforge-neo-watch/0.1 (+https://github.com/caliperforge/neo-watch)"
LATEST = Path("state/latest.json")
HEADERS = Path("state/headers.json")
MISSES = Path("state/misses.jsonl")
HISTORY = Path("history")
VALIDATORS = {"ETag": "If-None-Match", "Last-Modified": "If-Modified-Since"}
RETRY_DELAYS = (10, 30)


def fetch(saved: dict) -> tuple[list, dict] | None:
    headers = {"User-Agent": USER_AGENT}
    headers |= {sent: saved[name] for name, sent in VALIDATORS.items() if name in saved}
    for delay in (*RETRY_DELAYS, None):
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
        except (URLError, TimeoutError) as error:
            if delay is None:
                MISSES.parent.mkdir(exist_ok=True)
                with MISSES.open("a") as misses:
                    misses.write(json.dumps({"at": _iso(datetime.now(UTC)), "error": str(error)}) + "\n")
                return None
            sleep(delay)
            continue
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
