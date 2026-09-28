import hashlib, math, time, random, re
import requests
from .config import GOOGLE_MAPS_SERVER_KEY as GOOGLE_SERVER_KEY, OPENCHARGEMAP_API_KEY as OCM_KEY, GOOGLE_REGION_CODE

def parse_duration_seconds(value):
    if isinstance(value,(int,float)): return float(value)
    if not value: return 0.0
    try: return float(str(value).rstrip("s"))
    except Exception: return 0.0

def geocode(address):
    if not GOOGLE_SERVER_KEY:
        raise RuntimeError("GOOGLE_MAPS_SERVER_KEY is not configured")
    r=requests.get("https://maps.googleapis.com/maps/api/geocode/json",
                   params={"address":address,"key":GOOGLE_SERVER_KEY},timeout=15)
    r.raise_for_status()
    data=r.json()
    if data.get("status")!="OK" or not data.get("results"):
        raise ValueError(f"Could not locate '{address}'.")
    first=data["results"][0]
    loc=first["geometry"]["location"]
    return {"lat":loc["lat"],"lng":loc["lng"],"formatted":first.get("formatted_address",address)}

def _google_latlng(point):
    """
    Convert our internal {lat, lng} representation
    into the Google Routes API {latitude, longitude} format.
    """
    if not point:
        raise ValueError("Missing geographic point")

    return {
        "latitude": float(point["lat"]),
        "longitude": float(point["lng"]),
    }


def compute_route(origin, destination, intermediates=None, traffic=False):
    if not GOOGLE_SERVER_KEY:
        raise RuntimeError("GOOGLE_MAPS_SERVER_KEY is not configured")

    body = {
        "origin": {
            "location": {
                "latLng": _google_latlng(origin)
            }
        },
        "destination": {
            "location": {
                "latLng": _google_latlng(destination)
            }
        },
        "travelMode": "DRIVE",
        "routingPreference": (
            "TRAFFIC_AWARE"
            if traffic
            else "TRAFFIC_UNAWARE"
        ),
        "computeAlternativeRoutes": False,
        "units": "METRIC",
    }

    if intermediates:
        body["intermediates"] = [
            {
                "location": {
                    "latLng": _google_latlng(point)
                }
            }
            for point in intermediates
        ]

    response = requests.post(
        "https://routes.googleapis.com/directions/v2:computeRoutes",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": GOOGLE_SERVER_KEY,
            "X-Goog-FieldMask": (
                "routes.distanceMeters,"
                "routes.duration,"
                "routes.staticDuration,"
                "routes.polyline.encodedPolyline,"
                "routes.legs.distanceMeters,"
                "routes.legs.duration"
            ),
        },
        json=body,
        timeout=20,
    )

    if not response.ok:
        # Keep Google's actual error available during development.
        try:
            google_error = response.json()
        except Exception:
            google_error = response.text

        raise RuntimeError(
            f"Google Routes API error "
            f"(HTTP {response.status_code}): {google_error}"
        )

    data = response.json()

    routes = data.get("routes") or []

    if not routes:
        raise ValueError("Google Routes returned no route.")

    route = routes[0]

    return {
        "distance_km": round(
            route.get("distanceMeters", 0) / 1000,
            2
        ),
        "duration_min": round(
            parse_duration_seconds(
                route.get("duration")
            ) / 60,
            1
        ),
        "static_duration_min": round(
            parse_duration_seconds(
                route.get("staticDuration")
            ) / 60,
            1
        ),
        "polyline": (
            route.get("polyline") or {}
        ).get("encodedPolyline", ""),
    }

def route_matrix(points):
    """One-to-one route matrix helper kept for compatibility."""
    if not GOOGLE_SERVER_KEY or not points:
        return []
    results=[]
    for origin, destination in points:
        results.extend(route_matrix_batch([origin], [destination]))
    return results

