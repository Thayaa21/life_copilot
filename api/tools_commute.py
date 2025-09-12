import os
import time
import requests
import datetime as dt
from typing import Dict, Any, Tuple, List

MAPBOX_BASE = "https://api.mapbox.com/directions/v5/mapbox/driving-traffic"

class CommuteError(Exception):
    pass

def _fmt_hhmm(t: dt.datetime) -> str:
    return t.strftime("%H:%M")

def _today_at(hhmm: str, tz: dt.tzinfo | None = None) -> dt.datetime:
    now = dt.datetime.now(tz)
    h, m = map(int, hhmm.split(":"))
    return now.replace(hour=h, minute=m, second=0, microsecond=0)

def _pick_routes(json_: Dict[str, Any]) -> List[Dict[str, Any]]:
    routes = json_.get("routes", []) or []
    # Already sorted by Mapbox (best first), but sort defensively
    routes = sorted(routes, key=lambda r: r.get("duration", 9e9))
    return routes[:3]

def get_commute(home: Dict[str, float],
                office: Dict[str, float],
                arrive_by_hhmm: str,
                buffer_minutes: int,
                reroute_threshold_min: int = 8) -> Tuple[Dict[str, Any], int]:
    """
    Calls Mapbox 'driving-traffic' with alternatives, computes ETA and leave-by,
    and recommends reroute if an alternate saves >= reroute_threshold_min minutes.
    Returns (payload, latency_ms).
    """
    token = os.getenv("MAPBOX_TOKEN")
    if not token:
        raise CommuteError("missing_mapbox_token")

    start = time.perf_counter()

    coords = f"{home['lon']},{home['lat']};{office['lon']},{office['lat']}"
    params = {
        "alternatives": "true",
        "overview": "false",
        "steps": "false",
        "access_token": token,
        # annotations not strictly needed for ETA
    }
    r = requests.get(f"{MAPBOX_BASE}/{coords}", params=params, timeout=12)
    if r.status_code != 200:
        raise CommuteError(f"mapbox_http_{r.status_code}")
    data = r.json()
    routes = _pick_routes(data)
    if not routes:
        raise CommuteError("no_routes_found")

    # Durations are seconds
    primary = routes[0]
    alt = routes[1] if len(routes) > 1 else None

    eta_min = round(primary["duration"] / 60)
    alt_save_min = 0
    need_reroute = False
    if alt:
        alt_eta = round(alt["duration"] / 60)
        alt_save_min = max(0, eta_min - alt_eta)
        need_reroute = alt_save_min >= reroute_threshold_min

    arrive_dt = _today_at(arrive_by_hhmm)
    leave_by = arrive_dt - dt.timedelta(minutes=eta_min + buffer_minutes)

    payload = {
        "eta_min": eta_min,
        "leave_by": _fmt_hhmm(leave_by),
        "arrive_by": arrive_by_hhmm,
        "buffer_minutes": buffer_minutes,
        "recommendation": {
            "need_reroute": need_reroute,
            "alt_save_min": alt_save_min,
        }
    }
    latency_ms = int((time.perf_counter() - start) * 1000)
    return payload, latency_ms