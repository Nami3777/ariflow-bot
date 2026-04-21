# AriBot — Operator Onboarding Guide

**System**: Ariflow Bot (`@ariflow_bot`)
**Purpose**: Replaces manual shift coordination (group chats, whiteboards, spreadsheets) with structured check-in, automated briefings, and capability-matched reallocation.
**Audience**: Supervisors and operators joining for the first time.

---

## What Changes for You

| Before AriBot | With AriBot |
|---|---|
| Supervisor manually sends shift briefings to each operator | Each operator scans one QR code → receives personalised briefing instantly |
| Sick-leave replacement found by memory or whiteboard | Bot matches capability matrix → notifies replacement automatically |
| Safety rule updates sent ad-hoc via group chat | Formal QR acknowledgment — supervisor sees who has and hasn't confirmed |
| Training slot cover managed verbally | Bot tracks cover requests, approvals, and returns in real time |
| No audit trail | Every event timestamped in `logs/audit.log` |

---

## Part 1 — Supervisor Setup (First Time)

### 1.1 Start the bot

```bash
cd path/to/agile-workflow
pip install -r requirements.txt
python main.py
```

Stop with `Ctrl+C`. The bot must be running before operators scan in.

### 1.2 Register yourself

Send `/start` to `@ariflow_bot` in Telegram. Your chat ID will appear in the console:

```
chat_id=XXXXXXXXX
```

Add this to `data/operators.json`:

```json
{
  "YourName": 0
}
```

Add your name to `config.py` as a supervisor ID so you have access to all supervisor commands.

### 1.3 Register each operator

Each operator must send `/start` to `@ariflow_bot` once. Collect their chat IDs from the console log and add them to `data/operators.json`:

```json
{
  "Namyun":   0,
  "Hamish":   0,
  "Rafael":   0
}
```

Operators with `0` as their chat ID will not receive messages — the bot will warn you.

### 1.4 Set up the capability matrix

Edit `data/capabilities.json` to reflect each operator's qualified station types:

```json
{
  "Namyun":  ["S-Beta", "S-Alpha"],
  "Hamish":  ["D-Alpha", "S-Gamma", "S-Beta"],
  "Rafael":  ["S-Beta"]
}
```

Update this file whenever an operator completes new station training. The sick-leave and training slot agents use this to find valid replacements — an outdated matrix leads to incorrect assignments.

**Station type codes:**

| Code | Robot |
|---|---|
| `S-Alpha` | Single-arm Alpha |
| `S-Beta` | Single-arm Beta |
| `D-Beta` | Dual-arm Beta |
| `D-Alpha` | Dual-arm Alpha |
| `S-Gamma` | Single-arm Gamma |
| `S-Delta` | Single-arm Delta |

---

## Part 2 — Shift Startup (Every Shift)

### 2.1 Prepare the schedule CSV

The shift schedule CSV is the single source of truth. It must be uploaded at the start of every shift. A new upload resets all in-memory state (check-ins, announcements, training slot status).

**Required columns:**

| Column | Example |
|---|---|
| `shift_date` | `2026-04-12` |
| `operator_name` | `Namyun` (must match `operators.json`) |
| `station` | `A-7` |
| `station_type` | `S-Beta` |
| `shift_start` | `14:30` |
| `shift_end` | `23:00` |
| `trn_start` | `17:30` |
| `trn_end` | `18:30` |
| `trn_sop` | `6` (plain integer from the Training Slot Shift Plan) |
| `sop1` – `sop4` | `SOP#00033(90)` |
| `status` | `active` or `unassigned` |

Operators on standby: set `status = unassigned`, leave station and SOP columns empty.

**SOP format**: `SOP#00033(90)` = SOP number 00033, daily target 90 units.

### 2.2 Shift startup sequence

1. Upload the schedule CSV to the bot chat
2. `/announce [text]` — add any shift announcements (optional, repeat for multiple)
3. `/entry_qr` — generates the entrance QR code image
4. Print or display the QR at the facility entrance
5. Operators arrive and scan — briefings are sent automatically

### 2.3 Operator briefing (what each operator sees on check-in)

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

Standby operators receive a confirmation message with shift hours and standby status.

---

## Part 3 — During Shift

### 3.1 Live dashboard

```
/dashboard
```

Shows all operators, their stations, check-in status, and current activity. Auto-refreshes every 30 seconds.

### 3.2 Sick leave

```
/sick Namyun
```

What happens:
1. Namyun marked absent
2. Bot scans standby pool for an operator qualified for Namyun's station type
3. First match is reassigned and notified via Telegram DM
4. Event logged: `SICK: Namyun absent. Hamish reallocated to A-7 (S-Beta).`