def route_matrix_batch(origins, destinations):
    """Compute many origin→destination road legs in one Google Routes Matrix call."""
    if not GOOGLE_SERVER_KEY or not origins or not destinations:
        return []
    payload = {
        "origins": [
            {
                "waypoint": {
                    "location": {
                        "latLng": _google_latlng(point)
                    }
                }
            }
            for point in origins
        ],
        "destinations": [
            {
                "waypoint": {
                    "location": {
                        "latLng": _google_latlng(point)
                    }
                }
            }
            for point in destinations
        ],
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
    }
    r=requests.post(
        "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix",
        headers={"Content-Type":"application/json","X-Goog-Api-Key":GOOGLE_SERVER_KEY,
                 "X-Goog-FieldMask":"originIndex,destinationIndex,status,condition,distanceMeters,duration"},
        json=payload,timeout=30,
    )
    r.raise_for_status()
    rows=[]
    for line in r.iter_lines(decode_unicode=True):
        if not line:
            continue
        try:
            x=__import__("json").loads(line)
        except Exception:
            continue
        rows.append({
            "origin_index":x.get("originIndex"),
            "destination_index":x.get("destinationIndex"),
            "distance_km":round(x.get("distanceMeters",0)/1000,2) if x.get("distanceMeters") is not None else None,
            "duration_min":round(parse_duration_seconds(x.get("duration"))/60,1) if x.get("duration") else None,
            "ok":x.get("condition")=="ROUTE_EXISTS" or x.get("status") in (None,"OK"),
        })
    return rows

def decode_polyline(poly):
    coords=[]; index=0; lat=lng=0
    while index<len(poly):
        result=shift=0
        while True:
            b=ord(poly[index])-63; index+=1
            result |= (b&31)<<shift; shift+=5
            if b<32: break
        lat += ~(result>>1) if result&1 else result>>1
        result=shift=0
        while True:
            b=ord(poly[index])-63; index+=1
            result |= (b&31)<<shift; shift+=5
            if b<32: break
        lng += ~(result>>1) if result&1 else result>>1
        coords.append((lat/1e5,lng/1e5))
    return coords

def sample_polyline(poly, n=5):
    pts=decode_polyline(poly) if poly else []
    if not pts: return []
    if len(pts)<=n: return [{"lat":a,"lng":b} for a,b in pts]
    idxs=[round(i*(len(pts)-1)/(n-1)) for i in range(n)]
    return [{"lat":pts[i][0],"lng":pts[i][1]} for i in idxs]

def stable_int(key, low, high):
    h=hashlib.sha256(key.encode()).hexdigest()
    return low + int(h[:8],16)%(high-low+1)

def simulated_queue(station_id, connectors):
    """Generate a realistic-looking simulated queue for the prototype UI.

    The queue is deliberately simulated because neither Google Places nor
    Open Charge Map reliably exposes a live waiting queue.  It changes on
    each planning/search request while staying within plausible bounds for
    the number of connectors.
    """
    connectors=max(1,int(connectors or 1))
    rng=random.SystemRandom()
    # Most sites are lightly/moderately busy; larger sites can have more cars.
    max_queue=max(2,min(18,connectors*3+4))
    queue=rng.choices(
        population=list(range(max_queue+1)),
        weights=[max_queue+1-i for i in range(max_queue+1)],
        k=1,
    )[0]
    return int(queue)

def simulated_wait_minutes(station_id, queue, connectors=1):
    """Generate realistic simulated waiting time from queue size and capacity."""
    rng=random.SystemRandom()
    connectors=max(1,int(connectors or 1))
    queue=max(0,int(queue or 0))
    if queue == 0:
        return round(rng.uniform(0,4),1)
    # More connectors generally reduce the effective wait per queued vehicle.
    per_vehicle=rng.uniform(4.5,8.5) * max(0.65, min(1.0, 2.0/connectors))
    variability=rng.uniform(0,5.0)
    return round(queue*per_vehicle + variability,1)

