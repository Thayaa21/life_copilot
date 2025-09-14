# 🧭 Life Copilot

**Life Copilot** is your intelligent daily assistant that transforms how you prepare for and manage your day. It's like having a personal concierge that analyzes your calendar, weather, commute, and upcoming events to provide proactive recommendations, reminders, and essential preparations.

## 🎯 What Life Copilot Does

Life Copilot acts as your daily preparation partner by:

- **📅 Calendar Intelligence**: Connects to your Google Calendar and analyzes upcoming events
- **🌤️ Weather-Aware Planning**: Considers weather conditions for outdoor events and commutes  
- **🚗 Smart Commute Management**: Calculates optimal departure times and suggests on-the-way stops
- **🛍️ Proactive Shopping**: Identifies what you need for special occasions and finds the best products
- **📱 Automated Reminders**: Creates calendar reminders for purchases, departures, and preparations
- **🤖 AI-Powered Insights**: Uses LLM to understand event context and provide tailored recommendations

## 🌟 Key Features

### 📊 **Daily Brief System**
- **Automated Morning Reports**: Generated every morning at 7:00 AM (configurable)
- **Comprehensive Overview**: Weather, commute times, first 3 events, and personalized plans
- **Smart Reminders**: Automatically creates "Leave by" reminders in your calendar
- **Markdown Reports**: Saves detailed reports to `data/reports/brief-YYYYMMDD.md`

### 🎯 **Event-Specific Intelligence**
- **Date Night Planning**: Suggests flowers, restaurants, and romantic stops along your route
- **Interview Preparation**: Recommends professional attire, accessories, and preparation items
- **Birthday Party Prep**: Identifies gifts, decorations, and party essentials
- **Outdoor Event Planning**: Considers weather and suggests appropriate gear
- **Generic Meeting Support**: Provides standard preparation checklists

### 🛒 **Smart Shopping Integration**
- **Amazon Product Search**: Finds the best products using Rainforest API
- **Intelligent Scoring**: Evaluates products on quality, value, delivery speed, and relevance
- **Order-by Reminders**: Automatically calculates when to order items for timely delivery
- **Budget-Aware Recommendations**: Considers your budget preferences and event timing

### 🗺️ **On-the-Way (OTW) Stops**
- **Route-Optimized Suggestions**: Finds coffee shops, florists, gift shops along your commute
- **Detour Analysis**: Shows how much extra time each stop adds to your journey
- **Contact Information**: Provides phone numbers and addresses for easy calling/ordering
- **Calendar Integration**: Can add stop reminders directly to your calendar

### 📅 **Calendar Management**
- **Google Calendar Integration**: Full OAuth2 integration with your calendar
- **Event Analysis**: Understands event context and timing
- **Smart Reminders**: Creates contextual reminders based on event type
- **Schedule Import**: Upload and parse various schedule formats (CSV, PDF, images)

### 🌤️ **Weather Integration**
- **Real-time Conditions**: Current temperature, UV index, and precipitation
- **Hourly Forecasts**: Next 6 hours of weather data
- **Event Planning**: Weather-aware recommendations for outdoor activities
- **Commute Planning**: Considers weather impact on travel times

## 🎬 Real-World Use Cases

### 💕 **Date Night Scenario**
*"I have a dinner date at 7 PM at a fancy restaurant downtown"*

**What Life Copilot does:**
1. **Analyzes the event**: Identifies it as a romantic dinner
2. **Checks weather**: "It's 75°F and sunny - perfect for the outdoor seating area"
3. **Calculates commute**: "Leave by 6:15 PM to arrive on time (45 min drive)"
4. **Suggests preparations**: 
   - "Order flowers by 2 PM today" → Creates calendar reminder
   - "Pick up flowers at Rose Garden Florist (+8 min detour, call 555-0123)"
   - "Consider a nice bottle of wine from Wine & Spirits (+5 min detour)"
5. **Creates reminders**: "Leave by 6:15 PM" automatically added to calendar

### 💼 **Job Interview Scenario**
*"I have a job interview tomorrow at 2 PM at TechCorp"*

**What Life Copilot does:**
1. **Identifies the event type**: Professional interview
2. **Recommends essentials**:
   - "Professional leather belt - $25, Prime delivery by tomorrow"
   - "Portfolio folder - $12, same-day delivery available"
   - "Tie clip - $15, order by 6 PM today"
