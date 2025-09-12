import time
import requests
from typing import Dict, List, Any, Tuple

def _pick_next_6(hourly: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
    # Open-Meteo returns arrays aligned by index
    times = hourly.get("time", [])[:6]
    temps = hourly.get("temperature_2m", [])[:6]
    uvs   = hourly.get("uv_index", [])[:6]
    pops  = hourly.get("precipitation_probability", [])[:6]
    out = []
    for i in range(min(len(times), 6)):
        out.append({
            "time": times[i],                          # ISO hh:mm will come in with timezone=auto
            "temp": round(float(temps[i]), 1) if temps else None,
            "uv":   round(float(uvs[i]),   1) if uvs   else None,
            "precip_prob": int(pops[i]) if pops else None
        })
    return out

def get_weather(lat: float, lon: float, use_fahrenheit: bool = True) -> Tuple[Dict[str, Any], int]:
    """
    Calls Open-Meteo and returns a compact dict + latency_ms.
    """
    start = time.perf_counter()
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,uv_index",
        "hourly": "temperature_2m,uv_index,precipitation_probability",
        "timezone": "auto",
    }
    if use_fahrenheit:
        params["temperature_unit"] = "fahrenheit"

    r = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    current = data.get("current", {})
    hourly  = data.get("hourly", {})

    result = {
        "temp_now": round(float(current.get("temperature_2m")), 1) if current.get("temperature_2m") is not None else None,
        "uv_now":   round(float(current.get("uv_index")),       1) if current.get("uv_index")       is not None else None,
        "hourly":   _pick_next_6(hourly)
    }
    latency_ms = int((time.perf_counter() - start) * 1000)
    return result, latency_ms