def estimate_tariff_inr_per_kwh(station, charger_kw=None):
    """Return a clearly labelled prototype tariff when provider tariff is absent."""
    text=' '.join(str(station.get(k) or '') for k in ('operator','usage','usage_cost','name')).lower()
    if 'free' in text:
        return 0.0
    power=float(charger_kw or station.get('max_power_kw') or 50)
    # A simple India-focused prototype tariff model. Provider-reported pricing
    # is preferred; this is only a fallback estimate when it is missing.
    if power >= 120:
        return 24.0
    if power >= 60:
        return 20.0
    if power >= 30:
        return 18.0
    return 15.0

def price_level_score(station):
    level=station.get('google_price_level')
    mapping={
        'PRICE_LEVEL_FREE':0.0,
        'PRICE_LEVEL_INEXPENSIVE':1.0,
        'PRICE_LEVEL_MODERATE':2.0,
        'PRICE_LEVEL_EXPENSIVE':3.0,
        'PRICE_LEVEL_VERY_EXPENSIVE':4.0,
    }
    if level in mapping:
        return mapping[level]
    return None

def pricing_for_station(station, energy_kwh):
    """Resolve provider pricing first, then give a clearly-labelled estimate."""
    provider=station.get('usage_cost')
    if provider and str(provider).strip() and str(provider).strip().lower() not in {'not reported','pricing not reported'}:
        provider_text=str(provider).strip()
        if provider_text.lower() == 'free':
            provider_tariff=0.0
        else:
            match=re.search(r'(\d+(?:\.\d+)?)', provider_text.replace(',', ''))
            provider_tariff=float(match.group(1)) if match else None
        provider_cost=round(max(0,float(energy_kwh or 0))*provider_tariff,2) if provider_tariff is not None else None
        return {
            'label': provider_text if provider_cost is None or float(energy_kwh or 0) <= 0 else f'{provider_text} · ~₹{provider_cost:.0f}',
            'provider_reported': True,
            'tariff_inr_per_kwh': provider_tariff,
            'estimated_cost_inr': provider_cost,
        }
    tariff=estimate_tariff_inr_per_kwh(station)
    cost=round(max(0,float(energy_kwh or 0))*tariff,2)
    return {
        'label': (f'Estimated ₹{tariff:.0f}/kWh' if float(energy_kwh or 0) <= 0 else f'Estimated ₹{tariff:.0f}/kWh · ~₹{cost:.0f}'),
        'provider_reported': False,
        'tariff_inr_per_kwh': tariff,
        'estimated_cost_inr': cost,
    }

def rank_charging_candidates(candidates):
    """Rank reachable stations using a multi-factor cost function.

    Lower is better.  Time/queue/charging matter most, with route deviation,
    charging cost and access distance also contributing.  This prevents the
    first/nearest provider result from automatically becoming the recommendation.
    """
    reachable=[c for c in candidates if c.get('reachable')]
    if not reachable:
        for c in candidates:
            c['optimization_score']=None
            c['score']=None
        return sorted(candidates,key=lambda x: float('inf'))

    def values(key, fallback=0.0):
        return [float(c.get(key) or fallback) for c in reachable]

    def norm(value, vals):
        lo=min(vals); hi=max(vals)
        return 0.0 if hi==lo else (float(value)-lo)/(hi-lo)

    extra_vals=values('total_extra_min')
    wait_vals=values('estimated_wait_min')
    charge_vals=values('estimated_charge_min')
    detour_vals=values('detour_km')
    distance_vals=values('distance_from_source_km')
    price_vals=values('estimated_cost_inr')

    for c in reachable:
        components={
            'extra':norm(c.get('total_extra_min'),extra_vals),
            'wait':norm(c.get('estimated_wait_min'),wait_vals),
            'charge':norm(c.get('estimated_charge_min'),charge_vals),
            'detour':norm(c.get('detour_km'),detour_vals),
            'distance':norm(c.get('distance_from_source_km'),distance_vals),
            'price':norm(c.get('estimated_cost_inr'),price_vals),
        }
        score=(
            0.35*components['extra'] +
            0.20*components['wait'] +
            0.15*components['charge'] +
            0.12*components['detour'] +
            0.10*components['price'] +
            0.08*components['distance']
        )*100
        c['optimization_score']=round(score,1)
        c['score']=score

    unreachable=[c for c in candidates if not c.get('reachable')]
    for c in unreachable:
        c['optimization_score']=None
        c['score']=None
    return sorted(reachable,key=lambda x:x['score']) + sorted(unreachable,key=lambda x:(x.get('distance_from_source_km') or float('inf')))

