import os
import json
import datetime as dt
from typing import List, Dict, Any, Optional
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar"]

TOKEN_PATH = "data/google_token.json"

def _client_config() -> dict:
    """Builds an OAuth client config dict from env vars (no credentials.json file needed)."""
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

def _ensure_creds() -> Credentials:
    """Loads or creates OAuth credentials; launches browser on first run."""
    creds: Optional[Credentials] = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Try refresh
            try:
                creds.refresh(Request())  # type: ignore[name-defined]
            except Exception:
                creds = None
        if not creds:
            flow = InstalledAppFlow.from_client_config(_client_config(), SCOPES)
            # This opens a browser to authorize your Google account
            creds = flow.run_local_server(port=0)
        # Save for next time
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return creds

def _svc():
    creds = _ensure_creds()
    return build("calendar", "v3", credentials=creds, cache_discovery=False)

def connect() -> dict:
    """Force an auth check; returns email of the authorized user."""
    svc = _svc()
    # A cheap call: get calendar settings / list to infer the primary id
    me = svc.calendarList().get(calendarId="primary").execute()
    return {"connected": True, "primary": me.get("summaryOverride") or me.get("summary")}

def _window_today_tomorrow(tz_str: str) -> tuple[str, str]:
    tz = ZoneInfo(tz_str)
    now = dt.datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = (start + dt.timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    # RFC3339 with offset
    return start.isoformat(), end.isoformat()

def get_events_today_and_tomorrow(tz_str: str = "America/Phoenix") -> List[Dict[str, Any]]:
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
                 tz_str: str = "America/Phoenix") -> Dict[str, Any]:
    """
    Creates a 15-min event at the given local ISO time with popup notification (minutes before = 0..).
    when_iso_local example: '2025-09-12T08:27'
    """
    svc = _svc()
    tz = ZoneInfo(tz_str)
    start_dt = dt.datetime.fromisoformat(when_iso_local)
    start_dt = start_dt.replace(tzinfo=tz)
    end_dt = start_dt + dt.timedelta(minutes=duration_minutes)

    evt = {
        "summary": summary,
        "description": description or "",
        "start": {"dateTime": start_dt.isoformat(), "timeZone": tz_str},
        "end":   {"dateTime": end_dt.isoformat(),   "timeZone": tz_str},
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": minutes}]
        }
    }
    created = svc.events().insert(calendarId="primary", body=evt).execute()
    return {"id": created.get("id"), "htmlLink": created.get("htmlLink")}