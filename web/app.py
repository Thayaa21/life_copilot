import streamlit as st
import requests

st.title("Health Check")

try:
    response = requests.get("http://localhost:8000/health")
    if response.status_code == 200 and response.json().get("status") == "ok":
        st.success("API is reachable and healthy! ✅")
    else:
        st.error("API responded, but status is not OK.")
except Exception as e:
    st.error(f"Could not reach API: {e}")