def normalize_vehicle(vehicle, personal_range_km=None):
    official=vehicle["reference_range_km"]
    if personal_range_km:
        blended=0.60*official+0.40*personal_range_km
        source="60% manufacturer/official reference + 40% owner estimate"
    else:
        blended=official
        source="manufacturer/official reference only"
    out=dict(vehicle)
    out["effective_range_km"]=round(blended,1)
    out["effective_km_per_kwh"]=round(blended/vehicle["battery_kwh"],3)
    out["effective_kwh_per_100km"]=round(vehicle["battery_kwh"]/blended*100,2)
    out["range_blend_source"]=source
    return out

def usable_range(vehicle, battery_pct, personal_range_km=None):
    v=normalize_vehicle(vehicle,personal_range_km)
    return max(0,(battery_pct-v["reserve_pct"])/100*v["effective_range_km"])

def charging_minutes(vehicle, start_pct, target_pct, charger_kw):
    if target_pct<=start_pct: return 0
    target=min(target_pct,90)
    energy=vehicle["battery_kwh"]*(target-start_pct)/100
    power=max(1,min(charger_kw,vehicle["dc_kw"]))
    # Simple taper approximation after 70%; real BMS curves vary by vehicle.
    taper=1.0+max(0,target-70)*0.012
    return energy/power*60*1.12*taper

def fetch_ocm_near(lat,lng,distance_km=25,maxresults=30):
    if not OCM_KEY: return []
    params={"output":"json","latitude":lat,"longitude":lng,"distance":distance_km,
            "distanceunit":"KM","maxresults":maxresults,"compact":"false","verbose":"true",
            "key":OCM_KEY}
    r=requests.get(
        "https://api.openchargemap.io/v3/poi/",
        params=params,
        headers={
            "User-Agent": "EVChargeRoute/3.0 academic prototype",
            "X-API-Key": OCM_KEY,
        },
        timeout=20,
    )
    r.raise_for_status()
    return r.json()

def parse_ocm(raw):
    out=[]
    for x in raw:
        addr=x.get("AddressInfo") or {}
        op=x.get("OperatorInfo") or {}
        status=x.get("StatusType") or {}
        usage=x.get("UsageType") or {}
        connections=x.get("Connections") or []
        ports=[]
        max_power=0
        for c in connections:
            ctype=(c.get("ConnectionType") or {})
            name=ctype.get("Title") or ctype.get("FormalName") or "Unknown"
            power=c.get("PowerKW")
            if power: max_power=max(max_power,float(power))
            ports.append({"type":name,"power_kw":power,"quantity":c.get("Quantity"),"level":(c.get("Level") or {}).get("Title") if isinstance(c.get("Level"),dict) else None})
        out.append({
            "id":str(x.get("ID")),
            "name":addr.get("Title") or "Unnamed charging site",
            "lat":addr.get("Latitude"),"lng":addr.get("Longitude"),
            "address":", ".join([v for v in [addr.get("AddressLine1"),addr.get("Town"),addr.get("StateOrProvince"),addr.get("Postcode")] if v]),
            "operator":op.get("Title") or "Not reported",
            "status":status.get("Title") or "Not reported",
            "status_is_operational":status.get("IsOperational"),
            "usage":usage.get("Title") or "Not reported",
            "usage_cost":usage.get("UsageCost"),
            "ports":ports,
            "max_power_kw":round(max_power,1) if max_power else None,
            "source":"Open Charge Map",
            "ocm_url":f"https://openchargemap.org/site/poi/details/{x.get('ID')}",
        })
    return out

