import os, json, time, math, hashlib
import requests
from typing import Dict, Any, List, Tuple, Optional

MAPBOX_BASE = "https://api.mapbox.com/directions/v5/mapbox/driving-traffic"
OVERPASS = "https://overpass-api.de/api/interpreter"

_CACHE_DIR = "data/.cache_places"
_CACHE_TTL_SEC = int(os.getenv("PLACES_CACHE_TTL_SEC", "900"))  # 15 min

class PlacesError(Exception): ...

def _ensure_cache_dir():
    os.makedirs(_CACHE_DIR, exist_ok=True)

def _cache_key(**kwargs) -> str:
    raw = json.dumps(kwargs, sort_keys=True)
    h = hashlib.sha1(raw.encode()).hexdigest()[:16]
    return os.path.join(_CACHE_DIR, f"{h}.json")

def _cache_get(key_path: str) -> Optional[Any]:
    _ensure_cache_dir()
    if not os.path.exists(key_path): return None
    if time.time() - os.path.getmtime(key_path) > _CACHE_TTL_SEC: return None
    try:
        with open(key_path, "r") as f:
            return json.load(f)
    except Exception:
        return None

def _cache_set(key_path: str, value: Any):
    _ensure_cache_dir()
    try:
        with open(key_path, "w") as f:
            json.dump(value, f)
    except Exception:
        pass

def _mapbox_route(home: Dict[str, float], office: Dict[str, float]) -> Dict[str, Any]:
    token = os.getenv("MAPBOX_TOKEN")
    if not token: raise PlacesError("missing_mapbox_token")
    coords = f"{home['lon']},{home['lat']};{office['lon']},{office['lat']}"
    params = {
        "alternatives": "false",
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
        "access_token": token
    }
    r = requests.get(f"{MAPBOX_BASE}/{coords}", params=params, timeout=12)
    r.raise_for_status()
    data = r.json()
    routes = data.get("routes", [])
    if not routes: raise PlacesError("no_route")
    return routes[0]

def _sample_points(geojson_coords: List[List[float]], every_km: float = 2.0, max_points: int = 6) -> List[Tuple[float, float]]:
    """Downsample route (lon,lat) pairs ~every_km; cap to max_points. Returns (lat,lon)."""
    out: List[Tuple[float, float]] = []
    if not geojson_coords: return out
    def haversine(lon1, lat1, lon2, lat2):
        R = 6371.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlmb = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dlmb/2)**2
        return 2*R*math.asin(math.sqrt(a))
    acc = 0.0
    last = geojson_coords[0]
    out.append((last[1], last[0]))
    for xy in geojson_coords[1:]:
        d = haversine(last[0], last[1], xy[0], xy[1])
        acc += d
        if acc >= every_km:
            out.append((xy[1], xy[0]))
            acc = 0.0
        last = xy
        if len(out) >= max_points: break
    if out[-1] != (geojson_coords[-1][1], geojson_coords[-1][0]):
        out[-1] = (geojson_coords[-1][1], geojson_coords[-1][0])
    return out

# ------- OSM category mapping (free) -------
_OSM_FILTERS = {
    "coffee": [
        'amenity="cafe"', 'amenity="coffee_shop"', 'shop="coffee"'
    ],
    "florist": [
        'shop="florist"'
    ],
    "gift shop": [
        'shop="gift"', 'shop="variety_store"'
    ],
    "bakery": [
        'shop="bakery"', 'amenity="bakery"'
    ]
}

def _overpass_query(lat: float, lon: float, radius_m: int, filters: List[str]) -> str:
    around = f'(around:{radius_m},{lat},{lon})'
    # Search nodes + ways (with center) for each filter
    parts = []
    for f in filters:
        parts.append(f'node[{f}]{around};')
        parts.append(f'way[{f}]{around};')
    body = "".join(parts)
    return f'[out:json][timeout:25];({body});out center 20;'