If no qualified standby operator is available, the bot alerts the supervisor immediately with station type and gap details.

### 3.3 Training slot breaks

**Operator starts training slot:**
```
/trn_start Namyun
```
Bot finds a standby operator qualified for A-7 and sends them a cover request.

**Operator returns:**
```
/trn_end Namyun
```
Cover operator released back to standby.

### 3.4 Station swaps

```
/swap Namyun Hamish
```

Submits a swap request. Supervisor reviews and approves:

```
/approve_swap [swap_id]
```

Both operators are notified. Event logged.

### 3.5 Announcements

```
/announce Data quality check — submit end-of-shift report by 22:30
/remove_announcement 1
```

Announcements appear in all briefings sent after they are added. Cleared automatically when a new CSV is uploaded, or manually with `/clear_announcements`.

---

## Part 4 — Safety Rules Updates

When a safety rule changes mid-shift:

```
/update New rule: all operators must wear gloves when handling D-Alpha units.
```

What happens:
1. Bot generates a new acknowledgment QR code
2. Supervisor displays QR on floor
3. Operators scan it — Telegram opens and bot records name + timestamp
4. Old QR code is immediately invalidated

**Check acknowledgment status:**
```
/ack_status
```

Shows a list of who has and hasn't acknowledged the current rules version. Follow up with unacknowledged operators before continuing work.

---

## Part 5 — Operator Quick Reference

This section is for operators. You do not need Telegram commands — your only action is scanning QR codes.

### 5.1 First-time setup (one time only)

1. Open Telegram on your phone
2. Search for `@ariflow_bot` and send `/start`
3. Tell your supervisor — they will register your chat ID

You only do this once.

### 5.2 Shift check-in (every shift)

1. Arrive at the facility entrance
2. Scan the QR code posted at the door with your phone camera
3. Telegram opens automatically — your personalised briefing appears within seconds

Your briefing shows your station, today's 4 SOPs with targets, your training slot window, and any announcements from the supervisor.

### 5.3 If you are called to cover

You will receive a Telegram message from the bot if:
- A colleague called in sick and you are the qualified replacement
- A colleague started their training slot and you are covering their station

The message will tell you the station, station type, and duration. Go to that station and begin. When the original operator returns, you will receive a release message.

### 5.4 Safety rules acknowledgment

When a safety update is issued, a new QR code will appear on the floor. Scan it with your phone — Telegram will open and confirm your acknowledgment automatically. No typing required.

---

## Part 6 — Troubleshooting

| Issue | Likely cause | Fix |
|---|---|---|
| Operator not receiving briefing | Chat ID is `0` in `operators.json` | Operator sends `/start` to bot; add chat ID to file |
| No standby replacement found | Capability matrix does not cover the station type | Update `data/capabilities.json`; if urgent, assign manually |
| Old acknowledgment QR still scanning | Bot version mismatch or cached QR | Run `/update` again to generate a fresh QR; old QR is invalidated |
| Bot not responding | Bot process stopped | Restart: `python main.py` in the agile-workflow directory |
| Check-in not working | CSV not yet uploaded, or name mismatch | Re-upload CSV; verify operator name in CSV matches `operators.json` exactly |

---

## Audit Log

All events are written to `logs/audit.log` with UTC timestamps. The log is append-only and persists across restarts.

```
[2026-04-12T06:15:00Z] SICK: Namyun absent. Hamish reallocated to A-7 (S-Beta).
[2026-04-12T07:00:00Z] TRN_START: Rafael on training slot. Namyun covering B-5 (S-Gamma).
[2026-04-12T07:30:00Z] TRN_END: Rafael returned to station B-5.
[2026-04-12T08:00:00Z] SWAP approved: Alonso ↔ Luca.
```

Supervisors can share this log with team leads or compliance reviewers as needed.

---

## Adoption Checklist — Before Going Live

- [ ] All operators have registered via `/start` and their chat IDs are in `operators.json`
- [ ] `capabilities.json` reflects current station qualifications for all operators
- [ ] Supervisor has tested the shift startup sequence with a sample CSV
- [ ] Supervisor has generated and scanned a test `/entry_qr` to confirm briefing delivery
- [ ] At least one operator has completed the check-in flow end-to-end
- [ ] `/sick` and `/trn_start` tested with standby operator in pilot run
- [ ] Audit log reviewed after pilot run to confirm event recording
- [ ] Supervisor knows how to restart the bot if it stops