def merge_stations(groups):
    seen={}
    for group in groups:
        for s in parse_ocm(group):
            key=s["id"] or f"{s['lat']},{s['lng']}"
            if key not in seen: seen[key]=s
    return list(seen.values())


def _parse_google_duration(value):
    return parse_duration_seconds(value)


def search_ev_stations_along_route(polyline, origin, max_results=20):
    """Find EV charging stations along the calculated Google route.

    Uses Places API (New) Text Search + Search Along Route and requests
    routing summaries so each candidate includes the road leg from the
    route origin and onward to the route destination.
    """
    if not GOOGLE_SERVER_KEY:
        raise RuntimeError("GOOGLE_MAPS_SERVER_KEY is not configured")
    if not polyline:
        return []

    body = {
        "textQuery": "EV charging station",
        "pageSize": max(1, min(int(max_results), 20)),
        "includedType": "electric_vehicle_charging_station",
        "strictTypeFiltering": True,
        "searchAlongRouteParameters": {
            "polyline": {"encodedPolyline": polyline}
        },
        "routingParameters": {
            "origin": {
                "latitude": float(origin["lat"]),
                "longitude": float(origin["lng"]),
            },
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE",
        },
    }

    field_mask = (
        "places.id,"
        "places.displayName,"
        "places.formattedAddress,"
        "places.location,"
        "places.businessStatus,"
        "places.evChargeOptions,"
        "places.priceLevel,"
        "routingSummaries"
    )

    r = requests.post(
        "https://places.googleapis.com/v1/places:searchText",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": GOOGLE_SERVER_KEY,
            "X-Goog-FieldMask": field_mask,
        },
        json=body,
        timeout=20,
    )

    if not r.ok:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise RuntimeError(
            f"Google Places Search Along Route error "
            f"(HTTP {r.status_code}): {detail}"
        )

    data = r.json()
    places = data.get("places") or []
    summaries = data.get("routingSummaries") or []
    results = []

    for idx, place in enumerate(places):
        loc = place.get("location") or {}
        if loc.get("latitude") is None or loc.get("longitude") is None:
            continue

        ev = place.get("evChargeOptions") or {}
        ports = []
        max_power = 0.0
        for item in ev.get("connectorAggregation") or []:
            rate = item.get("maxChargeRateKw")
            if rate is not None:
                max_power = max(max_power, float(rate))
            ports.append({
                "type": item.get("type", "Not reported"),
                "power_kw": rate,
                "quantity": item.get("count"),
                "available_count": item.get("availableCount"),
                "out_of_service_count": item.get("outOfServiceCount"),
            })

        summary = summaries[idx] if idx < len(summaries) else {}
        legs = summary.get("legs") or []
        first_leg = legs[0] if legs else {}
        last_leg = legs[-1] if legs else {}

        results.append({
            "id": f"google:{place.get('id', idx)}",
            "google_place_id": place.get("id"),
            "name": (place.get("displayName") or {}).get("text") or "EV charging station",
            "lat": loc.get("latitude"),
            "lng": loc.get("longitude"),
            "address": place.get("formattedAddress") or "Address not reported",
            "operator": "Google Maps place",
            "status": place.get("businessStatus") or "Not reported",
            "status_is_operational": (
                place.get("businessStatus") == "OPERATIONAL"
                if place.get("businessStatus")
                else None
            ),
            "usage": "Google Places",
            "usage_cost": (
                {
                    "PRICE_LEVEL_FREE": "Free",
                    "PRICE_LEVEL_INEXPENSIVE": "Inexpensive",
                    "PRICE_LEVEL_MODERATE": "Moderate",
                    "PRICE_LEVEL_EXPENSIVE": "Expensive",
                    "PRICE_LEVEL_VERY_EXPENSIVE": "Very expensive",
                }.get(place.get("priceLevel"), "Pricing not reported")
            ),
            "ports": ports,
            "max_power_kw": round(max_power, 1) if max_power else None,
            "source": "Google Places",
            "ocm_url": None,
            "google_maps_url": (
                f"https://www.google.com/maps/search/?api=1&query="
                f"{loc.get('latitude')},{loc.get('longitude')}"
                f"&query_place_id={place.get('id')}"
                if place.get("id") else None
            ),
            "distance_from_source_km": (
                round(first_leg.get("distanceMeters", 0) / 1000, 2)
                if first_leg.get("distanceMeters") is not None else None
            ),
            "duration_from_source_min": (
                round(_parse_google_duration(first_leg.get("duration")) / 60, 1)
                if first_leg.get("duration") else None
            ),
            "station_to_destination_km": (
                round(last_leg.get("distanceMeters", 0) / 1000, 2)
                if last_leg.get("distanceMeters") is not None else None
            ),
            "duration_to_destination_min": (
                round(_parse_google_duration(last_leg.get("duration")) / 60, 1)
                if last_leg.get("duration") else None
            ),
            "google_price_level": place.get("priceLevel"),
        })

    return results


