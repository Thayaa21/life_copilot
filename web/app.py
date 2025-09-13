import requests
import streamlit as st
import datetime as dt
from zoneinfo import ZoneInfo

API = "http://127.0.0.1:8000"
TZ  = "America/Phoenix"

st.set_page_config(page_title="Life Copilot", layout="wide")
st.title("Life Copilot")

# ───────────────────────────────── Sidebar: API health
with st.sidebar:
    st.markdown("### API Health")
    try:
        r = requests.get(f"{API}/health", timeout=3)
        st.success("API OK ✅" if r.ok and r.json().get("ok") else "API responded but not OK")
    except Exception as e:
        st.error(f"API unreachable: {e}")

# ───────────────────────────────── Weather
st.header("Weather")
colA, colB = st.columns([1, 2], gap="large")

with colA:
    if st.button("Fetch weather"):
        try:
            w = requests.get(f"{API}/weather", timeout=10).json()
            if "temp_now" in w:
                st.metric("Now (Temp)", f"{w['temp_now']}°")
                st.metric("UV Index", w.get("uv_now", "–"))
                st.caption(f"Latency: {w.get('latency_ms', '–')} ms")
                st.session_state["_weather_hourly"] = w.get("hourly", [])
            else:
                st.error("Weather payload missing expected fields.")
        except Exception as e:
            st.error(f"Weather error: {e}")

with colB:
    st.markdown("**Next 6 hours**")
    hourly = st.session_state.get("_weather_hourly", [])
    if hourly:
        st.table([{
            "Time": h.get("time", "–"),
            "Temp": f"{h.get('temp', '–')}°",
            "UV": h.get("uv", "–"),
            "Rain%": h.get("precip_prob", "–"),
        } for h in hourly])
    else:
        st.info("Click **Fetch weather** to load the next 6 hours.")

# ───────────────────────────────── Commute
st.header("Commute")
c1, c2 = st.columns([1, 2], gap="large")

with c1:
    if st.button("Check commute"):
        try:
            cm = requests.get(f"{API}/commute", timeout=10).json()
            st.session_state["_commute"] = cm
            st.metric("ETA", f"{cm['eta_min']} min")
            st.metric("Leave by", cm["leave_by"])
            st.caption(f"Latency: {cm.get('latency_ms','–')} ms")
            if cm["recommendation"]["need_reroute"]:
                st.warning(f"Alternate saves ~{cm['recommendation']['alt_save_min']} min — take alternate route.")
            else:
                st.success("Primary route is best now.")
        except Exception as e:
            st.error(f"Commute error: {e}")

with c2:
    cm = st.session_state.get("_commute")
    if cm:
        st.write("**Arrive by:**", cm["arrive_by"])
        st.write("**Buffer:**", f"{cm['buffer_minutes']} min")
        st.write("**Advice:**", "Leave now" if cm["leave_by"] <= "00:00" else f"Leave by {cm['leave_by']}")
    else:
        st.info("Click **Check commute** to load ETA/Leave-by.")

st.subheader("On-the-Way (OTW) pickups")
chips = st.columns(3)
chip_map = {0: "florist", 1: "coffee", 2: "gift shop"}

clicked = None
for idx, label in chip_map.items():
    if chips[idx].button(label.title()):
        clicked = label

if clicked:
    try:
        r = requests.get(f"{API}/places/along_route", params={"category": clicked}, timeout=25)
        data = r.json()
        st.session_state["_otw"] = (clicked, data.get("items", []))
        st.success(f"Found {len(st.session_state['_otw'][1])} {clicked} options along your route")
    except Exception as e:
        st.error(f"OTW error: {e}")

otw = st.session_state.get("_otw")
if otw:
    category, items = otw
    if not items:
        st.info(f"No {category} found along route within a short detour.")
    else:
        for idx, p in enumerate(items, 1):
            st.write(f"**#{idx} {p.get('name','(unknown)')}** — +{p.get('detour_min','?')} min detour")
            st.write(p.get("address",""))
            phone = p.get("phone")
            if phone: st.write(f"Phone: {phone}")
            links = []
            if p.get("url"): links.append(f"[Website]({p['url']})")
            if p.get("map_url"): links.append(f"[Map]({p['map_url']})")
            if links: st.markdown(" · ".join(links))

            btn_key = f"otw_rem_{category}_{idx}"
            if st.button("Add stop reminder", key=btn_key):
                cm = st.session_state.get("_commute")
                try:
                    tz = ZoneInfo(TZ)
                    now = dt.datetime.now(tz)
                    if cm and cm.get("arrive_by"):
                        today = dt.date.today()
                        ah, am = map(int, cm["arrive_by"].split(":"))
                        arrive_dt = dt.datetime(today.year, today.month, today.day, ah, am, tzinfo=tz)
                        when = arrive_dt - dt.timedelta(minutes=45)
                        if when < now: when = now + dt.timedelta(minutes=15)
                    else:
                        when = now + dt.timedelta(minutes=15)
                    when_iso = when.strftime("%Y-%m-%dT%H:%M")
                    desc = f"{p.get('name','')} — {p.get('address','')}\n{phone or ''}\n{p.get('map_url','')}"
                    resp = requests.post(f"{API}/calendar/reminder", json={
                        "summary": f"Pickup {category} — {p.get('name','')}",
                        "when": when_iso,
                        "description": desc,
                        "minutes": 10
                    }, timeout=10)
                    if resp.ok:
                        link = resp.json().get("created", {}).get("htmlLink")
                        st.success(f"Stop reminder set for {when_iso} ✅")
                        if link: st.markdown(f"[Open in Google Calendar]({link})")
                    else:
                        st.error(resp.text)
                except Exception as e:
                    st.error(f"Reminder error: {e}")
