import os, json
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from api.tools_weather import get_weather

load_dotenv()
app = FastAPI(title="Life Copilot API")

@app.get("/health")
def health():
    return JSONResponse({"ok": True})

def _load_profile_coords():
    # fallback if file is missing
    lat = float(os.getenv("DEFAULT_LAT", "33.424"))
    lon = float(os.getenv("DEFAULT_LON", "-111.928"))
    try:
        with open("data/profile.json", "r") as f:
            prof = json.load(f)
        # if you added lat/lon to profile, prefer those; else keep defaults
        lat = float(prof.get("lat", lat))
        lon = float(prof.get("lon", lon))
    except Exception:
        pass
    return lat, lon

@app.get("/weather")
def weather():
    try:
        lat, lon = _load_profile_coords()
        payload, latency_ms = get_weather(lat, lon, use_fahrenheit=True)
        payload["latency_ms"] = latency_ms
        return JSONResponse(payload)
    except Exception as e:
        # surface a friendly error without stack traces
        raise HTTPException(status_code=503, detail=f"weather_unavailable: {e}")
    

import json
from fastapi import HTTPException
from api.tools_commute import get_commute, CommuteError

def _load_commute_cfg():
    with open("data/commute.json", "r") as f:
        return json.load(f)

@app.get("/commute")
def commute():
    try:
        cfg = _load_commute_cfg()
        payload, latency_ms = get_commute(
            home=cfg["home"],
            office=cfg["office"],
            arrive_by_hhmm=cfg["arrive_by"],
            buffer_minutes=int(cfg.get("buffer_minutes", 10)),
        )
        payload["latency_ms"] = latency_ms
        return JSONResponse(payload)
    except CommuteError as ce:
        raise HTTPException(status_code=400, detail=str(ce))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"commute_unavailable: {e}")