def search_ev_stations_nearby_google(lat, lng, max_results=20):
    """Google Places fallback for the Stations tab when OCM has no records."""
    if not GOOGLE_SERVER_KEY:
        return []

    body = {
        "textQuery": "EV charging station",
        "pageSize": max(1, min(int(max_results), 20)),
        "includedType": "electric_vehicle_charging_station",
        "strictTypeFiltering": True,
        "locationBias": {
            "circle": {
                "center": {"latitude": float(lat), "longitude": float(lng)},
                "radius": 30000,
            }
        },
    }
    field_mask = (
        "places.id,places.displayName,places.formattedAddress,places.location,"
        "places.businessStatus,places.evChargeOptions,places.priceLevel"
    )
    r = requests.post(
        "https://places.googleapis.com/v1/places:searchText",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": GOOGLE_SERVER_KEY,
            "X-Goog-FieldMask": field_mask,
        },
        json=body,
        timeout=20,
    )
    if not r.ok:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise RuntimeError(
            f"Google Places nearby search error "
            f"(HTTP {r.status_code}): {detail}"
        )

    results = []
    for idx, place in enumerate((r.json().get("places") or [])):
        loc = place.get("location") or {}
        if loc.get("latitude") is None or loc.get("longitude") is None:
            continue
        ev = place.get("evChargeOptions") or {}
        ports = []
        max_power = 0.0
        for item in ev.get("connectorAggregation") or []:
            rate = item.get("maxChargeRateKw")
            if rate is not None:
                max_power = max(max_power, float(rate))
            ports.append({
                "type": item.get("type", "Not reported"),
                "power_kw": rate,
                "quantity": item.get("count"),
                "available_count": item.get("availableCount"),
                "out_of_service_count": item.get("outOfServiceCount"),
            })
        results.append({
            "id": f"google:{place.get('id', idx)}",
            "google_place_id": place.get("id"),
            "name": (place.get("displayName") or {}).get("text") or "EV charging station",
            "lat": loc.get("latitude"),
            "lng": loc.get("longitude"),
            "address": place.get("formattedAddress") or "Address not reported",
            "operator": "Google Maps place",
            "status": place.get("businessStatus") or "Not reported",
            "status_is_operational": (
                place.get("businessStatus") == "OPERATIONAL"
                if place.get("businessStatus") else None
            ),
            "usage": "Google Places",
            "usage_cost": (
                {
                    "PRICE_LEVEL_FREE": "Free",
                    "PRICE_LEVEL_INEXPENSIVE": "Inexpensive",
                    "PRICE_LEVEL_MODERATE": "Moderate",
                    "PRICE_LEVEL_EXPENSIVE": "Expensive",
                    "PRICE_LEVEL_VERY_EXPENSIVE": "Very expensive",
                }.get(place.get("priceLevel"), "Pricing not reported")
            ),
            "ports": ports,
            "max_power_kw": round(max_power, 1) if max_power else None,
            "source": "Google Places",
            "ocm_url": None,
            "google_maps_url": (
                f"https://www.google.com/maps/search/?api=1&query="
                f"{loc.get('latitude')},{loc.get('longitude')}"
                f"&query_place_id={place.get('id')}"
                if place.get("id") else None
            ),
            "google_price_level": place.get("priceLevel"),
        })
    return results


