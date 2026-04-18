import io
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

import qrcode
from telegram import Update
from telegram.ext import ContextTypes

from state import state, Operator

logger = logging.getLogger(__name__)

OPERATORS_PATH = Path(__file__).parent.parent / "data" / "operators.json"
BOT_USERNAME = "ariflow_bot"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_operator_ids() -> dict[str, int]:
    if OPERATORS_PATH.exists():
        data = json.loads(OPERATORS_PATH.read_text())
        return {k: v for k, v in data.items() if k != "_comment"}
    return {}


def _chat_id_to_name(chat_id: int) -> str | None:
    """Reverse lookup: Telegram chat ID → operator name."""
    for name, cid in _load_operator_ids().items():
        if cid == chat_id:
            return name
    return None


def _parse_sop(sop_str: str) -> tuple[str, str]:
    """'SOP#00033(90)' → ('SOP#00033', '90')"""
    match = re.match(r"(SOP#\d+)\((\d+)\)", sop_str.strip())
    if match:
        return match.group(1), match.group(2)
    return sop_str.strip(), ""


def _time_greeting(shift_start: str) -> str:
    try:
        hour = int(shift_start.split(":")[0])
    except ValueError:
        return "Hello"
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


def _task_slots(shift_start: str) -> list[tuple[str, str]]:
    """Return 4 x 2-hour task windows starting from shift_start."""
    try:
        base = datetime.strptime(shift_start, "%H:%M")
    except ValueError:
        return [("", "")] * 4
    slots = []
    for i in range(4):
        start = base + timedelta(hours=2 * i)
        end = base + timedelta(hours=2 * (i + 1))
        slots.append((start.strftime("%H:%M"), end.strftime("%H:%M")))
    return slots


def build_briefing(name: str, op: Operator) -> str:
    """Compose the full briefing message for one operator."""
    greeting = _time_greeting(op.shift_start)
    slots = _task_slots(op.shift_start)

    sops = [op.sop1, op.sop2, op.sop3, op.sop4]
    task_lines = []
    for i, (sop_str, (t_start, t_end)) in enumerate(zip(sops, slots), start=1):
        sop_num, target = _parse_sop(sop_str)
        target_part = f"   Target: {target}" if target else ""
        task_lines.append(f"  {t_start}–{t_end}   {sop_num}{target_part}")

    if op.umi_start and op.umi_end:
        umi_sop_str = f"   SOP#{op.umi_sop.zfill(5)}" if op.umi_sop else ""
        umi_line = f"⏱ U*I: {op.umi_start}–{op.umi_end}{umi_sop_str}"
    else:
        umi_line = ""

    announcement_block = ""
    if state.announcements:
        items = "\n".join(f"  • {a}" for a in state.announcements)
        announcement_block = f"\n\n📢 Announcements:\n{items}"
    else:
        announcement_block = "\n\n📢 No announcements today."

    body = (
        f"✅ Checked in — {greeting}, {name}!\n\n"
        f"📍 Station {op.station} — {op.station_type}\n"
        f"⏰ Shift: {op.shift_start} – {op.shift_end}\n\n"
        f"📋 Tasks today (2h each):\n"
        + "\n".join(task_lines)
    )
    if umi_line:
        body += f"\n\n{umi_line}"
    body += announcement_block
    return body


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def handle_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered by operator scanning the entrance QR code."""
    chat_id = update.effective_user.id
    name = _chat_id_to_name(chat_id)

    if not name:
        await update.message.reply_text(
            "Your Telegram account is not registered in the system.\n"
            "Ask your supervisor to add your chat ID."
        )
        return

    if not state.schedule_loaded:
        await update.message.reply_text(
            "No schedule loaded yet. Check back shortly or contact your supervisor."
        )
        return

    op = state.operators.get(name)
    if not op:
        await update.message.reply_text(
            f"You ({name}) are not on today's schedule."
        )
        return

    if op.status == "unassigned":
        umi_info = ""
        if op.umi_start and op.umi_end:
            umi_sop_str = f"   SOP#{op.umi_sop.zfill(5)}" if op.umi_sop else ""
            umi_info = f"\n⏱ U*I: {op.umi_start}–{op.umi_end}{umi_sop_str}"
        announcements = ""
        if state.announcements:
            items = "\n".join(f"  • {a}" for a in state.announcements)
            announcements = f"\n\n📢 Announcements:\n{items}"
        await update.message.reply_text(
            f"✅ Checked in, {name}.\n\n"
            f"You are unassigned for today.\n"
            f"We will allocate you to an empty station promptly.\n"
            f"⏰ Shift: {op.shift_start}–{op.shift_end}"
            + umi_info
            + announcements
        )
        return

    await update.message.reply_text(build_briefing(name, op))
    logger.info("Check-in: %s (chat_id=%d)", name, chat_id)


async def handle_entry_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Supervisor command: generate today's entrance check-in QR code."""
    deep_link = f"https://t.me/{BOT_USERNAME}?start=checkin"
    img = qrcode.make(deep_link)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    shift_label = f" — {state.shift_date}" if state.schedule_loaded else ""
    await update.message.reply_photo(
        photo=buf,
        caption=(
            f"Entrance check-in QR{shift_label}\n"
            f"Post at the facility entrance.\n"
            f"Operators scan to receive their shift briefing."
        )
    )