3. **Weather considerations**: "Partly cloudy, 68°F - perfect for a blazer"
4. **Route planning**: "Leave by 1:15 PM (30 min drive + 15 min buffer)"
5. **OTW suggestions**: "Coffee shop 2 blocks from interview location for pre-interview coffee"

### 🎂 **Birthday Party Scenario**
*"My daughter's birthday party is this Saturday at 3 PM"*

**What Life Copilot does:**
1. **Party planning mode**: Identifies birthday celebration
2. **Gift recommendations**:
   - "Age-appropriate toys and games"
   - "Party decorations and balloons"
   - "Cake decorations and candles"
3. **Weather planning**: "Sunny, 78°F - perfect for outdoor party games"
4. **Shopping timeline**: "Order decorations by Thursday for Saturday delivery"
5. **OTW stops**: "Party City on your way home (+12 min detour) for last-minute items"

### 🏃 **Outdoor Event Scenario**
*"I have a 5K run this Sunday morning at 8 AM"*

**What Life Copilot does:**
1. **Weather analysis**: "Cool morning, 55°F - perfect running weather"
2. **Gear recommendations**:
   - "Moisture-wicking running shirt - $18, Prime delivery"
   - "Energy gels for race day - $12, order by Friday"
3. **Preparation reminders**: "Lay out running clothes tonight"
4. **Route planning**: "Leave by 7:30 AM (20 min drive to start line)"
5. **Post-race planning**: "Coffee shop near finish line for post-race celebration"

## 🔄 Daily Workflow

### 🌅 **Morning Routine (7:00 AM)**
1. **Daily Brief Generated**: Comprehensive report with weather, commute, and first 3 events
2. **Leave-by Reminder**: Automatically calculated and added to calendar
3. **Event Analysis**: AI reviews upcoming events and suggests preparations
4. **Shopping Alerts**: Notifications for items that need to be ordered today

### 🚗 **Commute Time**
1. **Real-time Traffic**: Current ETA and optimal departure time
2. **OTW Suggestions**: Coffee shops, florists, or gift shops along your route
3. **Weather Updates**: Current conditions and hourly forecast
4. **Event Reminders**: Last-minute preparations for today's events

### 🛍️ **Shopping & Preparation**
1. **Smart Product Search**: AI finds the best items for your specific needs
2. **Order Timing**: Calculates when to order items for timely delivery
3. **Calendar Integration**: Shopping reminders automatically added to calendar
4. **Budget Management**: Considers your spending preferences and event budgets

### 📅 **Event Day**
1. **Final Reminders**: Last-minute preparations and departure times
2. **Weather Check**: Current conditions and any weather-related adjustments
3. **OTW Navigation**: Real-time suggestions for stops along your route
4. **Post-Event**: Follow-up reminders and preparation for next events

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

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.ai/) installed and running
- Google Calendar API credentials
- Mapbox API key (for commute routing)
- Rainforest API key (for Amazon product search)
- OpenWeather API key (for weather data)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd life_copilot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   Create a `.env` file in the project root:
   ```env
   # API Keys
   OPENWEATHER_API_KEY=your_openweather_key
   MAPBOX_ACCESS_TOKEN=your_mapbox_token
   RAINFOREST_API_KEY=your_rainforest_key
   
   # Google Calendar (will be set up during first run)
   GOOGLE_CREDENTIALS_FILE=data/google_token.json
   
   # Location (default to Phoenix, AZ)
   DEFAULT_LAT=33.424
   DEFAULT_LON=-111.928
   
   # Daily Brief Settings
   BRIEF_ENABLED=true
   BRIEF_TIME=07:00
   ```

4. **Configure your profile**
   Create `data/profile.json`:
   ```json
   {
     "user_role": "student",
     "default_gift_budget": 30,
     "default_interview_budget": 25,
     "prime_preferred": true,
     "lat": 33.424,
     "lon": -111.928
   }
   ```

5. **Set up commute configuration**
   Create `data/commute.json`:
   ```json
   {
     "home": {"lat": 33.424, "lon": -111.928},
     "office": {"lat": 33.448, "lon": -111.928},
     "arrive_by": "09:00",
     "buffer_minutes": 10
   }
   ```

6. **Start the services**
   ```bash
   # Terminal 1: Start the API server
   uvicorn api.main:app --reload --port 8000
   
   # Terminal 2: Start the web interface
   streamlit run web/app.py --server.port 8501
   ```

