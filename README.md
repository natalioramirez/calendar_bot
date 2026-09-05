# 🗓 Telegram Team Calendar & Reminder Bot

A modern, async Telegram bot built in Python to help work teams coordinate schedules, register important dates, organize multiple shared or personal calendars, attach rich notes, and receive automated reminder notifications with optional Google Calendar synchronization.

---

## ✨ Key Features

The bot itself is deliberately tiny: users **subscribe to a calendar**, **see upcoming
dates**, **add a date**, and **get alerts**. Nothing else. Everything administrative —
creating calendars, managing members, bulk event edits — happens in the web panel.

- 🔔 **Subscribe & get alerted**: `/sub` lists the available calendars; pick one and the
  bot sends you its reminders automatically. `/unsub` stops them.
- 📅 **See upcoming dates**: `/events` prints your next dates in a single plain list.
- ➕ **Add a date**: `/nuevo` walks you through calendar → date → title in three steps.
- 📝 **Rich Event Notes**: Agendas, meeting links, and descriptions are attached to events
  in the panel and shown alongside each date.
- 🖥 **Web Administration Panel**: All administration tasks (calendars, members, events, Islamic holiday sync) are done from a local Flask panel — there are no admin commands in the bot.
- 🔄 **Google Calendar Integration**: *Currently inactive* — the service client still lives in
  `bot/services/google_calendar.py`, but nothing calls it since event creation was removed
  from the bot. Re-wire it from the web panel if you need the push again.

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
│   │   ├── start.py           # /start: registers the user and lists the commands
│   │   ├── subscriptions.py   # /sub and /unsub
│   │   ├── create_event.py    # /nuevo: the 3-step event creation flow
│   │   └── events.py          # /events: the upcoming dates list
│   ├── keyboards/
│   │   └── common.py          # The calendar picker used by /sub and /unsub
│   ├── services/
│   │   ├── scheduler.py       # Background reminder checker & dispatcher
│   │   └── google_calendar.py # Google Calendar API v3 client
│   ├── utils/
│   │   └── datetime_utils.py  # Simple date & time parsing and formatting
│   └── main.py                # Bot application setup & runner
├── web/
│   ├── app.py                 # Flask web administration panel (the only admin interface)
│   └── templates/             # Panel pages (dashboard, calendars, members, events)
├── run.py                     # Single entry point: starts the bot + the web panel
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

### 5. Run the Bot + Admin Panel
A single command starts both the Telegram bot and the web administration panel:
```bash
python run.py
```
- 🤖 The bot starts polling — open it on Telegram and send `/start`.
- 🖥 The admin panel is served at **http://127.0.0.1:5314**.

Press `Ctrl+C` once to stop both services.

The host and port come from `WEB_ADMIN_HOST` / `WEB_ADMIN_PORT` in your `.env`.
The panel binds to `127.0.0.1`, so it is reachable only from this machine — it has
no login, so do not expose it on a public interface.

> Each service runs as its own process because both need a separate asyncio event
> loop; SQLite runs in WAL mode, so concurrent access from both is safe.
> You can still run them individually with `python -m bot.main` and `python -m web.app`.

---

## 🧪 Running Automated Tests

```bash
.venv/bin/pytest -v
```

---

## 📖 Bot Commands & Usage

The bot has four commands (plus `/cancel`) and no persistent menus:

| Command | Description |
| :--- | :--- |
| `/start` | Registers you and shows this list |
| `/sub` | Lists the calendars you are not subscribed to; tap one to subscribe |
| `/unsub` | Lists your calendars; tap one to stop its alerts |
| `/events` | Your upcoming dates, across every calendar you follow |
| `/nuevo` | Creates an event: pick a calendar, type the date, type the title |
| `/cancel` | Aborts `/nuevo` halfway through |

Alerts arrive on their own — there is nothing to configure.

### About `/nuevo`

Any subscriber can add a date to a calendar they follow — there is no admin role in the
bot. The event alerts **at its start time and one hour before**, for every subscriber of
that calendar; those timings are fixed (`DEFAULT_REMINDER_OFFSETS` in
`bot/handlers/create_event.py`). Dates in the past are rejected, since their reminders
would fire immediately.

Users still cannot create or delete *calendars* from the bot, and there are **no admin
commands** — that lives in the web panel.

---

## 🖥 Web Administration Panel

Served at **http://127.0.0.1:5314** (started by `python run.py`).

| Page | What you can do |
| :--- | :--- |
| **Dashboard** | Overview stats, upcoming events, and a manual *Islamic holiday sync* trigger |
| **Calendars** | Create and delete calendars, view invite codes |
| **Members** | Assign users to calendars, change roles, remove members |
| **Events** | Create and delete events in any calendar, filter by calendar |

Automatic Islamic holiday sync still runs by itself inside the bot process (on startup
and monthly); the panel button is for triggering it on demand.

### Avoiding API calls on every startup

By default the bot syncs Islamic holidays a few seconds after booting, which hits the
AlAdhan API each time it starts. To turn that off, set in your `.env`:

```env
CALLS_ON_BOOT=false
```

The monthly scheduled sync and the panel's manual sync button keep working — only the
startup call is skipped.

---

## 🔗 Google Calendar Setup (Optional, currently unused)

> ⚠️ Nothing calls the Google Calendar client right now. Events used to be pushed when the
> bot's creation wizard finished, and that wizard was removed when the bot was simplified.
> The steps below still describe how to configure the credentials if you wire it back up.

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
