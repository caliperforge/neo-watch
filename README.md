# neo-watch

Lost tonight: which near-Earth object candidates on the Minor Planet Center confirmation page will be lost without follow-up, and where to point tonight.

Record shape: https://github.com/caliperforge/sky-schema (vendored under `tests/fixtures/sky-schema/`, commit 4120d17).

Every 15 minutes `.github/workflows/poll.yml` fetches the MPC NEO confirmation page as JSON from https://www.minorplanetcenter.net/Extended_Files/neocp.json, keeps the raw rows in `state/latest.json`, and appends one appeared, updated or vanished record per change to `history/<YYYY-MM>.jsonl`. The page answers with both `ETag` and `Last-Modified`; the poller saves them in `state/headers.json` and sends them back as `If-None-Match` and `If-Modified-Since`. A fetch that fails on the network 3 times appends `{"at", "error"}` to `state/misses.jsonl` and leaves the state as it was, so gaps in the history are counted.

```
uv run python -m neowatch.poll
uv run pytest
uv run pytest -m live
```

`tests/fixtures/neocp.json` is synthetic: twelve hand-written rows in the MPC confirmation-page shape of 2026-11-06. Part b replaces it with rows recorded on its first live fetch.
