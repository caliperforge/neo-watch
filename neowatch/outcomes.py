import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from neowatch import mpc, poll
from neowatch.record import _iso

HISTORY = poll.HISTORY
OUTCOMES = Path("data/outcomes.jsonl")
RECENT = timedelta(hours=48)


def _vanished() -> dict[str, str]:
    last = {}
    for path in sorted(HISTORY.glob("*.jsonl")):
        for line in path.read_text().splitlines():
            event = json.loads(line)
            last[event["record"]["id"]] = (event["event"], event["at"])
    return {id: at for id, (event, at) in last.items() if event == "vanished"}


def _carried() -> dict[str, tuple[str, str]]:
    carried = {}
    for line in OUTCOMES.read_text().splitlines(keepends=True) if OUTCOMES.exists() else []:
        outcome = json.loads(line)
        if outcome["outcome"] != "unresolved":
            carried[outcome["id"]] = (outcome["vanished_at"], line)
    return carried


def _recent(at: str, now: datetime) -> bool:
    return now - datetime.fromisoformat(at) < RECENT


def _fate(id, at, now, previous, circulars) -> tuple[str, str | None, str | None]:
    designation = previous.get(id)
    if designation in circulars:
        return "confirmed_neo", "mpc-mpec", circulars[designation]
    if _recent(at, now):
        return "unresolved", None, None
    if designation:
        return "not_neo", "mpc-previous", mpc.PREVIOUS
    if id in previous:
        return "lost", "mpc-previous", mpc.PREVIOUS
    return "unresolved", None, None


def decide(now: datetime) -> list[str]:
    carried = _carried()
    rows = [(at, id, line) for id, (at, line) in carried.items()]
    previous, circulars = mpc.previous(), mpc.circulars()
    for id, at in _vanished().items():
        if id in carried:
            continue
        outcome, source, url = _fate(id, at, now, previous, circulars)
        line = {
            "id": id,
            "outcome": outcome,
            "stations": mpc.stations(id),
            "source": source,
            "url": url,
            "vanished_at": at,
            "resolved_at": None if outcome == "unresolved" else _iso(now),
        }
        rows.append((at, id, json.dumps(line) + "\n"))
    return [line for _, _, line in sorted(rows)]


def main() -> None:
    now = datetime.now(UTC)
    lines = decide(now)
    OUTCOMES.parent.mkdir(exist_ok=True)
    OUTCOMES.write_text("".join(lines))
    decided = [json.loads(line) for line in lines]
    counts = Counter(line["outcome"] for line in decided)
    for outcome in ("confirmed_neo", "not_neo", "lost", "unresolved"):
        print(f"{outcome}: {counts[outcome]}")
    for line in decided:
        if line["outcome"] == "unresolved":
            print(f"{line['id']}: {'<48 h' if _recent(line['vanished_at'], now) else 'not on previous list'}")


if __name__ == "__main__":
    main()
