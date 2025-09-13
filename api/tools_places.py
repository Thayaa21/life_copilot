import os, json, time, math, hashlib
import requests
from typing import Dict, Any, List, Tuple, Optional

MAPBOX_BASE = "https://api.mapbox.com/directions/v5/mapbox/driving-traffic"
YELP_BASE   = "https://api.yelp.com/v3/businesses/search"

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
    return routes[0]  # primary

def _sample_points(geojson_coords: List[List[float]], every_km: float = 2.0, max_points: int = 6) -> List[Tuple[float, float]]:
    """Downsample route (lon,lat) pairs ~every_km; cap to max_points."""
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

def _yelp_search(lat: float, lon: float, term: str, radius_m: int = 800, limit: int = 5) -> List[Dict[str, Any]]:
    key = os.getenv("YELP_API_KEY")
    if not key: raise PlacesError("missing_yelp_key")
    headers = {"Authorization": f"Bearer {key}"}
    params = {
        "term": term,
        "latitude": lat,
        "longitude": lon,
        "radius": radius_m,
        "limit": limit,
        "open_now": False,  # we’ll show open status if present
        "sort_by": "best_match"
    }
    r = requests.get(YELP_BASE, headers=headers, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    out = []
    for b in data.get("businesses", []):
        out.append({
            "id": b.get("id"),
            "name": b.get("name"),
            "phone": b.get("display_phone") or b.get("phone"),
            "address": ", ".join(b.get("location", {}).get("display_address", [])),
            "lat": b.get("coordinates", {}).get("latitude"),
            "lon": b.get("coordinates", {}).get("longitude"),
            "url": b.get("url"),
            "rating": b.get("rating"),
            "review_count": b.get("review_count"),
            "is_closed": b.get("is_closed", False)
        })
    return out

def _detour_minutes(home: Dict[str, float], office: Dict[str, float], place: Dict[str, float]) -> int:
    token = os.getenv("MAPBOX_TOKEN")
    coords_direct = f"{home['lon']},{home['lat']};{office['lon']},{office['lat']}"
    coords_leg1   = f"{home['lon']},{home['lat']};{place['lon']},{place['lat']}"
    coords_leg2   = f"{place['lon']},{place['lat']};{office['lon']},{office['lat']}"
    p = {"access_token": token, "overview": "false", "steps": "false"}
    d = requests.get(f"{MAPBOX_BASE}/{coords_direct}", params=p, timeout=10).json()
    l1= requests.get(f"{MAPBOX_BASE}/{coords_leg1}",   params=p, timeout=10).json()
    l2= requests.get(f"{MAPBOX_BASE}/{coords_leg2}",   params=p, timeout=10).json()
    t_direct = (d.get("routes",[{}])[0].get("duration") or 0)/60
    t_with   = ((l1.get("routes",[{}])[0].get("duration") or 0) + (l2.get("routes",[{}])[0].get("duration") or 0))/60
    detour = max(0, round(t_with - t_direct))
    return detour

def search_along_route(category: str, home: Dict[str, float], office: Dict[str, float]) -> List[Dict[str, Any]]:
    """Return top places along route ranked by minimal detour."""
    if category.strip() == "": raise PlacesError("empty_category")
    route = _mapbox_route(home, office)
    coords = route.get("geometry", {}).get("coordinates", [])
    samples = _sample_points(coords, every_km=2.0, max_points=6)

    cache_k = _cache_key(category=category, home=home, office=office, samples=samples)
    cached = _cache_get(cache_k)
    if cached is not None:
        return cached

    # collect candidates near samples
    raw_candidates: Dict[str, Dict[str, Any]] = {}
    for (lat, lon) in samples:
        try:
            found = _yelp_search(lat, lon, term=category, radius_m=800, limit=5)
            for p in found:
                if not p.get("id"): continue
                raw_candidates[p["id"]] = p
        except Exception:
            continue

    # take up to 6 to compute detour
    candidates = list(raw_candidates.values())[:6]
    results: List[Dict[str, Any]] = []
    for p in candidates:
        if p.get("lat") is None or p.get("lon") is None: continue
        detour = _detour_minutes(home, office, {"lat": p["lat"], "lon": p["lon"]})
        results.append({
            "name": p["name"],
            "phone": p.get("phone"),
            "address": p.get("address"),
            "rating": p.get("rating"),
            "review_count": p.get("review_count"),
            "detour_min": detour,
            "is_open": not p.get("is_closed", False),
            "url": p.get("url"),
            "map_url": f"https://www.google.com/maps/search/?api=1&query={p['lat']},{p['lon']}"
        })

    results.sort(key=lambda x: (x["detour_min"], -(x.get("rating") or 0)))
    final = results[:3]
    _cache_set(cache_k, final)
    return final