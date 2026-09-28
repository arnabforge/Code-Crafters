from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# IMPORTANT: config imports dotenv before any service reads environment variables.
from .config import CORS_ORIGINS, GOOGLE_MAPS_SERVER_KEY, OPENCHARGEMAP_API_KEY, EV_ADMIN_TOKEN
from .data import VEHICLES, vehicle_with_defaults
from .models import ProfileIn, PurchaseIn, PlanIn
from .db import init_db, upsert_owner, get_owner, add_purchase, add_route, list_owners, list_purchases, list_routes, delete_owner, delete_purchase, clear_all
from .services import (
    geocode, compute_route, sample_polyline, fetch_ocm_near, merge_stations,
    normalize_vehicle, usable_range, charging_minutes, simulated_queue,
    route_matrix_batch, autocomplete_places, place_details,
    search_ev_stations_along_route, search_ev_stations_nearby_google,
    enrich_google_stations_with_ocm, simulated_wait_minutes, pricing_for_station,
    rank_charging_candidates,
)

app = FastAPI(title="EVChargeRoute API", version="4.0.0")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup():
    init_db()


def admin_guard(x_admin_token: str = Header(default="")):
    if not EV_ADMIN_TOKEN or x_admin_token != EV_ADMIN_TOKEN:
        raise HTTPException(401, "Invalid admin token")
    return True


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "google_server_configured": bool(GOOGLE_MAPS_SERVER_KEY),
                "openchargemap_configured": bool(OPENCHARGEMAP_API_KEY),
    }


@app.get("/api/vehicles")
def vehicles():
    return {k: vehicle_with_defaults(v) for k, v in VEHICLES.items()}


@app.post("/api/profile")
def save_profile(req: ProfileIn):
    if req.vehicle_id not in VEHICLES:
        raise HTTPException(400, "Unknown vehicle model")
    return upsert_owner(req.model_dump())


@app.get("/api/profile")
def load_profile(email: str = Query(min_length=3, max_length=180)):
    owner = get_owner(email=email)
    if not owner:
        raise HTTPException(404, "No saved owner profile found for that email")
    return owner


@app.post("/api/purchases")
def purchase(req: PurchaseIn):
    if not get_owner(owner_id=req.owner_id):
        raise HTTPException(404, "Owner profile not found")
    return add_purchase(req.model_dump())


@app.get("/api/places/autocomplete")
def places_autocomplete(input: str = Query(min_length=2, max_length=300)):
    try:
        return {"suggestions": autocomplete_places(input)}
    except Exception as e:
        raise HTTPException(502, f"Places autocomplete error: {e}")


@app.get("/api/places/{place_id}")
def places_details(place_id: str):
    try:
        return place_details(place_id)
    except Exception as e:
        raise HTTPException(502, f"Place details error: {e}")


@app.get("/api/stations")
def stations(lat: float, lng: float, distance_km: float = 30):
    """Show nearby EV charging stations without changing the existing Stations UI."""
    ocm_stations = []
    google_stations = []
    errors = []

    if OPENCHARGEMAP_API_KEY:
        try:
            raw = fetch_ocm_near(lat, lng, distance_km, 100)
            ocm_stations = merge_stations([raw])
            print(f"[OCM STATIONS] lat={lat}, lng={lng}, radius={distance_km} km, count={len(ocm_stations)}")
        except Exception as e:
            errors.append(f"Open Charge Map: {e}")
            print(f"[OCM STATIONS ERROR] {e}")

    # Google is a fallback/coverage source; OCM remains the primary source for
    # the Stations tab because it provides the connector/operator/pricing fields
    # already used by the existing UI.
    if not ocm_stations and GOOGLE_MAPS_SERVER_KEY:
        try:
            google_stations = search_ev_stations_nearby_google(lat, lng, 20)
            print(f"[GOOGLE STATIONS] lat={lat}, lng={lng}, count={len(google_stations)}")
        except Exception as e:
            errors.append(f"Google Places: {e}")
            print(f"[GOOGLE STATIONS ERROR] {e}")

    stations_data = ocm_stations or google_stations
    for station in stations_data:
        connectors = max(1, sum(int(p.get("quantity") or 1) for p in station.get("ports", [])))
        station["queue"] = simulated_queue(station["id"], connectors)
        station["estimated_wait_min"] = simulated_wait_minutes(station["id"], station["queue"], connectors)
        if not station.get("usage_cost") or str(station.get("usage_cost")).strip().lower() in {"not reported", "pricing not reported"}:
            station["usage_cost"] = pricing_for_station(station, 0).get("label")

    if not stations_data and errors:
        raise HTTPException(502, "Charging-station provider error: " + " | ".join(errors))

    return {
        "live": bool(stations_data),
        "stations": stations_data,
        "count": len(stations_data),
        "source": "Open Charge Map" if ocm_stations else ("Google Places" if google_stations else "No provider results"),
        "message": ("; ".join(errors) if errors else None),
    }


