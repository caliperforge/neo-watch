import json
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import pytest

from neowatch.record import diff, from_mpc

FIXTURES = Path(__file__).parent / "fixtures"
ROWS = json.loads((FIXTURES / "neocp.json").read_text())
SCHEMA = json.loads((FIXTURES / "sky-schema" / "object.json").read_text())
AT = datetime(2026, 11, 6, 16, tzinfo=UTC)
ROW = {
    "Temp_Desig": "T0Test1",
    "Score": 90,
    "Discovery_year": 2026,
    "Discovery_month": 10,
    "Discovery_day": 31.75,
    "R.A.": 13.5,
    "Decl.": -5.0,
    "V": 20.0,
    "Updated": "Added Nov. 1.30 UT",
    "NObs": 5,
    "Arc": 0.5,
    "H": 22.0,
    "Not_Seen_dys": 5.4,
}


def test_row_maps_to_near_record():
    record = from_mpc(ROW, AT)
    assert record == {
        "schema_version": 0,
        "id": "T0Test1",
        "lane": "near",
        "source": "mpc-neocp",
        "ra": 202.5,
        "dec": -5.0,
        "t_first": "2026-10-31T18:00:00Z",
        "t_last": "2026-11-01T06:00:00Z",
        "n_obs": 5,
        "mag": 20.0,
        "score": 90,
        "arc_days": 0.5,
        "h": 22.0,
        "not_seen_days": 5.4,
        "urgency": None,
        "motion": None,
        "outcome": "pending",
        "stations": [],
    }
    jsonschema.validate(record, SCHEMA)


@pytest.mark.parametrize("row", ROWS, ids=[row["Temp_Desig"] for row in ROWS])
def test_fixture_rows_validate(row):
    jsonschema.validate(from_mpc(row, AT), SCHEMA)


def test_no_labels():
    assert not any("labels" in from_mpc(row, AT) for row in ROWS)


def test_diff_reports_each_kind():
    changed = {**ROWS[5], "NObs": ROWS[5]["NObs"] + 1}
    current = ROWS[1:5] + [changed] + ROWS[6:]
    assert diff(ROWS[:-1], current) == [
        ("updated", changed),
        ("appeared", ROWS[-1]),
        ("vanished", ROWS[0]),
    ]


def test_unwatched_change_gives_no_event():
    moved = [{**row, "R.A.": (row["R.A."] + 1) % 24} for row in ROWS]
    assert diff(ROWS, ROWS) == []
    assert diff(ROWS, moved) == []
