import re
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
import json


def normalize_detail(detail: dict, hierarchy: dict) -> dict:
    """Return {'meter_id','serial_no','make','phase_type','install_status','installation_type'}
    from either detail shape the portal uses:
      A) {"classData": "<json string with installed_meter>"}
      B) {"data": [{"parameterName": ..., "parameterValue": ...}, ...]}
    Falls back to the hierarchy block for fields missing from the detail."""
    detail = detail or {}
    out = {}
    if "classData" in detail:
        c = json.loads(detail["classData"]).get("installed_meter", {})
        out = {"meter_id": c.get("MeterId"), "serial_no": c.get("SerialNo"),
               "make": c.get("Make"), "phase_type": c.get("PhaseType"),
               "install_status": c.get("InstallationStatus"),
               "installation_type": c.get("InstallationType")}
    elif "data" in detail:
        p = {x.get("parameterName"): x.get("parameterValue") for x in detail["data"]}
        out = {"meter_id": p.get("Meter ID"), "serial_no": p.get("Serial No"),
               "make": p.get("Make"), "phase_type": p.get("Phase Type"),
               "install_status": p.get("Installation Status"),
               "installation_type": p.get("Installation Type")}
    out["meter_id"] = out.get("meter_id") or hierarchy.get("Meter ID")
    out["install_status"] = out.get("install_status") or hierarchy.get("Installation Status")
    out["installation_type"] = out.get("installation_type") or hierarchy.get("Installation Type")
    return out

IST = timezone(timedelta(hours=5, minutes=30))  # assumption: portal times are India local time


def parse_ts(s: str) -> datetime:
    return datetime.strptime(s, "%d/%m/%Y %H:%M").replace(tzinfo=IST)


def split_label(s: str | None):
    """'Feeder 8 (F-008)' -> {'name': 'Feeder 8', 'code': 'F-008'}"""
    if not s:
        return None
    m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", s)
    return {"name": m.group(1), "code": m.group(2)} if m else {"name": s, "code": None}


class MeterSummary(BaseModel):
    meter_id: str
    serial_no: str | None
    make: str | None
    phase_type: str | None
    install_status: str | None
    dt_code: str | None


class Location(BaseModel):
    latitude: float
    longitude: float


class MeterDetail(MeterSummary):
    installation_type: str | None
    location: Location | None
    hierarchy: dict[str, dict | None]


class Reading(BaseModel):
    timestamp: datetime          # ISO 8601 with +05:30
    kwh_register: float          # cumulative import register, kWh
    kvah_register: float         # cumulative apparent register, kVAh
    voltage_r: float | None      # volts, phase R
    consumption_kwh: float | None  # delta vs previous reading (None for first / on reset)


def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def build_readings(rows: list[dict]) -> list[Reading]:
    rows = sorted(rows, key=lambda r: parse_ts(r["timestamp"]))
    out, prev = [], None
    for r in rows:
        kwh = to_float(r.get("kwh"))
        delta = round(kwh - prev, 4) if kwh is not None and prev is not None and kwh >= prev else None
        out.append(Reading(
            timestamp=parse_ts(r["timestamp"]), kwh_register=kwh,
            kvah_register=to_float(r.get("kvah")), voltage_r=to_float(r.get("voltR")),
            consumption_kwh=delta,
        ))
        prev = kwh if kwh is not None else prev
    return out