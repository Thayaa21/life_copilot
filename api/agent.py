import json, os, datetime as dt
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from api.llm import llm_complete
from api.tools_catalog import search_products
from api.scoring import score_products
from api.tools_places_osm import search_along_route  # you added this in Phase 5B

TZ = "America/Phoenix"
PROFILE_PATH = "data/profile.json"

SCENARIO_PROMPT = """You are a concise planner for a personal routine copilot.
Given today's events (JSON) and a short weather brief, decide the MOST relevant upcoming scenario and produce a compact plan.
Scenarios: dinner_date, child_birthday, interview, morning_commute, generic_meeting, outdoor_event.
Return ONLY JSON with keys:
- scenario (string)
- event_title (string)
- event_time (ISO local or null)
- venue (string or null)
- checklist (5-7 short strings)
- questions (2-4 short questions; yes/no or ask for a number like a budget)"""

ACTION_PROMPT = """You convert a scenario + answers into actions.
Input JSON includes: scenario, event_time (local ISO), venue, answers (dict), profile (budgets, preferences), today (YYYY-MM-DD).
Decide:
1) missing_items[]: strings that user lacks.
2) catalog_queries[]: for each missing item, build {item,q,budget,deadline,prime_only}.
   - q: short Amazon search string (e.g., "men leather belt black 32-34").
   - budget: number or null (use profile defaults if not given).
   - deadline: YYYY-MM-DD or null (use event date if available, else tomorrow).
   - prime_only: boolean (prefer true).
3) need_otw_categories[]: zero or more of ['coffee','florist','gift shop','bakery'].
Return ONLY JSON: {"missing_items":[],"catalog_queries":[],"need_otw_categories":[]}"""

def _load_profile() -> Dict[str, Any]:
    if os.path.exists(PROFILE_PATH):
        with open(PROFILE_PATH,"r") as f: 
            return json.load(f)
    # defaults
    return {
        "user_role": "student",
        "default_gift_budget": 30,
        "default_interview_budget": 25,
        "prime_preferred": True
    }

def _today_iso(tz: str = TZ) -> str:
    return dt.datetime.now(ZoneInfo(tz)).strftime("%Y-%m-%d")

def plan_event(events, weather_brief):
    sys = "Be terse. Output strict JSON only."
    usr = json.dumps({"events": events[:6], "weather": weather_brief})
    out = llm_complete(SCENARIO_PROMPT, usr)
    try:
        j = json.loads(out)
        # normalize questions
        qs = j.get("questions", [])
        j["questions"] = [
            (q.get("text") if isinstance(q, dict) else str(q))
            for q in qs
        ]
        return j
    except Exception:
        return {
            "scenario": "generic_meeting",
            "event_title": (events[0]["summary"] if events else "Upcoming"),
            "event_time": (events[0].get("start") if events else None),
            "venue": (events[0].get("location") if events else None),
            "checklist": ["water","charger"],
            "questions": ["Do you need a coffee on the way?"]
        }

def decide_actions(plan: Dict[str, Any], answers: Dict[str, Any]) -> Dict[str, Any]:
    profile = _load_profile()
    payload = {
        "scenario": plan.get("scenario"),
        "event_time": plan.get("event_time"),
        "venue": plan.get("venue"),
        "answers": answers,
        "profile": profile,
        "today": _today_iso()
    }
    sys = "Return strict JSON only."
    out = llm_complete(ACTION_PROMPT, json.dumps(payload))
    try:
        return json.loads(out)
    except Exception:
        # fallback: typical interview case
        deadline = _today_iso()
        return {
            "missing_items": ["belt"],
            "catalog_queries": [{
                "item":"belt",
                "q":"men leather belt black 32-34",
                "budget": profile.get("default_interview_budget",25),
                "deadline": deadline,
                "prime_only": True
            }],
            "need_otw_categories": ["coffee"]
        }

def find_products(qspecs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for spec in qspecs[:2]:  # keep it tight
        raw = search_products(
            spec.get("q",""),
            budget=spec.get("budget"),
            deadline_iso=spec.get("deadline"),
            prime_only=bool(spec.get("prime_only", True)),
        )
        scored = score_products(raw, spec.get("q",""))
        if scored:
            top = scored[0]
            top["for_item"] = spec.get("item")
            out.append(top)
    return out

def find_otw(categories: List[str], home: Dict[str,float], office: Dict[str,float]) -> List[Dict[str, Any]]:
    res = []
    for c in categories[:2]:
        try:
            items = search_along_route(c, home, office)
            for it in items:
                res.append({"category": c, **it})
        except Exception:
            continue
    return res[:4]
