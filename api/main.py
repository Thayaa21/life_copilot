import os, json
import datetime as dt
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Body, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse

from api.tools_weather import get_weather
from api.tools_commute import get_commute, CommuteError
from api.tools_calendar import connect as cal_connect, get_events_today_and_tomorrow, add_reminder, add_event

# ★ Use only the OSM implementation (avoid name clash on PlacesError)
from api.tools_places_osm import search_along_route as osm_search_along_route, PlacesError

from api.agent import plan_event, decide_actions, find_products, find_otw

# ★ CSV/rule parser + LLM parser come from different modules
from api.schedule_parser import parse_schedule, extract_text
from api.schedule_llm import llm_parse_schedule

from api.brief import compose_and_optionally_commit
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()
BRIEF_ENABLED = os.getenv("BRIEF_ENABLED", "true").lower() == "true"
BRIEF_TIME = os.getenv("BRIEF_TIME", "07:00")  # HH:MM local
_scheduler = None
app = FastAPI(title="Life Copilot API")

@app.get("/health")
def health():
    return JSONResponse({"ok": True})

def _reschedule_brief(hhmm: str, enabled: bool):
    global _scheduler
    if not BRIEF_ENABLED:
        return
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
        _scheduler.start(paused=False)

    # clear existing jobs
    for job in list(_scheduler.get_jobs()):
        _scheduler.remove_job(job.id)

    if not enabled:
        return

    import re
    m = re.match(r"^(\d{2}):(\d{2})$", hhmm or "")
    if not m:
        hhmm = BRIEF_TIME
        m = re.match(r"^(\d{2}):(\d{2})$", hhmm)
    H, M = int(m.group(1)), int(m.group(2))

    # run daily at local tz (America/Phoenix)
    _scheduler.add_job(
        func=lambda: compose_and_optionally_commit(create_leave_event=True),
        trigger="cron",
        hour=H, minute=M, second=0,
        id="daily_brief",
        replace_existing=True
    )

# kick scheduler on startup with defaults or persisted config
@app.on_event("startup")
def _startup_schedule():
    if not BRIEF_ENABLED:
        return
    try:
        import json as _json, os as _os
        cfg_path = "data/brief.json"
        time_ = BRIEF_TIME
        enabled_ = True
        if _os.path.exists(cfg_path):
            with open(cfg_path) as f:
                cfg = _json.load(f)
                time_ = cfg.get("time", time_)
                enabled_ = bool(cfg.get("enabled", True))
        _reschedule_brief(time_, enabled_)
    except Exception:
        pass

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
@app.post("/brief/run")
def brief_run(payload: dict = Body(None)):
    """
    Run the Daily Brief now. payload: {"create_leave_event": true/false}
    Returns: {report_path, report_md, created_leave, plan, act, inputs}
    """
    if not BRIEF_ENABLED:
        raise HTTPException(status_code=503, detail="brief_disabled")
    try:
        flag = True
        if payload and "create_leave_event" in payload:
            flag = bool(payload["create_leave_event"])
        out = compose_and_optionally_commit(create_leave_event=flag)
        return JSONResponse(out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"brief_run_failed: {e}")

@app.post("/brief/config")
def brief_config(payload: dict = Body(...)):
    """
    Set daily brief time. payload: {"time":"HH:MM", "enabled": true/false}
    Persists to data/brief.json
    """
    try:
        cfg_path = "data/brief.json"
        os.makedirs("data", exist_ok=True)
        current = {}
        if os.path.exists(cfg_path):
            import json as _json
            with open(cfg_path) as f: current = _json.load(f)
        # update
        if "time" in payload:
            current["time"] = payload["time"]
        if "enabled" in payload:
            current["enabled"] = bool(payload["enabled"])
        # default if missing
        current.setdefault("time", BRIEF_TIME)
        current.setdefault("enabled", True)
        # write
        import json as _json
        with open(cfg_path, "w") as f: _json.dump(current, f)
        # reschedule
        _reschedule_brief(current.get("time"), current.get("enabled", True))
        return JSONResponse({"ok": True, "config": current})
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"brief_config_failed: {e}")

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
    

    from fastapi import Body
from api.tools_calendar import connect as cal_connect, get_events_today_and_tomorrow, add_reminder

@app.get("/calendar/connect")
def calendar_connect():
    try:
        info = cal_connect()
        return JSONResponse(info)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"calendar_connect_failed: {e}")

