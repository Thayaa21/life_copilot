import json, re
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from zoneinfo import ZoneInfo

from api.llm import llm_complete

TZ = "America/Phoenix"

_SCHEDULE_PROMPT = """You are extracting events from a messy schedule.
Return STRICT JSON only, no prose.

INPUT:
- free text with class/office schedule lines
- today's date and timezone
- default year to assume

RULES:
- For each event, output {summary, start, end, location, notes}
- Prefer explicit dates; if only weekday is given (Mon/Tue/etc), schedule the NEXT occurrence from today in the given timezone/year.
- Times may be ranges '9:00-10:15' or single time '14:30' (assume 60 minutes if no end).
- If a line implies multiple days (e.g., 'Tue & Thu'), create separate events.
- Keep summaries short (course code/title/meeting name).
- Put any uncertainties in a top-level 'assumptions' list of strings.
- If you can't parse an item, omit it rather than guessing wildly.

OUTPUT JSON SCHEMA:
{
  "events": [
     {"summary": "CS201 Lecture", "start":"YYYY-MM-DDTHH:MM", "end":"YYYY-MM-DDTHH:MM", "location":"Building A 101", "notes": "optional"}
  ],
  "assumptions": ["..."]
}"""

def _json_first_obj(s: str) -> Dict[str, Any]:
    """Extract first {...} block and json.loads it."""
    try:
        return json.loads(s)
    except Exception:
        pass
    m = re.search(r"\{.*\}", s, flags=re.S)
    if m:
        return json.loads(m.group(0))
    raise ValueError("No JSON object in LLM output")

def _next_weekday(from_day: date, target_idx: int) -> date:
    delta = (target_idx - from_day.weekday()) % 7
    if delta == 0:
        delta = 7
    return from_day + timedelta(days=delta)

def _wkday_idx(name: str) -> Optional[int]:
    names = ["mon","tue","wed","thu","fri","sat","sun"]
    for i, n in enumerate(names):
        if name.lower().startswith(n):
            return i
    return None

def normalize_llm_events(raw: Dict[str, Any], today: date, tz: str, default_year: int) -> Dict[str, Any]:
    events = []
    assumptions = list(raw.get("assumptions") or [])
    for e in raw.get("events", []):
        summary = (e.get("summary") or "").strip() or "(untitled)"
        location = (e.get("location") or "").strip() or None
        notes = (e.get("notes") or "").strip() or None
        start = (e.get("start") or "").strip()
        end   = (e.get("end") or "").strip()

        # If LLM returned weekday tokens instead of dates, convert to next occurrence
        # Accept forms like "Tue 09:00" or "Tue 09:00-10:00"
        if re.match(r"^[A-Za-z]{3}\b", start):
            parts = re.split(r"\s+", start, maxsplit=1)
            idx = _wkday_idx(parts[0])
            if idx is not None:
                day = _next_weekday(today, idx)
                timepart = parts[1] if len(parts) > 1 else "09:00"
                start = f"{day.isoformat()}T{timepart}"

        if end and re.match(r"^[A-Za-z]{3}\b", end):
            parts = re.split(r"\s+", end, maxsplit=1)
            idx = _wkday_idx(parts[0])
            if idx is not None:
                day = _next_weekday(today, idx)
                timepart = parts[1] if len(parts) > 1 else None
                if timepart:
                    end = f"{day.isoformat()}T{timepart}"
                else:
                    end = ""

        # If start is date-only, default to 09:00
        if re.match(r"^\d{4}-\d{2}-\d{2}$", start):
            start = f"{start}T09:00"

        # If end missing, assume +60 min
        if not end and re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$", start):
            from datetime import datetime, timedelta
            dt0 = datetime.fromisoformat(start)
            end = (dt0 + timedelta(minutes=60)).strftime("%Y-%m-%dT%H:%M")

        events.append({
            "summary": summary,
            "start": start,
            "end": end if end else None,
            "location": location,
            "notes": notes
        })
    return {"events": events, "assumptions": assumptions}

def llm_parse_schedule(free_text: str, default_year: int, tz: str = TZ) -> Dict[str, Any]:
    today = date.today()
    user_payload = {
        "today": today.strftime("%Y-%m-%d"),
        "timezone": tz,
        "default_year": default_year,
        "text": free_text
    }
    out = llm_complete(_SCHEDULE_PROMPT, json.dumps(user_payload))
    raw = _json_first_obj(out)
    return normalize_llm_events(raw, today, tz, default_year)