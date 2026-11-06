from datetime import UTC, datetime, timedelta

WATCHED = ("Score", "NObs", "Arc", "V", "Not_Seen_dys", "Updated")


def _iso(t: datetime) -> str:
    whole = datetime.fromtimestamp(round(t.timestamp()), UTC)
    return whole.strftime("%Y-%m-%dT%H:%M:%SZ")


def from_mpc(row: dict, at: datetime) -> dict:
    first = datetime(row["Discovery_year"], row["Discovery_month"], 1, tzinfo=UTC)
    first += timedelta(days=row["Discovery_day"] - 1)
    return {
        "schema_version": 0,
        "id": row["Temp_Desig"],
        "lane": "near",
        "source": "mpc-neocp",
        "ra": row["R.A."] * 15,
        "dec": row["Decl."],
        "t_first": _iso(first),
        "t_last": _iso(first + timedelta(days=row["Arc"])),
        "n_obs": row["NObs"],
        "mag": row["V"],
        "score": row["Score"],
        "arc_days": row["Arc"],
        "h": row["H"],
        "not_seen_days": row["Not_Seen_dys"],
        "urgency": None,
        "motion": None,
        "outcome": "pending",
        "stations": [],
    }


def diff(previous: list[dict], current: list[dict]) -> list[tuple[str, dict]]:
    before = {row["Temp_Desig"]: row for row in previous}
    now = {row["Temp_Desig"]: row for row in current}
    events = []
    for desig, row in now.items():
        old = before.get(desig)
        if old is None:
            events.append(("appeared", row))
        elif any(old[key] != row[key] for key in WATCHED):
            events.append(("updated", row))
    events += [("vanished", row) for desig, row in before.items() if desig not in now]
    return events
