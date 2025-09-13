# api/schedule_parser.py
import csv, io, re
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta

# ── Day parsing ────────────────────────────────────────────────────────────────
_DAY_ALIASES = {
    "m": 0, "mon": 0,
    "tu": 1, "tue": 1, "tues": 1,
    "w": 2, "wed": 2,
    "th": 3, "thu": 3, "thur": 3, "thurs": 3, "r": 3,
    "f": 4, "fri": 4,
    "sa": 5, "sat": 5,
    "su": 6, "sun": 6,
}

def _parse_days(s: str) -> List[int]:
    """
    Examples accepted:
      "M, W"  "MW"  "M W"  "Tu"  "Tues"  "Th"  "R"  "M, W, F"  "tues"
    """
    if not s:
        return []
    s = s.strip()
    # Tokenize on comma/space while preserving "Th/Tu/Tues"
    tokens = re.findall(r"(Mon|Tue|Tues|Tu|Wed|Thu|Thur|Thurs|Th|Fri|Sat|Sun|Su|Sa|M|W|F|R|Tu|tues|wed|thu|th|mon|fri|sat|sun)",
                        s, flags=re.I)
    idxs: List[int] = []
    if tokens:
        for t in tokens:
            t = t.lower()
            if t == "r":
                t = "th"
            key = (t[:3] if t[:3] in ("mon","tue","wed","thu","fri","sat","sun")
                   else t)
            idx = _DAY_ALIASES.get(key)
            if idx is not None:
                idxs.append(idx)
        return sorted(set(idxs))
    # compact like "MWF", "TTh"
    i = 0
    while i < len(s):
        ch = s[i].lower()
        if ch == "t":
            if i + 1 < len(s) and s[i+1].lower() == "h":
                idxs.append(3); i += 2; continue   # "Th"
            idxs.append(1); i += 1; continue        # "T"/"Tu"
        if ch == "r":
            idxs.append(3); i += 1; continue
        if ch == "m": idxs.append(0)
        elif ch == "w": idxs.append(2)
        elif ch == "f": idxs.append(4)
        elif ch == "s":
            if i + 1 < len(s) and s[i+1].lower() == "a":
                idxs.append(5); i += 2; continue    # "Sa"
            idxs.append(6); i += 1; continue        # "Su"
        i += 1
    return sorted(set(idxs))

# ── Time / date parsing ───────────────────────────────────────────────────────
def _to_24h(x: str) -> str:
    x = x.strip().lower()
    # normalize "am/pm"
    x = x.replace("a.m.", "am").replace("p.m.", "pm")
    return datetime.strptime(x, "%I:%M %p").strftime("%H:%M")

def _parse_time(s: str) -> tuple[str, Optional[str]]:
    """
    '9:00 AM - 10:15 AM' -> ('09:00','10:15')
    '8:00 am - 3:00 pm'  -> ('08:00','15:00')
    '10:00 AM'           -> ('10:00', None)
    """
    if not s: return ("09:00", None)
    parts = [p.strip() for p in s.split("-")]
    if len(parts) == 2:
        return (_to_24h(parts[0]), _to_24h(parts[1]))
    return (_to_24h(parts[0]), None)

def _parse_dates(s: str) -> tuple[date, Optional[date]]:
    """
    '8/21/25 - 12/5/25' -> (2025-08-21, 2025-12-05)
    '8/21/2025 - 12/5/2025' supported too.
    '8/21/25' -> (2025-08-21, None)
    """
    if not s: raise ValueError("dates required")
    parts = [p.strip() for p in s.split("-")]
    def to_date(x: str) -> date:
        last = x.split("/")[-1]
        fmt = "%m/%d/%y" if len(last) == 2 else "%m/%d/%Y"
        return datetime.strptime(x, fmt).date()
    if len(parts) == 2:
        return (to_date(parts[0]), to_date(parts[1]))
    return (to_date(parts[0]), None)

def _iter_weekdays_between(start: date, end: date, wdays: List[int]):
    cur = start
    while cur <= end:
        if cur.weekday() in wdays:
            yield cur
        cur += timedelta(days=1)

# ── CSV → events ──────────────────────────────────────────────────────────────
def parse_csv(blob: bytes, max_events: int = 400) -> List[Dict[str, Any]]:
    """
    Expects headers: title, days, times, dates, location
    Emits discrete events with local ISO 'YYYY-MM-DDTHH:MM' start/end.
    """
    txt = blob.decode("utf-8", errors="ignore")
    rdr = csv.DictReader(io.StringIO(txt))
    events: List[Dict[str, Any]] = []

    for row in rdr:
        title = (row.get("title") or row.get("Title") or "").strip() or "(untitled)"
        days  = (row.get("days")  or row.get("Days")  or "").strip()
        times = (row.get("times") or row.get("Times") or "").strip()
        dates = (row.get("dates") or row.get("Date(s)") or row.get("Dates") or "").strip()
        loc   = (row.get("location") or row.get("Location") or "").strip()

        if not dates:
            continue

        wdays = _parse_days(days)
        t_start, t_end = _parse_time(times)
        d_start, d_end = _parse_dates(dates)

        # Put map URL (if any) also into notes so it shows in Calendar description
        notes = ""
        if loc.startswith("http://") or loc.startswith("https://"):
            notes = f"Map: {loc}"

        if not d_end:
            # single-day
            start_iso = f"{d_start.isoformat()}T{t_start}"
            end_iso = f"{d_start.isoformat()}T{t_end}" if t_end else None
            events.append({"summary": title, "start": start_iso, "end": end_iso,
                           "location": loc, "notes": notes})
        else:
            if not wdays:
                # no days → assume the first day-of-week of start date
                wdays = [d_start.weekday()]
            for d in _iter_weekdays_between(d_start, d_end, wdays):
                start_iso = f"{d.isoformat()}T{t_start}"
                end_iso = f"{d.isoformat()}T{t_end}" if t_end else None
                events.append({"summary": title, "start": start_iso, "end": end_iso,
                               "location": loc, "notes": notes})
                if len(events) >= max_events:
                    break
        if len(events) >= max_events:
            break

    return events

# Maintain the same API your main.py expects
def extract_text(filename: str, blob: bytes) -> str:
    # CSV-only mode: we don’t OCR; keep compat signature.
    return blob.decode("utf-8", errors="ignore")

def parse_schedule(filename: str, blob: bytes, default_year: int) -> List[Dict[str, Any]]:
    # Only parse CSVs in this mode; ignore other file types.
    if not filename.lower().endswith(".csv"):
        return []
    return parse_csv(blob)