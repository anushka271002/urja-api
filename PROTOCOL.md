# How the Urja Meter Ops portal works

Findings from exploring https://urja-ops.flockenergy.tech as a normal logged-in user, using browser DevTools only. Read-only; nothing was modified.

## Stack

- Front end: **SvelteKit** (Svelte, Tailwind). Auth: **Better Auth**.
- The HTML source contains no data; rows are fetched after load.

## Authentication

- Login page: `/login`. The form has fields `email` and `password`, no hidden CSRF field.
- Submitting sends **`POST /login`**, form-encoded (`email`, `password`). It is a SvelteKit form action.
- **Success:** HTTP 200 and a `Set-Cookie`:
  `__Secure-better-auth.session_token=<token>.<signature>; Max-Age=3600; Path=/; HttpOnly; Secure; SameSite=Lax`
- **Failure:** body `{"type":"failure","status":401,"data":"..."}` (devalue-encoded; decodes to the email and `"Invalid email or password."`).
- Auth is **cookie only**. There is no `Authorization` header, and nothing in Local Storage. Session Storage only holds SvelteKit scroll/snapshot keys.
- **Sessions last 1 hour** (`Max-Age=3600`). An expired session sends the browser back to login (I was signed out on F5 after leaving the tab idle). A client must re-login automatically.
- Not verified: whether an `Origin` header is strictly required for the login POST. The client sends one (SvelteKit normally checks it).

## Screens

- `/meters`: paginated, searchable list (shows "403 total")
- `/meters/{id}`: meter detail
- `/transformers` and **Ops Desk**: exist in the navigation; **not explored**

## Endpoints observed

All were called with the session cookie.

### Meter list
`GET /portal/meters/search?q=<text>&page=<n>` (JSON, `page` is 1-based)
```json
{"data":[{"meterId":"J100000","serialNo":"SE33962","make":"HPL","phaseType":"single",
          "installStatus":"Decommissioned","dtCode":"DT-001"}, ...],
 "total":403,"page":1,"pageSize":20}
```
- Page size is 20, total 403, so 21 pages.
- The page fired this request twice on load.

### Meter location
`GET /portal/meters/{id}/geo`
```json
{"data":{"latitude":"26.938961002479868","longitude":"75.83095696146852"}}
```
Coordinates are **strings**.

### Meter consumption
`GET /portal/meters/{id}/energy` (about 27 kB)
```json
{"data":[{"timestamp":"23/06/2026 23:30","kwh":"48438.74","kvah":"52313.84","voltR":"226"}, ...]}
```
- Interval: 30 minutes. J100000 returned **337 rows** (about 7 days), starting 2026-06-23 23:30.
- All values, including numbers, are **strings**. Timestamps are `DD/MM/YYYY HH:mm` with **no timezone**.
- `kwh` / `kvah` grow steadily, so they look like **cumulative registers**, not per-interval usage.
- I saw no query parameters; the whole series arrives in one response.

### Meter detail (not a clean API)
`GET /meters/{id}/__data.json` returns SvelteKit's page data in **devalue** format: `{"type":"data","nodes":[...]}`, where the data node is a flat array and numbers are pointers to other array items. It decodes to:
```
{ meterId, detail, hierarchy }
```
`hierarchy` is a flat object with keys `Meter ID`, `Installation Status`, `Installation Type`, `Zone`, `Circle`, `Division`, `Subdivision`, `Sub Station`, `Feeder`, `DT`. Values look like `"Feeder 8 (F-008)"`.

`detail` comes in **two different shapes** depending on the meter:

- **A (J100007):** `{"classData": "<JSON string>"}` where the string decodes to `{"installed_meter": {"MeterId","SerialNo","Make","PhaseType","InstallationStatus","InstallationType"}}`. This is JSON inside JSON.
- **B (J100000):** `{"data":[{"parameterName":"Serial No","parameterValue":"SE33962"}, ...]}`, a list of name/value pairs.

## Quirks and surprises

1. Three naming styles: `meterId` (list), `MeterId` (classData), `"Meter ID"` / `"Sub Station"` (hierarchy and parameter names).
2. Numbers are sent as strings everywhere.
3. Timestamps are day-first with no timezone.
4. Two shapes for meter detail (above), one with a nested JSON string.
5. Hierarchy values pack a name and a code into one string.
6. Session lifetime is only 1 hour.
7. The list endpoint is called twice by the page on load.
8. Data oddity: J100000 is `Decommissioned` yet has a week of consumption readings.
9. Not verified: what the portal returns for an unknown meter ID. My client treats a detail page with no usable meter data as "not found".

## Not covered

Transformers page, Ops Desk, any export/bulk path, rate limits, and whether `energy` accepts date parameters.