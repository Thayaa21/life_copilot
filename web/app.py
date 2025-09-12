import requests, streamlit as st

st.set_page_config(page_title="Life Copilot", layout="wide")
st.title("Life Copilot — Phase 2: Weather")

with st.sidebar:
    st.markdown("### API Health")
    try:
        r = requests.get("http://127.0.0.1:8000/health", timeout=3)
        st.success("API OK ✅" if r.ok and r.json().get("ok") else "API responded but not OK")
    except Exception as e:
        st.error(f"API unreachable: {e}")

st.markdown("## Weather")

colA, colB = st.columns([1, 2], gap="large")

with colA:
    if st.button("Fetch weather"):
        try:
            w = requests.get("http://127.0.0.1:8000/weather", timeout=10).json()
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
        # display as simple table
        st.table([{
            "Time": h.get("time", "–"),
            "Temp": f"{h.get('temp', '–')}°",
            "UV": h.get("uv", "–"),
            "Rain%": h.get("precip_prob", "–"),
        } for h in hourly])
    else:
        st.info("Click **Fetch weather** to load the next 6 hours.")
import streamlit as st, requests

st.markdown("## Commute")

c1, c2 = st.columns([1, 2], gap="large")

with c1:
    if st.button("Check commute"):
        try:
            cm = requests.get("http://127.0.0.1:8000/commute", timeout=10).json()
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
        st.write("**Advice:**",
                 "Leave now" if cm["leave_by"] <= "00:00" else f"Leave by {cm['leave_by']}")
    else:
        st.info("Click **Check commute** to load ETA/Leave-by.")