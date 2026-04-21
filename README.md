# Ariflow Bot — Agile Workflow Optimization

A Telegram bot that manages robotics factory shift operations: operator check-in with personalised briefings, sick-leave reallocation, safety rules acknowledgment, training slot coordination, and ad-hoc announcements.

Built as a portfolio project demonstrating agent-based workflow automation and GRC skills — specifically role-based access control, capability-gated reallocation, change approval workflows, safety acknowledgment tracking, and a full audit trail — modeled on operational patterns in a physical AI / robotics environment.

> **Privacy note**: Operator names and station identifiers in the sample data (`data/`) are fully anonymised — fictional names and generic codes are used in place of real individuals or proprietary terminology. The operational logic reflects genuine patterns from a robotics assembly environment.

---

## What Problem This Solves

In a robotics assembly facility, every shift involves:
- 30–40 operators assigned across 18+ stations, each requiring different robot training
- 4 SOPs per operator per shift (2h each), with individual daily targets
- Staggered training slots that temporarily vacate stations
- Sick-leave events needing immediate capability-matched reallocation
- Safety rule updates that must be formally acknowledged before work begins
- A supervisor managing all of this manually via group chats, whiteboards, and spreadsheets

This bot replaces that manual coordination with a structured check-in flow, automatic SOPs briefing, capability-based reallocation, QR-code acknowledgment, and a full audit trail.

---

## Architecture

```
Telegram Bot (ariflow_bot)
        ↓
Orchestrator  — validates input, guards schedule state, routes to agents
        ↓
┌───────────────────────────────────────────────────────────────┐
│ Agent 1: CSV Parser        — loads the shift schedule         │
│ Agent 2: Daily Briefing    — check-in QR + personalised briefs│
│ Agent 3: Sick Leave        — capability-matched reallocation  │
│ Agent 4: Rules Ack         — QR code + acknowledgment tracking│
│ Agent 5: Shift Coordinator — training slots + station swaps   │
└───────────────────────────────────────────────────────────────┘
        ↓
state.py  — in-memory shift state (resets on new CSV upload)
```

---

## Commands

### Supervisor

**Shift start**
| Command | What it does |
|---|---|
| Upload `.csv` file | Loads the shift schedule — do this first |
| `/entry_qr` | Generates the entrance QR code to post at the door |
| `/announce [text]` | Adds an announcement to all subsequent briefings |
| `/remove_announcement [number]` | Removes a specific announcement by number |

**During shift**
| Command | What it does |
|---|---|
| `/dashboard` | Live shift overview — auto-refreshes every 30s |
| `/sick [name]` | Marks operator absent, finds compatible replacement, notifies them |
| `/trn_start [name]` | Operator starts training slot; finds temporary cover |
| `/trn_end [name]` | Operator returns; releases cover back to standby |
| `/swap [name1] [name2]` | Requests a station swap |
| `/approve_swap [id]` | Approves a pending swap |

**Safety**
| Command | What it does |
|---|---|
| `/update [rules text]` | Issues a safety rules update and generates acknowledgment QR code |
| `/ack_status` | Shows who has and hasn't acknowledged the latest rules update |

### Operator

| Action | What it does |
|---|---|
| Scan entrance QR code | Check in and instantly receive your personalised shift briefing |

---

## Operator Check-in Flow

```
Supervisor uploads CSV
        ↓
Supervisor runs /entry_qr → QR image generated
        ↓
QR posted at facility entrance
        ↓
Operator arrives → scans QR with phone → Telegram opens
        ↓
Bot identifies operator by Telegram chat ID
        ↓
Operator receives personalised briefing (station, SOPs, training slot, announcements)
```

Unassigned (standby) operators also receive a message confirming they are on standby for the shift.

---

## Briefing Message Format

Each operator receives this on check-in:

```
✅ Checked in — Good afternoon, Namyun!

📍 Station A-7 — S-Beta
⏰ Shift: 14:30 – 23:00

📋 Tasks today (2h each):
  14:30–16:30   SOP#00033   Target: 90
  16:30–18:30   SOP#00016   Target: 160
  18:30–20:30   SOP#00001   Target: 110
  20:30–22:30   SOP#00020   Target: 80

⏱ Training Slot: 17:30–18:30   SOP#00006

📢 Announcements:
  • Demo at 3:00 PM — visitors on floor, maintain station cleanliness
```

