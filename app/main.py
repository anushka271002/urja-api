import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
from .devalue import decode_data_json
from .models import *  # noqa
from .portal import PortalClient, PortalError, PortalNotFound, Settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.portal = PortalClient(Settings())
    yield
    await app.state.portal.aclose()

app = FastAPI(title="Urja Meter API", version="0.1.0", lifespan=lifespan)


def portal() -> PortalClient:
    return app.state.portal


@app.exception_handler(PortalNotFound)
async def _nf(_, e):
    from fastapi.responses import JSONResponse
    return JSONResponse({"error": {"code": "not_found", "message": "meter not found"}}, 404)


@app.exception_handler(PortalError)
async def _pe(_, e):
    from fastapi.responses import JSONResponse
    return JSONResponse({"error": {"code": "upstream_error", "message": str(e)}}, 502)


@app.get("/health")
async def health():
    return {"status": "ok", "portal_session_age_seconds": portal().session_age}


@app.get("/meters")
async def list_meters(q: str = "", page: int = Query(1, ge=1)):
    body = await portal().get_json("/portal/meters/search", {"q": q, "page": page})
    items = [MeterSummary(
        meter_id=m["meterId"], serial_no=m.get("serialNo"), make=m.get("make"),
        phase_type=m.get("phaseType"), install_status=m.get("installStatus"),
        dt_code=m.get("dtCode")) for m in body["data"]]
    meta = {k: v for k, v in body.items() if k != "data"}  # pass through whatever paging info exists
    return {"data": items, "page": page, "portal_meta": meta}


@app.get("/meters/{meter_id}", response_model=MeterDetail)
async def get_meter(meter_id: str):
    meter_id = meter_id.upper()
    page, geo = await asyncio.gather(
        portal().get_json(f"/meters/{meter_id}/__data.json"),
        portal().get_json(f"/portal/meters/{meter_id}/geo"),
    )
    d = decode_data_json(page)
    h = d.get("hierarchy") or {}
    info = normalize_detail(d.get("detail"), h)
    if not info.get("meter_id"):
        raise PortalNotFound(meter_id)
    g = geo.get("data") or {}
    lat, lon = to_float(g.get("latitude")), to_float(g.get("longitude"))
    return MeterDetail(
        **info,
        dt_code=(split_label(h.get("DT")) or {}).get("code"),
        location=Location(latitude=lat, longitude=lon) if lat is not None and lon is not None else None,
        hierarchy={k.lower().replace(" ", "_"): split_label(v)
                   for k, v in h.items() if k not in ("Meter ID", "Installation Status", "Installation Type")},
    )
    return MeterDetail(
        meter_id=cls["MeterId"], serial_no=cls.get("SerialNo"), make=cls.get("Make"),
        phase_type=cls.get("PhaseType"), install_status=cls.get("InstallationStatus"),
        installation_type=cls.get("InstallationType"),
        dt_code=(split_label(h.get("DT")) or {}).get("code"),
        location=Location(latitude=lat, longitude=lon) if lat is not None and lon is not None else None,
        hierarchy={k.lower().replace(" ", "_"): split_label(v)
                   for k, v in h.items() if k not in ("Meter ID", "Installation Status", "Installation Type")},
    )


@app.get("/meters/{meter_id}/consumption")
async def get_consumption(meter_id: str,
                          from_: datetime | None = Query(None, alias="from"),
                          to: datetime | None = None):
    meter_id = meter_id.upper()
    body = await portal().get_json(f"/portal/meters/{meter_id}/energy")
    readings = build_readings(body["data"])
    if from_:
        readings = [r for r in readings if r.timestamp >= from_.astimezone(IST)] if from_.tzinfo else \
                   [r for r in readings if r.timestamp >= from_.replace(tzinfo=IST)]
    if to:
        readings = [r for r in readings if r.timestamp <= (to if to.tzinfo else to.replace(tzinfo=IST))]
        total, size = body.get("total"), body.get("pageSize", 20)
    return {
        "data": items,
        "pagination": {
            "page": page,
            "page_size": size,
            "total": total,
            "total_pages": -(-total // size) if total else None,
        },
    }