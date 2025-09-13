# api/tools_calendar.py

import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request  # for token refresh

# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────

SCOPES = ["https://www.googleapis.com/auth/calendar"]  # read/write
TOKEN_PATH = "data/google_token.json"
TZ_DEFAULT = os.getenv("TZ", "America/Phoenix")

# These must be in your environment (.env):
#   GOOGLE_OAUTH_CLIENT_ID
#   GOOGLE_OAUTH_CLIENT_SECRET
def _client_config() -> dict:
    cid = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    csec = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
    if not cid or not csec:
        raise RuntimeError("Missing GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET in .env")
    return {
        "installed": {
            "client_id": cid,
            "client_secret": csec,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"]
        }
    }

# ──────────────────────────────────────────────────────────────────────────────
# Auth / Service
# ──────────────────────────────────────────────────────────────────────────────

def _ensure_creds() -> Credentials:
    """Load or create OAuth credentials; opens a browser on first run."""
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)

    creds: Optional[Credentials] = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    # Refresh or (re)authorize
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        if not creds:
            flow = InstalledAppFlow.from_client_config(_client_config(), SCOPES)
            # Spins up a localhost receiver and opens a browser consent page
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return creds

def _svc():
    """Build Calendar API client (discovery cache disabled to avoid file warnings)."""
    creds = _ensure_creds()
    return build("calendar", "v3", credentials=creds, cache_discovery=False)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _coerce_local_iso(s: Optional[str], tz_str: str) -> Optional[str]:
    """
    Accepts:
      - 'YYYY-MM-DDTHH:MM' (local time) → attaches tz and returns RFC3339 with offset
      - RFC3339 with timezone → returned as-is
    Returns an ISO string with tz offset (minute precision).
    """
    if not s:
        return None
    # Local naive string → attach timezone
    if len(s) == 16 and "T" in s:
        dt = datetime.strptime(s, "%Y-%m-%dT%H:%M").replace(tzinfo=ZoneInfo(tz_str))
        return dt.isoformat(timespec="minutes")  # e.g. 2025-09-13T09:00-07:00
    # Assume caller already provided RFC3339 w/ tz
    return s

def _window_today_tomorrow(tz_str: str) -> tuple[str, str]:
    tz = ZoneInfo(tz_str)
    now = datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = (start + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    return start.isoformat(), end.isoformat()

# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def connect() -> Dict[str, Any]:
    """
    Force an auth check; returns info on the primary calendar.
    Triggers OAuth flow the first time and caches token.
    """
    svc = _svc()
    me = svc.calendarList().get(calendarId="primary").execute()
    return {
        "connected": True,
        "primary": me.get("summaryOverride") or me.get("summary") or "primary"
    }

def get_events_today_and_tomorrow(tz_str: str = TZ_DEFAULT) -> List[Dict[str, Any]]:
    svc = _svc()
    time_min, time_max = _window_today_tomorrow(tz_str)
    events_result = svc.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    items = events_result.get("items", [])
    out: List[Dict[str, Any]] = []
    for e in items:
        start = e.get("start", {}).get("dateTime") or e.get("start", {}).get("date")
        end = e.get("end", {}).get("dateTime") or e.get("end", {}).get("date")
        out.append({
            "id": e.get("id"),
            "summary": e.get("summary"),
            "start": start,
            "end": end,
            "location": e.get("location"),
            "hangoutLink": e.get("hangoutLink"),
        })
    return out

def add_reminder(summary: str,
                 when_iso_local: str,
                 description: Optional[str] = None,
                 minutes: int = 0,
                 duration_minutes: int = 15,
                 tz_str: str = TZ_DEFAULT) -> Dict[str, Any]:
    """
    Creates a short event at the given local ISO time with a popup reminder X minutes before.
    when_iso_local: 'YYYY-MM-DDTHH:MM' (local) or RFC3339 with tz.
    """
    svc = _svc()

    start_iso = _coerce_local_iso(when_iso_local, tz_str)
    if not start_iso:
        raise ValueError("start time is required")

    dt0 = datetime.fromisoformat(start_iso)
    end_iso = (dt0 + timedelta(minutes=duration_minutes)).isoformat(timespec="minutes")

    evt = {
        "summary": summary or "(no title)",
        "description": description or "",
        "start": {"dateTime": start_iso, "timeZone": tz_str},
        "end":   {"dateTime": end_iso,   "timeZone": tz_str},
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": int(minutes)}]
        }
    }
    created = svc.events().insert(calendarId="primary", body=evt).execute()
    return {"id": created.get("id"), "htmlLink": created.get("htmlLink")}

def add_event(summary: str,
              start_iso_local: str,
              end_iso_local: Optional[str],
              description: str = "",
              location: str = "",
              tz_str: str = TZ_DEFAULT) -> Dict[str, Any]:
    """
    Create a standard Calendar event.
    start_iso_local/end_iso_local should be 'YYYY-MM-DDTHH:MM' (local) or RFC3339 with tz.
    If end is missing or invalid, defaults to +60 minutes after start.
    """
    svc = _svc()

    start_iso = _coerce_local_iso(start_iso_local, tz_str)
    if not start_iso:
        raise ValueError("start time is required (YYYY-MM-DDTHH:MM or RFC3339)")

    if end_iso_local:
        end_iso = _coerce_local_iso(end_iso_local, tz_str)
    else:
        dt0 = datetime.fromisoformat(start_iso)
        end_iso = (dt0 + timedelta(minutes=60)).isoformat(timespec="minutes")

    # Safety: ensure end > start (avoid Google 400)
    try:
        if datetime.fromisoformat(end_iso) <= datetime.fromisoformat(start_iso):
            dt0 = datetime.fromisoformat(start_iso)
            end_iso = (dt0 + timedelta(minutes=60)).isoformat(timespec="minutes")
    except Exception:
        # If parse fails for any reason, force +60 min
        dt0 = datetime.fromisoformat(start_iso)
        end_iso = (dt0 + timedelta(minutes=60)).isoformat(timespec="minutes")

    body = {
        "summary": summary or "(no title)",
        "description": description or "",
        "location": location or "",
        "start": {"dateTime": start_iso, "timeZone": tz_str},
        "end":   {"dateTime": end_iso,   "timeZone": tz_str},
    }
    created = svc.events().insert(calendarId="primary", body=body).execute()
    return created