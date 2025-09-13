# 🧭 Life Copilot

**Life Copilot** is a personal assistant platform that connects weather, commute, calendar, shopping, and planning into one streamlined daily workflow.  
It combines **real APIs**, **LLM planning (Ollama)**, and **Google Calendar integration** into a unified dashboard.

---

## ✨ Features

- **Weather**: Real-time forecast + hourly outlook (via open weather APIs).
- **Commute**: Home → Office ETA, leave-by time, alternate route check.
- **On-the-Way Stops (OTW)**: Find coffee shops, florists, gift shops along your commute (free OSM + Mapbox).
- **Calendar**: 
  - Connect your Google Calendar  
  - View today & tomorrow’s events  
  - Add reminders and event commits
- **Product Catalog**: 
  - Search Amazon (Rainforest API)  
  - Smart scoring (quality, value, delivery, match)  
  - “Order by” reminders created in Calendar
- **Planner (Phase 6)**:  
  - LLM (Ollama by default) analyzes your events + weather → creates a **scenario plan, checklist, and questions**  
  - Action layer suggests Amazon gifts and OTW stops
- **Schedule Import**:  
  - Upload CSV/TXT/ICS/PDF/Images of your class/office schedule  
  - Rule-based parser or LLM-based parsing (Ollama)  
  - Review → Commit into Google Calendar
- **Daily Brief (Phase 7)**:  
  - Auto-generated report every morning (Markdown)  
  - Includes Weather, Commute, First 3 Events, Plan, OTW, Picks  
  - Saves to `data/reports/brief-YYYYMMDD.md`  
  - Optionally creates **“Leave by” reminder** in Google Calendar  
  - Configurable daily time via API/UI (default 07:00 local)

---

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python 3.11+)
- **Frontend**: Streamlit
- **LLM**: [Ollama](https://ollama.ai/) (local), optional HuggingFace/Groq later
- **Scheduler**: APScheduler (daily brief automation)
- **APIs**:  
  - Weather (open/free)  
  - Commute (Mapbox/OSM)  
  - Amazon Catalog (Rainforest API)  
  - Google Calendar API (OAuth2)

---

## 📂 Project Structure