@app.post("/api/plan")
def plan(req: PlanIn):
    if req.vehicle_id not in VEHICLES:
        raise HTTPException(400, "Unknown vehicle model")
    if not GOOGLE_MAPS_SERVER_KEY:
        raise HTTPException(503, "GOOGLE_MAPS_SERVER_KEY is not configured")

    vehicle = normalize_vehicle(VEHICLES[req.vehicle_id], req.personal_range_km)
    try:
        source = geocode(req.source)
        destination = geocode(req.destination)
        route = compute_route(source, destination, traffic=True)
    except Exception as e:
        raise HTTPException(502, f"Route provider error: {e}")

    safe_range = usable_range(VEHICLES[req.vehicle_id], req.battery_pct, req.personal_range_km)
    direct = safe_range >= route["distance_km"]

    # Primary route-planner discovery: Google Search Along Route. It uses the
    # actual route polyline and returns routing summaries for the station legs.
    live_stations = []
    google_error = None
    if GOOGLE_MAPS_SERVER_KEY:
        try:
            live_stations = search_ev_stations_along_route(
                route["polyline"],
                source,
                max_results=20,
            )
            live_stations = enrich_google_stations_with_ocm(live_stations, radius_km=2)
            print(f"[GOOGLE ROUTE STATIONS] count={len(live_stations)}")
        except Exception as e:
            google_error = str(e)
            print(f"[GOOGLE ROUTE STATIONS ERROR] {e}")

    # OCM fallback preserves the original provider path if Google Places has
    # no route results or is temporarily unavailable.
    if not live_stations and OPENCHARGEMAP_API_KEY:
        raw_groups = []
        for point in sample_polyline(route["polyline"], 8):
            try:
                raw = fetch_ocm_near(point["lat"], point["lng"], 20, 100)
                raw_groups.append(raw)
                print(
                    f"[OCM ROUTE] {point['lat']:.5f}, {point['lng']:.5f} -> {len(raw)} raw stations"
                )
            except Exception as e:
                print(f"[OCM ROUTE ERROR] {point['lat']}, {point['lng']} -> {e}")
        live_stations = merge_stations(raw_groups)[:50]
        print(f"[OCM ROUTE TOTAL] {len(live_stations)} stations")

    candidates = []

    # Google Search Along Route already provides the two road legs. OCM fallback
    # candidates need a Route Matrix calculation.
    google_candidates = all(
        s.get("source") == "Google Places" and
        s.get("distance_from_source_km") is not None
        for s in live_stations
    ) if live_stations else False

    if google_candidates:
        for station in live_stations:
            to_s_km = station.get("distance_from_source_km")
            from_s_km = station.get("station_to_destination_km")
            if to_s_km is None or from_s_km is None:
                continue

            reachable = to_s_km <= safe_range
            connectors = max(1, sum(int(p.get("quantity") or 1) for p in station.get("ports", [])))
            queue = simulated_queue(station["id"], connectors)
            wait = simulated_wait_minutes(station["id"], queue, connectors)
            energy_used_kwh = to_s_km * vehicle["battery_kwh"] / vehicle["effective_range_km"]
            station_soc = max(0, req.battery_pct - energy_used_kwh / vehicle["battery_kwh"] * 100)
            target_pct = min(90, max(station_soc, from_s_km / vehicle["effective_range_km"] * 100 + vehicle["reserve_pct"]))
            charge = charging_minutes(vehicle, station_soc, target_pct, station.get("max_power_kw") or 50)
            energy_to_charge_kwh = vehicle["battery_kwh"] * max(0, target_pct - station_soc) / 100
            pricing = pricing_for_station(station, energy_to_charge_kwh)
            detour_km = max(0, to_s_km + from_s_km - route["distance_km"])
            drive_overhead = max(0, (station.get("duration_from_source_min") or 0) + (station.get("duration_to_destination_min") or 0) - route["duration_min"])
            extra = round(wait + charge + drive_overhead, 1) if reachable else None

            row = dict(station)
            row.update({
                "distance_from_source_km": round(to_s_km, 2),
                "station_to_destination_km": round(from_s_km, 2),
                "detour_km": round(detour_km, 2),
                "queue": queue,
                "estimated_wait_min": wait,
                "station_soc_pct": round(station_soc, 1),
                "target_soc_pct": round(target_pct, 1),
                "estimated_charge_min": round(charge, 1) if reachable else None,
                "estimated_charge_cost_inr": pricing.get("estimated_cost_inr"),
                "pricing_provider_reported": pricing.get("provider_reported"),
                "usage_cost": pricing.get("label") or station.get("usage_cost") or "Pricing not reported",
                "total_extra_min": extra,
                "reachable": reachable,
                "score": extra if reachable else None,
            })
            candidates.append(row)
    else:
        valid_stations = [
            s for s in live_stations
            if s.get("lat") is not None and s.get("lng") is not None
        ]
        station_points = [
            {"lat": s["lat"], "lng": s["lng"]}
            for s in valid_stations
        ]

        if station_points:
            try:
                source_legs = route_matrix_batch(
                    [{"lat": source["lat"], "lng": source["lng"]}],
                    station_points,
                )
                destination_legs = route_matrix_batch(
                    station_points,
                    [{"lat": destination["lat"], "lng": destination["lng"]}],
                )
            except Exception as e:
                raise HTTPException(502, f"Route Matrix error: {e}")

            source_by_dest = {
                r.get("destination_index"): r
                for r in source_legs
                if r.get("destination_index") is not None
            }
            destination_by_origin = {
                r.get("origin_index"): r
                for r in destination_legs
                if r.get("origin_index") is not None
            }

            for idx, station in enumerate(valid_stations):
                to_s = source_by_dest.get(idx)
                from_s = destination_by_origin.get(idx)
                if not to_s or not from_s or not to_s["ok"] or not from_s["ok"]:
                    continue

                reachable = to_s["distance_km"] <= safe_range
                connectors = max(1, sum(int(p.get("quantity") or 1) for p in station.get("ports", [])))
                queue = simulated_queue(station["id"], connectors)
                wait = simulated_wait_minutes(station["id"], queue, connectors)
                energy_used_kwh = to_s["distance_km"] * vehicle["battery_kwh"] / vehicle["effective_range_km"]
                station_soc = max(0, req.battery_pct - energy_used_kwh / vehicle["battery_kwh"] * 100)
                target_pct = min(90, max(station_soc, from_s["distance_km"] / vehicle["effective_range_km"] * 100 + vehicle["reserve_pct"]))
                charge = charging_minutes(vehicle, station_soc, target_pct, station.get("max_power_kw") or 50)
                energy_to_charge_kwh = vehicle["battery_kwh"] * max(0, target_pct - station_soc) / 100
                pricing = pricing_for_station(station, energy_to_charge_kwh)
                detour_km = max(0, to_s["distance_km"] + from_s["distance_km"] - route["distance_km"])
                drive_overhead = max(0, to_s["duration_min"] + from_s["duration_min"] - route["duration_min"])
                extra = round(wait + charge + drive_overhead, 1) if reachable else None

                row = dict(station)
                row.update({
                    "distance_from_source_km": to_s["distance_km"],
                    "station_to_destination_km": from_s["distance_km"],
                    "detour_km": round(detour_km, 2),
                    "queue": queue,
                    "estimated_wait_min": wait,
                    "station_soc_pct": round(station_soc, 1),
                    "target_soc_pct": round(target_pct, 1),
                    "estimated_charge_min": round(charge, 1) if reachable else None,
                    "estimated_charge_cost_inr": pricing.get("estimated_cost_inr"),
                    "pricing_provider_reported": pricing.get("provider_reported"),
                    "usage_cost": pricing.get("label") or station.get("usage_cost") or "Pricing not reported",
                    "total_extra_min": extra,
                    "reachable": reachable,
                    "score": extra if reachable else None,
                })
                candidates.append(row)

    candidates = rank_charging_candidates(candidates)
    recommendation = candidates[0] if candidates and candidates[0].get("reachable") else None

    if direct:
        decision = "DIRECT"
        message = "The selected EV can reach the destination while retaining the configured safety reserve."
    elif recommendation:
        decision = "CHARGE"
        message = "A provider-reported charging location is reachable; the stop is ranked using real road legs, simulated queue and estimated charging time."
    else:
        decision = "WARNING"
        message = "No reachable charging station was found in the provider data. Increase battery, widen coverage, or verify charger availability."

    result = {
        "decision": decision, "message": message, "vehicle": vehicle,
        "origin": source, "destination": destination, "route": route,
        "distance_km": route["distance_km"], "duration_min": route["duration_min"],
        "available_range_km": round(safe_range, 1), "battery_pct": req.battery_pct,
        "recommended_station": recommendation, "stations": candidates[:20],
        "subscription": req.subscription,
        "queue_note": "Queue count and waiting time are simulated from realistic connector-aware ranges; station metadata/status and provider pricing are used when available, otherwise pricing is clearly labelled as an estimate.",
        "formula": "Google road route + Google Search Along Route + Open Charge Map enrichment/fallback + personalized energy/range model + simulated queue/wait + charging time + multi-factor station cost function",
        "optimization_weights": "35% total extra time, 20% waiting time, 15% charging time, 12% route detour, 10% estimated/provider charging cost, 8% source distance; lower score is better",
        "provider_note": google_error if google_error and not candidates else None,
    }
    add_route({"owner_id": req.owner_id, "source": req.source, "destination": req.destination, "vehicle_id": req.vehicle_id, "distance_km": route["distance_km"], "duration_min": route["duration_min"], "decision": decision})
    return result


@app.get("/api/admin/owners")
def admin_owners(_: bool = Depends(admin_guard)): return list_owners()

@app.get("/api/admin/purchases")
def admin_purchases(_: bool = Depends(admin_guard)): return list_purchases()

@app.get("/api/admin/routes")
def admin_routes(_: bool = Depends(admin_guard)): return list_routes()

@app.delete("/api/admin/owners/{owner_id}")
def admin_delete_owner(owner_id: int, _: bool = Depends(admin_guard)):
    if not delete_owner(owner_id): raise HTTPException(404, "Owner not found")
    return {"deleted": True}

@app.delete("/api/admin/purchases/{purchase_id}")
def admin_delete_purchase(purchase_id: int, _: bool = Depends(admin_guard)):
    if not delete_purchase(purchase_id): raise HTTPException(404, "Purchase not found")
    return {"deleted": True}

@app.delete("/api/admin/all")
def admin_clear_all(_: bool = Depends(admin_guard)):
    clear_all(); return {"deleted": True}

DIST = __import__("pathlib").Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")
    @app.get("/{path:path}")
    def serve_react(path: str):
        p = DIST / path
        if path and p.exists() and p.is_file(): return FileResponse(p)
        return FileResponse(DIST / "index.html")