- **Tasks**: 4 SOPs assigned for the day, each lasting 2 hours, with the target count
- **Training Slot**: A scheduled break for robot handling practice; the operator leaves their station temporarily
- **Announcements**: Only shown if the supervisor has added any via `/announce`

---

## Announcements

Announcements are ad-hoc — they happen when visitors, demos, or special events occur.

```
Supervisor: /announce Demo at 3:00 PM — visitors on floor
Bot:        Announcement added (1 total): • Demo at 3:00 PM — visitors on floor

Supervisor: /announce Data quality check — submit end-of-shift report by 22:30
Bot:        Announcement added (2 total): ...
```

Announcements accumulate during the shift and appear in every briefing sent after they are added. They are cleared automatically when a new schedule CSV is loaded, or manually with `/clear_announcements`.

---

## Schedule CSV (`data/sample_schedule.csv`)

The schedule CSV is uploaded by the supervisor at the start of each shift. It is the single source of truth for all operator assignments, SOPs, and training slot times.

### Required Columns

| Column | Description | Example |
|---|---|---|
| `shift_date` | Date of the shift | `2026-04-12` |
| `operator_name` | Full name (must match `operators.json`) | `Namyun`, `Emir Aslan` |
| `station` | Station ID | `A-7`, `B-5`, `DF C-1` |
| `station_type` | Robot model at that station | `S-Beta`, `D-Alpha` |
| `shift_start` | Shift start time HH:MM | `14:30` |
| `shift_end` | Shift end time HH:MM | `23:00` |
| `trn_start` | Training slot start HH:MM | `17:30` |
| `trn_end` | Training slot end HH:MM | `18:30` |
| `trn_sop` | Training slot SOP number (plain integer) | `6` |
| `sop1` | Task 1 SOP with target | `SOP#00033(90)` |
| `sop2` | Task 2 SOP with target | `SOP#00016(160)` |
| `sop3` | Task 3 SOP with target | `SOP#00001(110)` |
| `sop4` | Task 4 SOP with target | `SOP#00020(80)` |
| `status` | `active` or `unassigned` | `active` |

### SOP Format

```
SOP#00033(90)
      │    │
      │    └── Daily target count (how many units to complete)
      └──────── SOP number (zero-padded 5 digits)
```

Target counts reflect task complexity:
- `160` — simple, repetitive task (full shift output expected)
- `80–130` — moderate complexity
- `< 80` — complex or precision task

### Training Slot SOP

The training slot SOP is a plain integer (e.g. `6`), which maps to `SOP#00006` in the briefing. It rotates weekly per the training schedule posted on the floor.

### Unassigned Operators

Operators with `status = unassigned` are on standby. Leave `station`, `trn_start`, `trn_end`, `trn_sop`, and all `sop*` columns empty.

```csv
2026-04-12,Hamish,,,14:30,23:00,,,,,,,,unassigned
```

They still receive a check-in message confirming standby status and shift hours.

### Station Types

| Code | Description |
|---|---|
| `S-Alpha` | Single-arm Alpha robot |
| `S-Beta` | Single-arm Beta robot |
| `D-Beta` | Dual-arm Beta robot |
| `D-Alpha` | Dual-arm Alpha robot |
| `S-Gamma` | Single-arm Gamma robot |
| `S-Delta` | Single-arm Delta robot |

### Two Shifts (example)

| Shift | Time | Stations |
|---|---|---|
| Morning | 06:00–14:30 | A-1 to C-5 (all stations) |
| Afternoon | 14:30–23:00 | A-1 to C-5 (all stations) |

Both shifts can be in the same CSV file — the bot loads all rows together.

---

## Capability Matrix (`data/capabilities.json`)

Maps each operator to the station types they are trained for. Used by sick-leave reallocation (Agent 3) and training slot cover (Agent 5) to find compatible replacements from the standby pool.

```json
{
  "Namyun": ["S-Beta", "S-Alpha"],
  "Hamish": ["D-Alpha", "S-Gamma", "S-Beta"]
}
```

**Matching logic**: when a station becomes vacant, the bot scans the standby pool in order and assigns the **first operator** whose capability list includes the required station type. If no match → immediate supervisor alert with station type and gap details.

Update this file whenever operator qualifications change.

---

## Operator Registry (`data/operators.json`)

Maps operator names to their Telegram chat IDs. Required for:
- Check-in identification (QR scan → chat ID → name lookup)
- Sending reallocation notifications
- Sending training slot cover requests

