# Urja Meter API

A small REST API that sits in front of the legacy "Urja Meter Ops" web portal, which has no public API. It logs in to the portal on your behalf, calls the portal's internal endpoints, and returns clean, consistent JSON.

- How the portal works: [PROTOCOL.md](PROTOCOL.md)
- OpenAPI spec: [openapi.json](openapi.json) (also served live at `/docs` when running)

## What it exposes

| Endpoint | Description |
|---|---|
| `GET /health` | Service status and age of the portal session |
| `GET /meters?q=&page=` | Paginated meter list, with optional search by meter number or serial |
| `GET /meters/{meter_id}` | Meter detail: attributes, location, and network hierarchy |
| `GET /meters/{meter_id}/consumption?from=&to=` | Half-hourly readings with per-interval consumption |

## Structure

```
app/
  portal.py    portal client: login, cookie handling, auto re-login on expiry
  devalue.py   decoder for SvelteKit's __data.json ("devalue") format
  models.py    response models and cleanup helpers (types, timestamps, labels)
  main.py      FastAPI app and endpoints
tests/         unit tests for parsing helpers
```

Flow: request -> `main.py` -> `portal.py` (session + HTTP) -> `devalue.py` (detail page only) -> `models.py` (normalise) -> clean JSON.

## Run it

Requires Python 3.10+.

```
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
# edit .env and set PORTAL_PASSWORD
python -m pytest
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/docs.

Configuration (`.env`): `PORTAL_URL`, `PORTAL_EMAIL`, `PORTAL_PASSWORD`. Credentials are never committed.

To regenerate the spec:
```
python -c "import json; from app.main import app; json.dump(app.openapi(), open('openapi.json','w'), indent=2)"
```

## Sample request

```
curl http://127.0.0.1:8000/meters/J100000
```
```json
{
  "meter_id": "J100000",
  "serial_no": "SE33962",
  "make": "HPL",
  "phase_type": "single",
  "install_status": "Decommissioned",
  "dt_code": "DT-001",
  "installation_type": "Whole Current",
  "location": {"latitude": 26.938961, "longitude": 75.830957},
  "hierarchy": {
    "zone": {"name": "Jaipur Zone 1", "code": "Z-01"},
    "feeder": {"name": "Feeder 1", "code": "F-001"},
    "dt": {"name": "Malviya Nagar DT 1", "code": "DT-001"}
  }
}
```
(hierarchy shortened; the real response also has circle, division, subdivision, sub_station)

Errors always use `{"error": {"code": "...", "message": "..."}}`: 404 `not_found`, 502 `upstream_error`.

## Assumptions

- **Timezone:** the portal sends `DD/MM/YYYY HH:mm` with no timezone. I assumed India local time (IST, +05:30) and output ISO 8601 with that offset.
- **`kwh` and `kvah` are cumulative registers**, not per-interval usage (they rise by about 0.4 every 30 minutes). I return them as `kwh_register` / `kvah_register` and compute `consumption_kwh` as the difference from the previous reading. If a register goes down (a possible meter reset), the delta is `null` rather than negative.
- **`voltR` is volts on phase R.** Inferred from the name only.
- **Meter IDs are uppercase** (`J100000`); the API upper-cases input.
- **Consumption filtering:** the portal's `energy` endpoint returned all readings in one response (337 rows for J100000) and I saw no query parameters, so `from`/`to` are applied by my service after fetching.
- **Naive `from`/`to` values are treated as IST.**

## Design decisions and trade-offs

- **Use the portal's JSON endpoints where they exist** (`/portal/...`) and decode `__data.json` only for the detail page, where no cleaner endpoint exists. Scraping HTML was never needed.
- **One login at a time.** A lock prevents many concurrent requests from each triggering a login. The session is refreshed at 50 minutes (the portal cookie lasts 60), and a request that hits an expired session re-logs in once and retries once.
- **Normalised one naming style.** The portal mixes `meterId`, `MeterId` and `"Meter ID"`. The API uses snake_case throughout, real numbers, and ISO timestamps.
- **Both detail shapes are supported** (see PROTOCOL.md), with a fallback to the hierarchy block for missing fields.
- **No database or cache.** Every request goes to the portal. This keeps the service simple and always fresh, at the cost of speed and extra portal load.

## What I would do next

1. Add a short TTL cache (metadata around an hour, consumption a few minutes) with stale-while-revalidate.
2. Add retries with backoff and a concurrency limit so the portal is never overloaded.
3. Explore the Transformers page and expose a hierarchy tree, reporting orphaned or inconsistent nodes.
4. Mock the portal in tests so the client and re-login logic are covered.
5. Sync meters into SQLite to support filtering across attributes and "near this location" queries.
6. Verify the timezone and register assumptions with the utility.

## Reflection

**Assumptions.** Listed above. The riskiest are IST timestamps and treating `kwh` as a cumulative register. Both came from reading the data, not from documentation.

**Most difficult part.** Working out how the portal serves meter detail. It is not a clean API but SvelteKit's `__data.json` in a flattened format, and the same endpoint returned two different shapes depending on the meter. I got unstuck by printing the decoded structure for the failing meter and comparing it with the one that worked. 

**With another day.** Caching, hierarchy tree with data-quality reporting, mocked-portal tests, and the local query layer.

**A mistake I made.** I wrote the detail parser from a single sample meter, and it crashed on the next one with a 500. I also first blamed lowercase IDs, which was wrong; the real cause was the second data shape. I fixed it by handling both shapes and returning a 404 when a meter has no usable data. I also pasted my password and a live session token into my notes and a chat at one point; I redacted the notes and made sure nothing sensitive reached git. *

**What I would criticise.** There are too few tests, and none cover the HTTP client or session expiry. The portal's behaviour for unknown meter IDs is not fully verified. Every request hits the portal, which does not scale. `from`/`to` filtering happens after downloading all rows. There is no hierarchy or transformer coverage.

## Time spent and use of AI

About **3-4 hours**. I used an AI assistant for guidance (explaining DevTools, SvelteKit and devalue concepts, debugging tracebacks) and to help draft code and documentation. I did the exploration of the portal myself in the browser and tested and fixed the code against the live portal. 