def _osm_search(lat: float, lon: float, category: str, radius_m: int = 800) -> List[Dict[str, Any]]:
    filters = _OSM_FILTERS.get(category.lower())
    if not filters:
        # fallback: treat as text search on name (coarse)
        filters = [f'name~"{category}",i']
    q = _overpass_query(lat, lon, radius_m, filters)
    r = requests.post(OVERPASS, data={"data": q}, timeout=25)
    r.raise_for_status()
    data = r.json()
    out = []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name: continue
        phone = tags.get("contact:phone") or tags.get("phone")
        lat_c = el.get("lat") or (el.get("center") or {}).get("lat")
        lon_c = el.get("lon") or (el.get("center") or {}).get("lon")
        out.append({
            "id": f"{el.get('type')}/{el.get('id')}",
            "name": name,
            "phone": phone,
            "address": ", ".join([t for t in [
                tags.get("addr:housenumber"),
                tags.get("addr:street"),
                tags.get("addr:city")
            ] if t]),
            "lat": lat_c,
            "lon": lon_c,
            "url": tags.get("website") or tags.get("contact:website"),
            "tags": tags
        })
    return out

def _detour_minutes(home: Dict[str, float], office: Dict[str, float], place: Dict[str, float]) -> int:
    token = os.getenv("MAPBOX_TOKEN")
    if not token: raise PlacesError("missing_mapbox_token")
    coords_direct = f"{home['lon']},{home['lat']};{office['lon']},{office['lat']}"
    coords_leg1   = f"{home['lon']},{home['lat']};{place['lon']},{place['lat']}"
    coords_leg2   = f"{place['lon']},{place['lat']};{office['lon']},{office['lat']}"
    p = {"access_token": token, "overview": "false", "steps": "false"}
    d = requests.get(f"{MAPBOX_BASE}/{coords_direct}", params=p, timeout=10).json()
    l1= requests.get(f"{MAPBOX_BASE}/{coords_leg1}",   params=p, timeout=10).json()
    l2= requests.get(f"{MAPBOX_BASE}/{coords_leg2}",   params=p, timeout=10).json()
    t_direct = (d.get("routes",[{}])[0].get("duration") or 0)/60
    t_with   = ((l1.get("routes",[{}])[0].get("duration") or 0) + (l2.get("routes",[{}])[0].get("duration") or 0))/60
    return max(0, round(t_with - t_direct))

def search_along_route(category: str, home: Dict[str, float], office: Dict[str, float]) -> List[Dict[str, Any]]:
    """Return top places along route ranked by minimal detour. Free sources only."""
    if not category.strip():
        raise PlacesError("empty_category")
    route = _mapbox_route(home, office)
    coords = route.get("geometry", {}).get("coordinates", [])
    samples = _sample_points(coords, every_km=2.0, max_points=6)

    cache_k = _cache_key(category=category, home=home, office=office, samples=samples)
    cached = _cache_get(cache_k)
    if cached is not None:
        return cached

    # Gather candidates near each sampled point
    raw: Dict[str, Dict[str, Any]] = {}
    for (lat, lon) in samples:
        try:
            found = _osm_search(lat, lon, category, radius_m=800)
            for p in found:
                if not p.get("id"): continue
                raw[p["id"]] = p
        except Exception:
            continue

    # Take up to 6 for detour calc
    candidates = list(raw.values())[:6]
    results: List[Dict[str, Any]] = []
    for p in candidates:
        if p.get("lat") is None or p.get("lon") is None: continue
        detour = _detour_minutes(home, office, {"lat": p["lat"], "lon": p["lon"]})
        results.append({
            "name": p["name"],
            "phone": p.get("phone"),
            "address": p.get("address"),
            "detour_min": detour,
            "url": p.get("url"),
            "map_url": f"https://www.google.com/maps/search/?api=1&query={p['lat']},{p['lon']}"
        })

    results.sort(key=lambda x: (x["detour_min"], x.get("name","")))
    final = results[:3]
    _cache_set(cache_k, final)
    return final