@app.get("/calendar/events")
def calendar_events():
    try:
        items = get_events_today_and_tomorrow("America/Phoenix")
        return JSONResponse({"events": items})
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"calendar_events_failed: {e}")

@app.post("/calendar/reminder")
def calendar_reminder(payload: dict = Body(...)):
    """
    Expects JSON: {
      "summary": "Leave by 08:27",
      "when": "2025-09-12T08:27",
      "description": "Commute buffer included",
      "minutes": 0
    }
    """
    try:
        summary = payload["summary"]
        when_iso = payload["when"]
        description = payload.get("description")
        minutes = int(payload.get("minutes", 0))
        created = add_reminder(summary, when_iso, description, minutes, tz_str="America/Phoenix")
        return JSONResponse({"created": created})
    except KeyError as ke:
        raise HTTPException(status_code=400, detail=f"missing_field: {ke}")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"calendar_reminder_failed: {e}")
    
from fastapi import Query
from api.tools_catalog import search_products, CatalogError
from api.scoring import score_products

@app.get("/catalog/search")
def catalog_search(
    q: str = Query(..., description="Product search query"),
    budget: float | None = Query(None),
    deadline: str | None = Query(None, description="YYYY-MM-DD latest acceptable delivery date"),
    prime_only: bool = Query(True),
    zip: str | None = Query(None)
):
    try:
        raw = search_products(q, budget=budget, deadline_iso=deadline,
                              prime_only=prime_only, provider="rainforest", zip_code=zip)
        if not raw:
            return JSONResponse({"items": [], "count": 0, "note": "no_results_after_filters"})
        scored = score_products(raw, q)
        return JSONResponse({"items": scored[:2], "count": len(scored)})
    except CatalogError as ce:
        raise HTTPException(status_code=400, detail=str(ce))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"catalog_unavailable: {e}")
    
TZ = "America/Phoenix"

def _today_local(tz_str: str = TZ) -> dt.datetime:
    return dt.datetime.now(ZoneInfo(tz_str))

def compute_order_by_iso(deadline_iso: str | None,
                         delivery_days: int | None,
                         cutoff_hour: int = 19,
                         tz_str: str = TZ) -> str:
    """
    Pick the latest safe 'order by' time so the item arrives by the deadline.
    If delivery_days is known: order_no_later_than = (deadline_date - delivery_days) @ cutoff_hour.
    If unknown: default to today @ cutoff_hour.
    If computed time is already past: nudge to now + 30 min.
    Returns local ISO string: 'YYYY-MM-DDTHH:MM'
    """
    now = _today_local(tz_str)
    # default: today at cutoff
    base = now.replace(hour=cutoff_hour, minute=0, second=0, microsecond=0)

    if deadline_iso and delivery_days is not None:
        try:
            y, m, d = map(int, deadline_iso.split("-"))
            target_date = dt.date(y, m, d) - dt.timedelta(days=int(delivery_days))
            base = dt.datetime(target_date.year, target_date.month, target_date.day, cutoff_hour, 0, tzinfo=ZoneInfo(tz_str))
        except Exception:
            pass  # keep default

    # ensure order-by isn't in the past
    if base < now:
        base = (now + dt.timedelta(minutes=30)).replace(second=0, microsecond=0)

    return base.strftime("%Y-%m-%dT%H:%M")

from fastapi import Body
from api.tools_calendar import add_reminder

@app.post("/catalog/order_reminder")
def catalog_order_reminder(payload: dict = Body(...)):
    """
    JSON:
    {
      "title": "Men Leather Belt ...",
      "url": "https://amazon.com/...",
      "delivery_days": 1,              # can be null
      "deadline": "2025-09-15"         # can be null
    }
    Creates a calendar event: "Order by 7:00 PM — <short title>"
    """
    try:
        title = (payload.get("title") or "").strip()
        url   = (payload.get("url")   or "").strip()
        delivery_days = payload.get("delivery_days")  # may be None
        deadline      = payload.get("deadline")       # may be None

        if not title:
            raise ValueError("missing title")

        when_iso = compute_order_by_iso(deadline, delivery_days, cutoff_hour=19, tz_str=TZ)
        summary = f"Order by 7:00 PM — {title[:40]}{'…' if len(title) > 40 else ''}"
        desc = (f"{url}" if url else "")

        created = add_reminder(summary=summary,
                               when_iso_local=when_iso,
                               description=desc,
                               minutes=15,  # popup 15 min before
                               tz_str=TZ)
        return JSONResponse({"created": created, "when": when_iso})
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"order_reminder_failed: {e}")
    
