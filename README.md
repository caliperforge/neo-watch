# neo-watch

Lost tonight: which near-Earth object candidates on the Minor Planet Center confirmation page will be lost without follow-up, and where to point tonight.

Record shape: https://github.com/caliperforge/sky-schema (vendored under `tests/fixtures/sky-schema/`, commit 4120d17).

Every 15 minutes `.github/workflows/poll.yml` fetches the MPC NEO confirmation page as JSON from https://www.minorplanetcenter.net/Extended_Files/neocp.json, keeps the raw rows in `state/latest.json`, and appends one appeared, updated or vanished record per change to `history/<YYYY-MM>.jsonl`. The page answers with both `ETag` and `Last-Modified`; the poller saves them in `state/headers.json` and sends them back as `If-None-Match` and `If-Modified-Since`. A fetch that fails on the network 3 times appends `{"at", "error"}` to `state/misses.jsonl` and leaves the state as it was, so gaps in the history are counted.

Every day at 11:30 UTC `.github/workflows/outcomes.yml` runs `uv run python -m neowatch.outcomes`, which gives each candidate whose last history event is `vanished` one line in `data/outcomes.jsonl`, at its last vanish. It reads three MPC pages, each HTML with no `ETag` or `Last-Modified` and an update rhythm not stated: https://www.minorplanetcenter.net/iau/NEO/ToConfirm_PrevDes.html, a `<li>` list giving each former candidate's designation (`2026 VH<sub>9</sub> = SarSza7`) or fate (`was not confirmed`, `does not exist`), whose entries follow the Daily Orbit Update MPEC; https://www.minorplanetcenter.net/mpec/RecentMPECs.html, the links and titles of the 100 most recent MPECs; and https://cgi.minorplanetcenter.net/cgi-bin/showobsorbs.cgi?Obj=<id>&obs=y, the candidate's observations in a `<pre>` block, whose columns 78-80 give the stations. A candidate whose designation titles one of those MPECs is `confirmed_neo`; one vanished under 48 h ago is `unresolved`; one the previous list designates is `not_neo`, and one it lists without a designation is `lost`; any other is `unresolved`. Decided lines are kept byte for byte; `unresolved` ones are decided again on the next run.

```
uv run python -m neowatch.poll
uv run pytest
uv run pytest -m live
```

`tests/fixtures/neocp.json` is synthetic: twelve hand-written rows in the MPC confirmation-page shape of 2026-11-06. Part b replaces it with rows recorded on its first live fetch.
