# api/brief.py
import os, json, datetime as dt
from zoneinfo import ZoneInfo
from typing import Dict, Any, List, Tuple
import requests

API_BASE = os.getenv("BRIEF_API_BASE", "http://127.0.0.1:8000")  # call our own API
TZ = os.getenv("BRIEF_TZ", "America/Phoenix")

REPORT_DIR = "data/reports"
os.makedirs(REPORT_DIR, exist_ok=True)

def _today_local() -> dt.datetime:
    return dt.datetime.now(ZoneInfo(TZ))

def _get(url: str, **kw):
    r = requests.get(url, timeout=kw.pop("timeout", 15))
    r.raise_for_status()
    return r.json()

def _post(url: str, json_body: Dict[str, Any], **kw):
    r = requests.post(url, json=json_body, timeout=kw.pop("timeout", 30))
    r.raise_for_status()
    return r.json()

def fetch_inputs() -> Dict[str, Any]:
    weather = _get(f"{API_BASE}/weather")
    commute = _get(f"{API_BASE}/commute")
    # If Calendar is disabled upstream, this will return {"events":[]}
    events  = _get(f"{API_BASE}/calendar/events").get("events", [])

    # Small, readable weather brief
    hourly = weather.get("hourly", [])
    wbrief = ""
    if hourly:
        h0 = hourly[0]
        wbrief = f"Now {h0.get('temp','?')}°F · UV {h0.get('uv','?')} · Rain {h0.get('precip_prob','?')}%"

    return {"weather": weather, "commute": commute, "events": events, "weather_brief": wbrief}

def run_planner(events: List[Dict[str, Any]], weather_brief: str) -> Dict[str, Any]:
    try:
        out = _post(f"{API_BASE}/agent/plan", {"events": events, "weather_brief": weather_brief})
        return out.get("plan", {}) or {}
    except Exception:
        return {}

def run_actions(plan: Dict[str, Any]) -> Dict[str, Any]:
    # We let backend decide: picks + OTW
    try:
        out = _post(f"{API_BASE}/agent/act", {
            "plan": plan,
            "answers": {},     # zero-shot; UI can fill later
            "use_otw": True
        })
        return out
    except Exception:
        return {"recommendations": [], "otw": []}

def maybe_create_leave_reminder(commute: Dict[str, Any]) -> Dict[str, Any] | None:
    """Optionally create a 'Leave by' reminder ~cm['leave_by'] with a small buffer."""
    try:
        arrive_by = commute.get("arrive_by")  # "HH:MM"
        leave_by  = commute.get("leave_by")   # "HH:MM"
        if not (arrive_by and leave_by):
            return None
        today = dt.date.today()
        tz = ZoneInfo(TZ)
        lh, lm = map(int, leave_by.split(":"))
        leave_dt = dt.datetime(today.year, today.month, today.day, lh, lm, tzinfo=tz)
        when_iso = leave_dt.strftime("%Y-%m-%dT%H:%M")

        # create reminder via your API (which writes to Calendar if enabled)
        r = requests.post(f"{API_BASE}/calendar/reminder", json={
            "summary": f"Leave by {leave_by}",
            "when": when_iso,
            "description": "Auto from Daily Brief",
            "minutes": 0
        }, timeout=10)
        if r.ok:
            return r.json().get("created")
    except Exception:
        return None
    return None

def render_markdown(data: Dict[str, Any],
                    plan: Dict[str, Any],
                    act: Dict[str, Any]) -> str:
    now = _today_local()
    c = data["commute"]
    w = data["weather"]
    events = data["events"]

    lines = []
    lines.append(f"# Daily Brief — {now.strftime('%Y-%m-%d (%a) %H:%M %Z')}")
    lines.append("")
    lines.append(f"**Weather:** Now {w.get('temp_now','?')}°F, UV {w.get('uv_now','?')} · {data.get('weather_brief','')}")
    lines.append(f"**Commute:** ETA {c.get('eta_min','?')} min · Leave by {c.get('leave_by','?')} · Arrive by {c.get('arrive_by','?')}")
    lines.append("")
    lines.append("## First 3 events")
    for e in (events or [])[:3]:
        lines.append(f"- **{e.get('summary','(no title)')}** — {e.get('start','?')} → {e.get('end','?')}  "
                     f"{' · '+e['location'] if e.get('location') else ''}")
    lines.append("")
    if plan:
        lines.append("## Plan")
        lines.append(f"- **Scenario**: {plan.get('scenario','?')}")
        lines.append(f"- **Event**: {plan.get('event_title','?')} @ {plan.get('event_time','?')}")
        if plan.get("checklist"):
            lines.append("- **Checklist:** " + "; ".join(plan.get("checklist", [])))
        if plan.get("questions"):
            lines.append("- **Questions:** " + "; ".join([q.get('text') if isinstance(q, dict) else str(q) for q in plan.get("questions", [])]))
        lines.append("")
    recs = (act or {}).get("recommendations", []) or []
    if recs:
        lines.append("## Picks")
        for r in recs[:2]:
            lines.append(f"- **{r.get('title','')}** — ${r.get('price','?')} "
                         f"(Prime {r.get('prime')}, {r.get('delivery_days','?')}d)  "
                         f"{'(link)' if r.get('url') else ''}")
    otw = (act or {}).get("otw", []) or []
    if otw:
        lines.append("## On-the-way (OTW)")
        for p in otw[:3]:
            links = []
            if p.get("url"): links.append("site")
            if p.get("map_url"): links.append("map")
            links_txt = f" [{' · '.join(links)}]" if links else ""
            lines.append(f"- **{p.get('name','')}** — +{p.get('detour_min','?')} min · {p.get('address','')}{links_txt}")

    return "\n".join(lines)

def save_report(md: str) -> str:
    now = _today_local()
    path = os.path.join(REPORT_DIR, f"brief-{now.strftime('%Y%m%d')}.md")
    with open(path, "w") as f:
        f.write(md)
    return path

def compose_and_optionally_commit(create_leave_event: bool = True) -> Dict[str, Any]:
    data = fetch_inputs()
    plan = run_planner(data["events"], data.get("weather_brief",""))
    act  = run_actions(plan) if plan else {"recommendations": [], "otw": []}

    created = None
    if create_leave_event:
        created = maybe_create_leave_reminder(data["commute"])

    md = render_markdown(data, plan, act)
    path = save_report(md)
    return {
        "report_path": path,
        "report_md": md,
        "created_leave": created,
        "plan": plan,
        "act": act,
        "inputs": {
            "weather": {"temp_now": data["weather"].get("temp_now"), "uv_now": data["weather"].get("uv_now")},
            "commute": data["commute"],
            "events": data["events"][:3],
        }
    }