def enrich_google_stations_with_ocm(stations, radius_km=2):
    """Add OCM operator/status/pricing/connector metadata when a nearby OCM POI matches."""
    if not OCM_KEY or not stations:
        return stations

    enriched = []
    for station in stations:
        try:
            raw = fetch_ocm_near(
                station["lat"], station["lng"], radius_km, 10
            )
            nearby = merge_stations([raw])
            if nearby:
                nearest = min(
                    nearby,
                    key=lambda x: (
                        (float(x.get("lat") or 0) - float(station["lat"])) ** 2
                        + (float(x.get("lng") or 0) - float(station["lng"])) ** 2
                    )
                )
                if nearest.get("name"):
                    station["name"] = nearest["name"]
                station["operator"] = nearest.get("operator") or station["operator"]
                station["status"] = nearest.get("status") or station["status"]
                station["status_is_operational"] = nearest.get("status_is_operational")
                station["usage"] = nearest.get("usage") or station["usage"]
                station["usage_cost"] = nearest.get("usage_cost") or station["usage_cost"]
                if nearest.get("ports"):
                    station["ports"] = nearest["ports"]
                station["max_power_kw"] = nearest.get("max_power_kw") or station["max_power_kw"]
                station["ocm_url"] = nearest.get("ocm_url")
        except Exception:
            # Google station discovery must still work if OCM enrichment is unavailable.
            pass
        enriched.append(station)
    return enriched

def autocomplete_places(text):
    if not GOOGLE_SERVER_KEY:
        raise RuntimeError("GOOGLE_MAPS_SERVER_KEY is not configured")
    body = {"input": text}
    if GOOGLE_REGION_CODE:
        body["regionCode"] = GOOGLE_REGION_CODE
    r = requests.post(
        "https://places.googleapis.com/v1/places:autocomplete",
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": GOOGLE_SERVER_KEY},
        json=body, timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    suggestions = []
    for item in data.get("suggestions", []):
        pred = item.get("placePrediction") or {}
        text_obj = pred.get("text") or {}
        structured = pred.get("structuredFormat") or {}
        suggestions.append({
            "place_id": pred.get("placeId"),
            "text": text_obj.get("text", ""),
            "main_text": (structured.get("mainText") or {}).get("text", text_obj.get("text", "")),
            "secondary_text": (structured.get("secondaryText") or {}).get("text", ""),
        })
    return suggestions


def place_details(place_id):
    if not GOOGLE_SERVER_KEY:
        raise RuntimeError("GOOGLE_MAPS_SERVER_KEY is not configured")
    r = requests.get(
        f"https://places.googleapis.com/v1/places/{place_id}",
        headers={"X-Goog-Api-Key": GOOGLE_SERVER_KEY, "X-Goog-FieldMask": "id,displayName,formattedAddress,location"},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    loc = data.get("location") or {}
    return {
        "place_id": data.get("id", place_id),
        "formatted": data.get("formattedAddress") or (data.get("displayName") or {}).get("text", ""),
        "lat": loc.get("latitude"),
        "lng": loc.get("longitude"),
    }