# ───────────────────────────────── Calendar
st.header("Calendar")
col1, col2 = st.columns([1,2], gap="large")

with col1:
    if st.button("Connect Google Calendar"):
        try:
            r = requests.get(f"{API}/calendar/connect", timeout=60)
            if r.ok:
                st.success(f"Connected: {r.json().get('primary','primary')}")
            else:
                st.error(r.text)
        except Exception as e:
            st.error(f"Auth error: {e}")

    if st.button("Load today & tomorrow events"):
        try:
            r = requests.get(f"{API}/calendar/events", timeout=10)
            st.session_state["_events"] = r.json().get("events", [])
            st.success(f"Loaded {len(st.session_state['_events'])} events")
        except Exception as e:
            st.error(f"Load error: {e}")

with col2:
    events = st.session_state.get("_events", [])
    if events:
        for e in events:
            st.write(f"**{e.get('summary','(no title)')}**  —  {e.get('start','?')}  →  {e.get('end','?')}")
    else:
        st.info("No events loaded yet.")

st.divider()
st.markdown("### Create a reminder")

with st.form("rem_form", clear_on_submit=True):
    default_time = (dt.datetime.now(ZoneInfo(TZ)) + dt.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M")
    colA, colB = st.columns(2)
    with colA:
        summary = st.text_input("Summary", "Leave by (test)")
    with colB:
        when_iso = st.text_input("When (local ISO)", default_time)
    desc = st.text_input("Description", "Commute buffer included")
    minutes = st.number_input("Popup minutes before", value=0, min_value=0, max_value=120, step=5)
    submit = st.form_submit_button("Create reminder")

if submit:
    try:
        r = requests.post(f"{API}/calendar/reminder", json={
            "summary": summary, "when": when_iso, "description": desc, "minutes": int(minutes)
        }, timeout=10)
        if r.ok:
            link = r.json()["created"].get("htmlLink", "")
            st.success(f"Reminder created. Open in Calendar: {link}")
        else:
            st.error(r.text)
    except Exception as e:
        st.error(f"Create error: {e}")

# st.header("Schedule Import")

# # CSV only (title,days,times,dates,location)
# uploaded = st.file_uploader(
#     "Upload schedule CSV (headers: title, days, times, dates, location)",
#     type=["csv"]
# )

# if uploaded is not None:
#     try:
#         files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type or "text/csv")}
#         # CSV-only ⇒ force rule parser; don't send LLM flags
#         r = requests.post(f"{API}/schedule/ingest", files=files, data={"use_llm": "false"}, timeout=60)
#         if not r.ok:
#             st.error(r.text)
#         else:
#             resp = r.json()
#             events = resp.get("proposed", [])
#             if not events:
#                 st.warning("No events recognized from the CSV. Check headers and sample rows.")
#             else:
#                 st.success(f"Parsed {len(events)} event(s). Review and edit below, then add to Calendar:")
#                 editable = []
#                 for i, e in enumerate(events, 1):
#                     col1, col2, col3 = st.columns([2,2,2])
#                     with col1:
#                         summary = st.text_input(f"Summary #{i}", e.get("summary","(no title)"), key=f"ev_s_{i}")
#                     with col2:
#                         start = st.text_input(f"Start #{i} (YYYY-MM-DDTHH:MM)", e.get("start",""), key=f"ev_st_{i}")
#                     with col3:
#                         end = st.text_input(f"End #{i} (YYYY-MM-DDTHH:MM or blank)", e.get("end","") or "", key=f"ev_en_{i}")
#                     loc = st.text_input(f"Location #{i}", e.get("location","") or "", key=f"ev_l_{i}")
#                     notes = st.text_input(f"Notes #{i}", e.get("notes","") or "", key=f"ev_n_{i}")
#                     editable.append({
#                         "summary": summary,
#                         "start": start,
#                         "end": end or None,
#                         "location": loc,
#                         "description": notes  # goes into Calendar description
#                     })

#                 confirm = st.checkbox("I reviewed and confirm these events are correct.")
#                 if st.button("Add to Google Calendar", disabled=not confirm):
#                     try:
#                         r2 = requests.post(f"{API}/schedule/commit", json={"events": editable}, timeout=90)
#                         if r2.ok:
#                             created = r2.json().get("created", [])
#                             st.success(f"Created {len(created)} event(s).")
#                             for c in created:
#                                 link = c.get("htmlLink")
#                                 if link:
#                                     st.markdown(f"- [Open event]({link})")
#                         else:
#                             st.error(r2.text)
#                     except Exception as e:
#                         st.error(f"Commit error: {e}")
#     except Exception as e:
#         st.error(f"Ingest error: {e}")

# ───────────────────────────────── Recommendations (+ Order-by reminder)
st.header("Recommendations")

# Form to fetch products
with st.form("rec_form"):
    col1, col2, col3, col4 = st.columns([2,1,1,1])
    with col1:
        q = st.text_input("Search query", "men leather belt")
    with col2:
        budget = st.number_input("Budget ($)", min_value=1.0, value=25.0, step=1.0)
    with col3:
        prime_only = st.checkbox("Prime only", value=True)
    with col4:
        deadline = st.text_input(
            "Deliver by (YYYY-MM-DD)",
            (dt.date.today() + dt.timedelta(days=2)).isoformat()
        )
    submitted = st.form_submit_button("Find top picks")

if submitted:
    try:
        resp = requests.get(f"{API}/catalog/search", params={
            "q": q,
            "budget": budget,
            "prime_only": str(prime_only).lower(),
            "deadline": deadline
        }, timeout=15)
        data = resp.json()
        st.session_state["_recs"] = data.get("items", [])
        st.success(f"Found {len(st.session_state['_recs'])} items")
    except Exception as e:
        st.error(f"Catalog error: {e}")

# Render recommendations (with order-by buttons)
recs = st.session_state.get("_recs", [])
if not recs:
    st.info("Use the form above to search for products.")
else:
    for i, it in enumerate(recs, start=1):
        st.subheader(f"#{i}  {it.get('title','')}")
        c1, c2 = st.columns([1,3])
        with c1:
            if it.get("image"):
                st.image(it["image"])
        with c2:
            st.write(f"**Price:** ${it.get('price','?')}  ·  **Prime:** {it.get('prime')}")
            st.write(f"**Rating:** {it.get('rating','?')}  ·  **Reviews:** {it.get('reviews','?')}")
            st.write(f"**Est. delivery:** {it.get('delivery_days','?')} day(s)")
            sc = it.get("scores", {})
            st.write(f"**Scores** — total: {sc.get('total','?')}  "
                     f"(quality {sc.get('quality','?')}, delivery {sc.get('delivery','?')}, "
                     f"value {sc.get('value','?')}, match {sc.get('match','?')})")
            if it.get("url"):
                st.markdown(f"[View on Amazon]({it['url']})")

            # Order-by button (now variables are in scope)
            btn_key = f"order_btn_{i}_{it.get('asin','noasin')}"
            if st.button("Add Order-by reminder", key=btn_key):
                try:
                    resp2 = requests.post(f"{API}/catalog/order_reminder", json={
                        "title": it.get("title"),
                        "url": it.get("url"),
                        "delivery_days": it.get("delivery_days"),   # may be None
                        "deadline": deadline or None                # from the form above
                    }, timeout=10)
                    if resp2.ok:
                        data_resp = resp2.json()
                        st.success(f"Order-by reminder set for {data_resp.get('when')}  ✅")
                        link = data_resp.get("created", {}).get("htmlLink")
                        if link:
                            st.markdown(f"[Open in Google Calendar]({link})")
                    else:
                        st.error(resp2.text)
                except Exception as e:
                    st.error(f"Reminder error: {e}")

import datetime as dt
from zoneinfo import ZoneInfo

st.header("Planner (Phase 6)")

# Build a tiny weather brief from your loaded weather (optional)
events = st.session_state.get("_events", [])
hourly = st.session_state.get("_weather_hourly", [])
weather_brief = ""
if hourly:
    nowh = hourly[0]
    weather_brief = f"Now {nowh.get('temp','?')}°F, UV {nowh.get('uv','?')}, rain {nowh.get('precip_prob','?')}%."

colp1, colp2 = st.columns([1,2])
with colp1:
    if st.button("Make a plan from my events"):
        try:
            r = requests.post(f"{API}/agent/plan",
                              json={"events": events, "weather_brief": weather_brief},
                              timeout=40)
            st.session_state["_plan"] = r.json().get("plan", {})
            st.success("Plan ready.")
        except Exception as e:
            st.error(f"Plan error: {e}")

plan = st.session_state.get("_plan", {})
with colp2:
    if plan:
        st.write(f"**Scenario:** {plan.get('scenario')}")
        st.write(f"**Event:** {plan.get('event_title','')} @ {plan.get('event_time','?')}")
        if plan.get("venue"):
            st.write(f"**Venue:** {plan['venue']}")
        st.write("**Checklist**")
        st.write(plan.get("checklist", []))
        st.write("**Questions**")
        questions = plan.get("questions", [])
        answers = {}
        for i, q in enumerate(questions):
            # if q is a dict, get first string field
            if isinstance(q, dict):
                # try "text" or just stringify the whole dict
                q = q.get("text") or str(q)
            elif not isinstance(q, str):
                q = str(q)

            ql = q.lower()
            if any(tok in ql for tok in ["budget","amount","$"]):
                answers[q] = st.number_input(q, min_value=1, value=25, step=1, key=f"qnum_{i}")
            elif ql.startswith("do "):
                answers[q] = st.checkbox(q, key=f"qyn_{i}")
            else:
                answers[q] = st.text_input(q, key=f"qtxt_{i}")
        st.session_state["_answers"] = answers

# Act
if plan:
    if st.button("Get picks & OTW based on my answers"):
        try:
            r = requests.post(f"{API}/agent/act", json={
                "plan": plan,
                "answers": st.session_state.get("_answers", {}),
                "use_otw": True
            }, timeout=60)
            st.session_state["_act"] = r.json()
            st.success("Action results loaded.")
        except Exception as e:
            st.error(f"Act error: {e}")

act = st.session_state.get("_act")
if act:
    st.subheader("Top recommendation(s)")
    for rec in act.get("recommendations", []):
        st.write(f"**{rec.get('title','')}** — ${rec.get('price','?')} · Prime {rec.get('prime')}")
        sc = rec.get("scores", {})
        st.caption(f"Score {sc.get('total','?')} (quality {sc.get('quality','?')}, delivery {sc.get('delivery','?')})")
        if rec.get("url"):
            st.markdown(f"[Amazon]({rec['url']})")
        # Reuse the order-by button you built
        if st.button("Add Order-by reminder", key=f"agent_order_{rec.get('asin','noasin')}"):
            try:
                deadline = (plan.get("event_time","") or "")[:10] or None
                resp2 = requests.post(f"{API}/catalog/order_reminder", json={
                    "title": rec.get("title"),
                    "url": rec.get("url"),
                    "delivery_days": rec.get("delivery_days"),
                    "deadline": deadline
                }, timeout=10)
                if resp2.ok:
                    when = resp2.json().get("when")
                    st.success(f"Order-by reminder set for {when} ✅")
                else:
                    st.error(resp2.text)
            except Exception as e:
                st.error(f"Reminder error: {e}")

    st.subheader("On-the-Way (OTW) suggestions")
    for p in act.get("otw", []):
        st.write(f"**{p.get('name','')}** — +{p.get('detour_min','?')} min detour")
        st.write(p.get("address",""))
        if p.get("phone"):
            st.write(f"Phone: {p['phone']}")
        links = []
        if p.get("url"): links.append(f"[Website]({p['url']})")
        if p.get("map_url"): links.append(f"[Map]({p['map_url']})")
        if links:
            st.markdown(" · ".join(links))
st.header("Daily Brief")

colb1, colb2 = st.columns([1,2])

with colb1:
    run_now = st.button("Run brief now")
    set_time = st.text_input("Daily time (HH:MM)", "07:00")
    enable_brief = st.checkbox("Enable daily brief", value=True)
    if st.button("Save brief schedule"):
        try:
            r = requests.post(f"{API}/brief/config", json={"time": set_time, "enabled": enable_brief}, timeout=10)
            if r.ok:
                st.success("Brief schedule saved.")
            else:
                st.error(r.text)
        except Exception as e:
            st.error(f"Save error: {e}")

with colb2:
    if run_now:
        try:
            r = requests.post(f"{API}/brief/run", json={"create_leave_event": True}, timeout=90)
            if r.ok:
                data = r.json()
                st.success("Brief ready.")
                st.markdown("#### Report")
                st.code(data.get("report_md",""), language="markdown")
                if data.get("report_path"):
                    st.caption(f"Saved → {data['report_path']}")
                if data.get("created_leave"):
                    st.caption("Added 'Leave by' reminder to Calendar.")
            else:
                st.error(r.text)
        except Exception as e:
            st.error(f"Brief error: {e}")