7. **Access the application**
   - Web Interface: http://localhost:8501
   - API Documentation: http://localhost:8000/docs

### First-Time Setup

1. **Connect Google Calendar**: Click "Connect Google Calendar" in the web interface
2. **Test Weather**: Click "Fetch weather" to verify weather API
3. **Test Commute**: Click "Check commute" to verify routing
4. **Run Daily Brief**: Click "Run brief now" to generate your first report

## 📂 Project Structure

```
life_copilot/
├── api/                    # FastAPI backend
│   ├── main.py            # Main API server
│   ├── agent.py           # LLM planning and decision making
│   ├── brief.py           # Daily brief generation
│   ├── llm.py             # LLM integration (Ollama)
│   ├── scoring.py         # Product scoring algorithm
│   ├── tools_*.py         # API integrations (weather, commute, calendar, etc.)
│   └── schedule_*.py      # Schedule parsing and import
├── web/                   # Streamlit frontend
│   └── app.py             # Main web interface
├── data/                  # Configuration and data storage
│   ├── profile.json       # User profile and preferences
│   ├── commute.json       # Home/office locations and commute settings
│   ├── google_token.json  # Google Calendar OAuth tokens
│   └── reports/           # Generated daily briefs
├── agent/                 # LangGraph agent components
│   ├── graph.py           # Agent workflow graph
│   └── prompts.py         # LLM prompts and templates
└── requirements.txt       # Python dependencies
```

## 🔧 Configuration

### Daily Brief Settings
- **Time**: Configure when the daily brief is generated (default: 7:00 AM)
- **Enable/Disable**: Turn daily brief on or off
- **Leave-by Reminders**: Automatically create calendar reminders for departure times

### Event Scenarios
The system recognizes these event types and provides tailored recommendations:
- `dinner_date` - Romantic dinner planning
- `child_birthday` - Birthday party preparation  
- `interview` - Job interview preparation
- `morning_commute` - Standard work commute
- `generic_meeting` - Business meeting preparation
- `outdoor_event` - Weather-dependent outdoor activities

### Shopping Preferences
- **Budget Defaults**: Set default budgets for different event types
- **Prime Preference**: Prefer Amazon Prime eligible items
- **Delivery Timing**: Calculate optimal order times for event deadlines

## 🤖 AI Integration

### LLM Configuration
- **Default**: Ollama (local, privacy-focused)
- **Models**: Supports various Ollama models
- **Fallback**: Graceful degradation if LLM is unavailable

### Planning Intelligence
- **Event Analysis**: Understands event context and requirements
- **Weather Integration**: Considers weather in all recommendations
- **Timing Optimization**: Calculates optimal order and departure times
- **Route Planning**: Suggests efficient stops along commute routes

## 📱 API Endpoints

### Core Services
- `GET /weather` - Current weather and hourly forecast
- `GET /commute` - Commute times and route optimization
- `GET /calendar/events` - Today and tomorrow's calendar events
- `POST /calendar/reminder` - Create calendar reminders

### Planning & Recommendations
- `POST /agent/plan` - Generate event-specific plans
- `POST /agent/act` - Get product recommendations and OTW stops
- `GET /catalog/search` - Search Amazon products
- `POST /catalog/order_reminder` - Create order-by reminders

### Daily Brief
- `POST /brief/run` - Generate daily brief immediately
- `POST /brief/config` - Configure daily brief settings

### Schedule Import
- `POST /schedule/ingest` - Upload and parse schedule files
- `POST /schedule/commit` - Add parsed events to calendar

## 🔒 Privacy & Security

- **Local LLM**: Ollama runs locally, keeping your data private
- **OAuth2**: Secure Google Calendar integration
- **No Data Storage**: Personal data is not stored permanently
- **API Keys**: All external API keys are environment variables

## 🐛 Troubleshooting

### Common Issues
1. **Ollama not running**: Start Ollama service before running the application
2. **API keys missing**: Ensure all required API keys are in your `.env` file
3. **Calendar connection failed**: Check Google Calendar API credentials
4. **Weather data unavailable**: Verify OpenWeather API key and location settings

### Debug Mode
Enable debug logging by setting `DEBUG=true` in your `.env` file.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Life Copilot** - Your intelligent daily preparation assistant. Never be unprepared for life's important moments again! 🚀