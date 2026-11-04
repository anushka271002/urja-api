Framework : SvelteKit
Login form: <form method="POST"> with no action attribute, so it posts to the same URL as the page I was on.
node_ids: [0, 7]: the page is built from layout node 0 and page node 7. The portal has at least 8 route components, so there are more screens than just this one.

## Login
- URL:https://urja-ops.flockenergy.tech/login
- Method: POST
- Request name - login
- Status code - 200 OK
- Remote address - [64:ff9b::2851:f567]:443
- content-type - application/json
- Payload form encoded
- set-cookie : __Secure-better-auth.session_token=2cJEiIPf5x1twaqIOg9KXWHoq4ChuqND.%2BDVpPzMBsgjpkfJGGMrs3xAR0Z4xSQequy99FrBfM3g%3D; Max-Age=3600; Path=/; HttpOnly; Secure; SameSite=Lax
- Session storage keys - sveltekit:scroll	{"1793772313381":{"x":0,"y":0},"1793772313382":{"x":0,"y":0}}
sveltekit:snapshot	{}

- How auth is carried (cookie/header):
## Auth (so far)
- Framework: SvelteKit + Better Auth
- Login: POST /login, SvelteKit form action, failure = 401 {"type":"failure",...} with devalue-encoded data
- Session: cookie __Secure-better-auth.session_token (HttpOnly, Secure, SameSite=Lax, path=/), format token.signature
- No Authorization header; cookie only
- Cookie expiry observed: 1 hr


Finding	Why it matters
Three different naming styles: meterId (list), MeterId / InstallationStatus (detail), "Meter ID" / "Sub Station" (hierarchy keys)	Your API must normalise to one style (snake_case)
The meter detail comes from SvelteKit’s __data.json in devalue format, not a clean API	You need a small decoder
Inside it, classData is a JSON string inside JSON, which needs a second parse	Quirk worth documenting
Hierarchy values look like "Feeder 8 (F-008)"	Split into name and code
Timestamps are "23/06/2026 23:30": day-first, no timezone	Assume IST (+05:30) and output ISO 8601
kwh, kvah, voltR, and lat/lng are all strings	Convert to numbers
kwh rises about 0.42 per 30 minutes (48438.74 → 48439.16), so it is a cumulative register, not per-interval usage	Compute the per-interval delta
J100000 is “Decommissioned” but has energy data, and the list says DT-001 while the detail hierarchy uses a different format	Data-quality quirks
The session lasts 1 hour (Max-Age=3600)	Auto re-login

- Quirk: meter detail comes in 2 shapes: classData (JSON string inside JSON) or
  detail.data = [{parameterName, parameterValue}]. Shape varies per meter.
- Quirk: hierarchy values are "Name (CODE)" strings.
- Mistake: coded against one sample (J100007), crashed on J100000. Fixed by handling both + 404 for unknown.