async def handle_announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Supervisor command: /announce [text] — add an announcement to today's briefings."""
    if not context.args:
        await update.message.reply_text("Usage: /announce [announcement text]")
        return
    text = " ".join(context.args).strip()
    state.announcements.append(text)
    await update.message.reply_text(
        f"Announcement added ({len(state.announcements)} total):\n• {text}"
    )


async def handle_clear_announcements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Supervisor command: clear all announcements."""
    count = len(state.announcements)
    state.announcements.clear()
    await update.message.reply_text(f"Cleared {count} announcement(s).")


async def handle_remove_announcement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Supervisor command: /remove_announcement [number] — remove one announcement by index."""
    if not context.args:
        await update.message.reply_text("Usage: /remove_announcement [number]")
        return

    try:
        index = int(context.args[0]) - 1
    except ValueError:
        await update.message.reply_text("Please provide a number. Check /status to see the list.")
        return

    if index < 0 or index >= len(state.announcements):
        await update.message.reply_text(
            f"No announcement #{index + 1}. There are {len(state.announcements)} announcement(s)."
        )
        return

    removed = state.announcements.pop(index)
    await update.message.reply_text(f"Removed: {removed}")


async def handle_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Supervisor command: /preview [name] — see exactly what that operator's briefing looks like."""
    if not context.args:
        await update.message.reply_text("Usage: /preview [operator_name]")
        return

    name = " ".join(context.args).strip()
    op = state.operators.get(name)
    if not op:
        await update.message.reply_text(f"Operator not found: {name}")
        return

    if op.status == "sick":
        msg = f"[Preview for {name}]\n\nStatus: SICK — marked absent this shift."
    elif op.status == "umi":
        cover = state.umi_covers.get(name, "unknown")
        msg = (
            f"[Preview for {name}]\n\n"
            f"Status: ON U*I BREAK\n"
            f"Station {op.station} covered by {cover}."
        )
    elif op.status == "unassigned":
        umi_info = ""
        if op.umi_start and op.umi_end:
            umi_sop_str = f"   SOP#{op.umi_sop.zfill(5)}" if op.umi_sop else ""
            umi_info = f"\n⏱ U*I: {op.umi_start}–{op.umi_end}{umi_sop_str}"
        msg = (
            f"[Preview for {name}]\n\n"
            f"✅ Checked in, {name}.\n\n"
            f"You are unassigned for today.\n"
            f"We will allocate you to an empty station promptly.\n"
            f"⏰ Shift: {op.shift_start}–{op.shift_end}" + umi_info
        )
    else:
        msg = f"[Preview for {name}]\n\n" + build_briefing(name, op)

    await update.message.reply_text(msg)


async def handle_briefing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Supervisor fallback: push briefings to all registered operators via DM."""
    operator_ids = _load_operator_ids()
    sent = 0
    no_id = []

    for name, op in state.operators.items():
        chat_id = operator_ids.get(name)
        if not chat_id:
            no_id.append(name)
            continue
        if op.status == "unassigned":
            umi_info = ""
            if op.umi_start and op.umi_end:
                umi_sop_str = f"   SOP#{op.umi_sop.zfill(5)}" if op.umi_sop else ""
                umi_info = f"\n⏱ U*I: {op.umi_start}–{op.umi_end}{umi_sop_str}"
            msg = (
                f"✅ Shift briefing, {name}.\n\n"
                f"You are unassigned for today.\n"
                f"We will allocate you to an empty station promptly.\n"
                f"⏰ Shift: {op.shift_start}–{op.shift_end}" + umi_info
            )
        else:
            msg = build_briefing(name, op)
        try:
            await context.bot.send_message(chat_id=chat_id, text=msg)
            sent += 1
        except Exception as e:
            logger.error("Failed to send briefing to %s: %s", name, e)
            no_id.append(name)

    reply = f"Briefings sent: {sent}/{len(state.operators)}."
    if no_id:
        reply += f"\nNo chat ID for: {', '.join(no_id)}"
    await update.message.reply_text(reply)
