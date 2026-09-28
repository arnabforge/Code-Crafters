import json
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parent / "vehicles.json"

with CATALOG_PATH.open("r", encoding="utf-8") as fh:
    VEHICLES = json.load(fh)

def vehicle_with_defaults(v):
    out = dict(v)
    out["derived_km_per_kwh"] = round(v["reference_range_km"] / v["battery_kwh"], 2)
    out["derived_kwh_per_100km"] = round(v["battery_kwh"] / v["reference_range_km"] * 100, 2)
    return out