@app.get("/places/along_route")
def places_along_route(category: str):
    """
    Example: /places/along_route?category=coffee
    Free stack: OSM Overpass for POIs, Mapbox for detour.
    """
    try:
        cfg = _load_commute_cfg()
        items = osm_search_along_route(category, cfg["home"], cfg["office"])
        return JSONResponse({"items": items})
    except PlacesError as pe:
        raise HTTPException(status_code=400, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"places_unavailable: {e}")
    
@app.post("/agent/plan")
def agent_plan(payload: dict):
    """
    payload: { "events": [...], "weather_brief": "string" }
    events format: each item at least has summary; if available include start (ISO) and location.
    """
    try:
        events = payload.get("events", [])
        weather = payload.get("weather_brief", "")
        plan = plan_event(events, weather)
        return JSONResponse({"plan": plan})
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"agent_plan_failed: {e}")

@app.post("/agent/act")
def agent_act(payload: dict):
    """
    payload: {
      "plan": {...},            # from /agent/plan
      "answers": {...},         # map question->answer
      "use_otw": true           # include OTW lookups via OSM
    }
    """
    try:
        cfg = _load_commute_cfg()  # you already have this from earlier phases
        plan = payload.get("plan", {})
        answers = payload.get("answers", {})
        actions = decide_actions(plan, answers)

        recs = find_products(actions.get("catalog_queries", []))
        otw = find_otw(actions.get("need_otw_categories", []) if payload.get("use_otw") else [], cfg["home"], cfg["office"])

        return JSONResponse({
            "scenario": plan.get("scenario"),
            "event_title": plan.get("event_title"),
            "event_time": plan.get("event_time"),
            "venue": plan.get("venue"),
            "checklist": plan.get("checklist", []),
            "questions": plan.get("questions", []),
            "recommendations": recs,
            "otw": otw,
            "actions": actions
        })
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"agent_act_failed: {e}")
    
@app.post("/schedule/ingest")
async def schedule_ingest(
    file: UploadFile = File(...),
    default_year: int = Form(None),
    use_llm: bool | str = Form(False)   # accept str "true"/"false" from forms too
):
    """
    Upload schedule (csv/txt/ics/pdf/png/jpg). If use_llm=true, parse with LLM.
    Returns proposed events plus any 'assumptions'. If LLM fails, falls back to rule parser.
    """
    try:
        # normalize bool from form strings
        if isinstance(use_llm, str):
            use_llm = use_llm.strip().lower() in ("1", "true", "yes", "y", "on")

        blob = await file.read()
        year = default_year or datetime.now().year

        # OCR/text extraction (your schedule_parser does this)
        text = extract_text(file.filename, blob)

        if use_llm:
            try:
                parsed = llm_parse_schedule(text, year, tz=TZ)
                events = parsed.get("events", [])
                assumptions = parsed.get("assumptions", [])
                return JSONResponse({"proposed": events, "assumptions": assumptions, "used": "llm"})
            except Exception as e:
                # FALLBACK to rule-based if LLM path fails
                events = parse_schedule(file.filename, blob, year)
                return JSONResponse({
                    "proposed": events,
                    "assumptions": [f"LLM parse failed → fallback to rule parser: {e}"],
                    "used": "llm_fallback_rule"
                })

        # rule-based path (no LLM)
        events = parse_schedule(file.filename, blob, year)
        return JSONResponse({"proposed": events, "assumptions": [], "used": "rule"})

    except Exception as e:
        # surface exact reason to the client for debugging
        raise HTTPException(status_code=400, detail=f"schedule_ingest_failed: {e}")

@app.post("/schedule/commit")
def schedule_commit(payload: dict):
    """
    payload: { "events":[{"summary","start","end","location","description"}] }
    Creates events in Google Calendar.
    """
    try:
        created = []
        for e in payload.get("events", []):
            c = add_event(
                summary=e.get("summary","(no title)"),
                start_iso_local=e.get("start"),
                end_iso_local=e.get("end"),
                description=e.get("description",""),
                location=e.get("location",""),
                tz_str="America/Phoenix"
            )
            created.append({"id": c.get("id"), "htmlLink": c.get("htmlLink")})
        return JSONResponse({"created": created})
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"schedule_commit_failed: {e}")