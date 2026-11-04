from app.devalue import resolve
from app.models import parse_ts, split_label, build_readings

def test_devalue():
    arr = [{"a": 1, "b": 2}, "x", [3], "y"]
    assert resolve(arr) == {"a": "x", "b": ["y"]}

def test_label():
    assert split_label("Feeder 8 (F-008)") == {"name": "Feeder 8", "code": "F-008"}

def test_timestamp_is_ist():
    assert parse_ts("24/06/2026 00:00").isoformat() == "2026-06-24T00:00:00+05:30"

def test_delta():
    rows = [{"timestamp": "24/06/2026 00:00", "kwh": "10.5", "kvah": "11", "voltR": "230"},
            {"timestamp": "24/06/2026 00:30", "kwh": "10.9", "kvah": "11.4", "voltR": "x"}]
    r = build_readings(rows)
    assert r[0].consumption_kwh is None and r[1].consumption_kwh == 0.4 and r[1].voltage_r is None