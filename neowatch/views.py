import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from neowatch import outcomes, poll
from neowatch.record import _iso, from_mpc

VIEWS = Path("data/views.json")
WEEK = timedelta(days=7)
KEPT = ("id", "score", "ra", "dec", "mag", "h", "n_obs", "arc_days", "not_seen_days")
FATES = ("confirmed_neo", "not_neo", "lost", "unresolved")


def _read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def _counts(lines: list[dict]) -> dict[str, int]:
    counts = Counter(line["outcome"] for line in lines)
    return {fate: counts[fate] for fate in FATES}


def build(now: datetime) -> dict:
    events = [event for path in sorted(poll.HISTORY.glob("*.jsonl")) for event in _read(path)]
    rows = json.loads(poll.LATEST.read_text()) if poll.LATEST.exists() else []
    records = [from_mpc(row, now) for row in rows]
    tonight = sorted(records, key=lambda record: (record["score"], record["not_seen_days"]), reverse=True)
    days = {}
    for event in events:
        days.setdefault(event["at"][:10], Counter())[event["event"]] += 1
    decided = _read(outcomes.OUTCOMES)
    week = [line for line in decided if now - datetime.fromisoformat(line["vanished_at"]) <= WEEK]
    return {
        "generated_at": _iso(now),
        "polled_at": max((event["at"] for event in events), default=None),
        "tonight": [{key: record[key] for key in KEPT} for record in tonight],
        "days": [{"day": day, "appeared": n["appeared"], "vanished": n["vanished"]} for day, n in sorted(days.items())],
        "outcomes": {"all_time": _counts(decided), "last_7_days": _counts(week)},
    }


def main() -> None:
    views = build(datetime.now(UTC))
    VIEWS.parent.mkdir(exist_ok=True)
    VIEWS.write_text(json.dumps(views))


if __name__ == "__main__":
    main()