```json
{
  "Namyun": 0,
  "Rafael": 0
}
```

`0` means not yet registered — the bot will skip DMs and warn the supervisor.

**How to find a chat ID**: operator sends `/start` to `@ariflow_bot`. The bot logs the incoming update — look for `chat_id=XXXXXXXXX` in the console output.

---

## QR Codes

The bot generates two types of QR code images:

### 1. Entrance Check-in QR (`/entry_qr`)

Generated by supervisor at shift start. Posted at the facility entrance.

**Encodes**: `https://t.me/ariflow_bot?start=checkin`

When scanned: Telegram opens → bot receives `checkin` deep link → identifies operator by chat ID → sends personalised briefing.

One QR code serves the entire facility — each operator gets their own briefing based on their registered chat ID.

### 2. Rules Acknowledgment QR (`/update [text]`)

Generated when a safety rules update is issued.

**Encodes**: `https://t.me/ariflow_bot?start=ack_[version]`

When scanned: Telegram opens → bot records operator name + timestamp → supervisor can check `/ack_status` to see who has and hasn't acknowledged. Version increments with each `/update`, expiring old QR codes immediately.

---

## Audit Log (`logs/audit.log`)

Every significant event is written to `logs/audit.log` with a UTC timestamp:

```
[2026-04-12T06:15:00Z] SICK: Tamara absent. Pierre reallocated to B-2 (D-Alpha).
[2026-04-12T07:00:00Z] TRN_START: Serena on training slot. Camille covering B-5 (S-Gamma).
[2026-04-12T07:30:00Z] TRN_END: Serena returned to station B-5.
[2026-04-12T08:00:00Z] SWAP approved: Alonso ↔ Luca.
```

The log is append-only and does not reset between bot restarts — it persists across shifts.

---

## Project Structure

```
agile-workflow/
├── .env                     # BOT_TOKEN (never commit this)
├── .gitignore
├── requirements.txt
├── main.py                  # Entry point (asyncio.run — Python 3.12+ compatible)
├── config.py                # Token + supervisor IDs
├── state.py                 # In-memory shift state (resets on new CSV upload)
├── orchestrator.py          # Command routing + validation layer
├── agents/
│   ├── csv_parser.py        # Agent 1: parse CSV → load schedule
│   ├── daily_briefing.py    # Agent 2: entry QR + check-in + announcements
│   ├── sick_leave.py        # Agent 3: /sick + capability-matched reallocation
│   ├── rules_ack.py         # Agent 4: /update + QR + ack tracking
│   └── shift_coordinator.py # Agent 5: /trn_start /trn_end /swap
├── data/
│   ├── sample_schedule.csv  # Full shift schedule (morning + afternoon, anonymised)
│   ├── capabilities.json    # Operator → qualified station types
│   └── operators.json       # Operator name → Telegram chat ID
└── logs/
    └── audit.log            # Timestamped event log (append-only)
```

---

## Running the Bot

```bash
cd path/to/ariflow-bot
pip install -r requirements.txt
python main.py
```

Stop with `Ctrl+C`.

### Shift startup sequence

1. `python main.py` — start the bot
2. Upload `sample_schedule.csv` (or the day's actual schedule CSV) to the bot chat
3. `/announce [text]` — add any announcements for the shift (optional)
4. `/entry_qr` — generate the entrance QR and post it at the door
5. Operators arrive and scan → briefings sent automatically
6. During shift: use `/sick`, `/trn_start`, `/trn_end`, `/swap` as needed
7. `/update [text]` for any safety rule changes → display QR for acknowledgment

### First-time setup checklist

- [ ] Token is in `.env` as `BOT_TOKEN=...`
- [ ] Your chat ID is in `data/operators.json` (send `/start` to get it from the logs)
- [ ] `data/capabilities.json` reflects actual operator qualifications per station type
- [ ] `data/operators.json` has chat IDs for all operators (fill in as each person registers)

---

## Dependencies

| Package | Purpose |
|---|---|
| `python-telegram-bot==21.*` | Async Telegram bot framework |
| `python-dotenv` | Loads `.env` for the bot token |
| `qrcode[pil]` | Generates QR code images (entry check-in + rules acknowledgment) |

> **Python 3.12+ note**: `run_polling()` and `Updater.idle()` from PTB 21 do not work with Python 3.12+ due to `asyncio.get_event_loop()` removal. `main.py` uses `asyncio.run()` with an explicit async context manager — this is the correct pattern.
