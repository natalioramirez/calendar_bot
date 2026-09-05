# 🗓 Telegram Team Calendar & Reminder Bot

A modern, async Telegram bot built in Python to help work teams coordinate schedules, register important dates, organize multiple shared or personal calendars, attach rich notes, and receive automated reminder notifications with optional Google Calendar synchronization.

---

## ✨ Key Features

- 📅 **Register & Schedule Important Dates**: Interactive wizard to add events with dates and times.
- 🗂 **Multiple Calendars**: Create separate calendars for different teams, projects, or categories (e.g., *Engineering*, *Marketing*, *Client Deadlines*).
- 🔗 **Easy Team Onboarding**: Invite teammates using a unique invite code or 1-click invite link (`https://t.me/YourBot?start=join_CODE`).
- 📝 **Rich Event Notes**: Attach agendas, meeting links, checklist items, and descriptions directly to events.
- 🔔 **Automated Reminder Notifications**:
  - Configurable alert timings: *At event time*, *15 minutes before*, *1 hour before*, *1 day before*.
  - Dispatches reminder notifications directly to all enrolled team members.
  - Per-calendar notification mute/unmute toggles.
- 🔄 **Google Calendar Integration**: Optional sync with Google Calendar API (via Service Account).

---

## 🏗 Architecture & Code Structure

```
tg_calendar/
├── bot/
│   ├── config.py              # Environment settings & configuration (pydantic-settings)
│   ├── database/
│   │   ├── models.py          # SQLAlchemy ORM models (User, Calendar, Member, Event, Reminder)
│   │   ├── session.py         # Async SQLite / PostgreSQL session factory
│   │   └── crud.py            # Database queries and operations
│   ├── handlers/
│   │   ├── start.py           # /start, /help, and invite code handling
│   │   ├── calendars.py       # Calendar creation, switching, membership, invite links
│   │   └── events.py          # Event creation wizard, notes editing, listing, deletion
│   ├── keyboards/
│   │   ├── common.py          # Main reply keyboard & navigation buttons
│   │   └── calendar_picker.py # Inline keyboards for calendars, dates, times, and reminders
│   ├── services/
│   │   ├── scheduler.py       # Background reminder checker & dispatcher
│   │   └── google_calendar.py # Google Calendar API v3 client
│   ├── utils/
│   │   └── datetime_utils.py  # Simple date & time parsing and formatting
│   └── main.py                # Bot application setup & runner
├── tests/                     # Automated pytest suite
├── .env.example               # Environment variables template
├── requirements.txt           # Python dependencies
└── pytest.ini                 # Pytest configuration
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10+ installed
- A Telegram account

### 2. Create your Telegram Bot Token
1. Open Telegram and search for [@BotFather](https://t.me/BotFather).
2. Send `/newbot` and follow the prompts to choose a name and username for your bot.
3. BotFather will provide you with an API token (e.g., `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`).

### 3. Setup Virtual Environment & Install Dependencies
```bash
# Clone or navigate to the repository
cd tg_calendar

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Open `.env` and set your `BOT_TOKEN`:
```env
BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
```

### 5. Run the Bot
```bash
python -m bot.main
```
Open your bot on Telegram and send `/start`!

---

## 🧪 Running Automated Tests

```bash
.venv/bin/pytest -v
```

---

## 📖 Bot Commands & Usage

| Command | Button Equivalent | Description |
| :--- | :--- | :--- |
| `/start` | - | Registers user, shows dashboard, or joins a calendar via link |
| `/new` | `➕ New Event` | Interactive wizard to schedule a new date/event with notes |
| `/events` | `📅 Upcoming Dates` | View all upcoming events across your calendars |
| `/calendars` | `🗂 My Calendars` | Manage team calendars, create new ones, share invite codes |
| `/help` | `❓ Help & Info` | Detailed instructions and tips |

---

## 🔗 Google Calendar Setup (Optional)

To sync bot events with a shared Google Calendar:
1. Create a project in the [Google Cloud Console](https://console.cloud.google.com/).
2. Enable the **Google Calendar API**.
3. Create a **Service Account** and download the JSON key file (save it to e.g. `credentials/service_account.json`).
4. Share your Google Calendar with the service account's email (found in the JSON file) with *Make changes to events* permission.
5. In `.env`, set:
   ```env
   GOOGLE_SERVICE_ACCOUNT_FILE=credentials/service_account.json
   GOOGLE_CALENDAR_ID=your_calendar_id@group.calendar.google.com
   ```
