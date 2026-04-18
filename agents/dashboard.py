import asyncio
import logging
from datetime import datetime, timezone
from telegram import Update, Message
from telegram.ext import ContextTypes
from state import state

logger = logging.getLogger(__name__)

REFRESH_SECONDS = 30

_dashboard_task: asyncio.Task | None = None
_dashboard_message: Message | None = None


def _build_dashboard() -> str:
    if not state.schedule_loaded:
        return "No schedule loaded."

    active    = [n for n, op in state.operators.items() if op.status == "active"]
    sick      = [n for n, op in state.operators.items() if op.status == "sick"]
    on_umi    = [n for n, op in state.operators.items() if op.status == "umi"]
    standby   = [n for n, op in state.operators.items() if op.status == "unassigned"]
    gaps      = [r for r in state.sick_reallocations if r.replacement == "UNCOVERED"]

    lines = [
        f"Shift: {state.shift_date}",
        f"Operators: {len(active)} active | {len(standby)} standby | {len(sick)} sick | {len(on_umi)} on U*I",
        "",
    ]

    for r in state.sick_reallocations:
        if r.replacement == "UNCOVERED":
            lines.append(f"SICK:  {r.absent} -> UNCOVERED ({r.station}, {r.station_type})")
        else:
            lines.append(f"SICK:  {r.absent} -> {r.replacement} ({r.station}, {r.station_type})")

    for name in on_umi:
        op = state.operators[name]
        cover = state.umi_covers.get(name, "no cover assigned")
        lines.append(f"U*I:   {name} -> {cover} ({op.station}, {op.station_type})")

    lines.append(f"GAPS:  {len(gaps)} uncovered" if gaps else "GAPS:  none")
    lines.append("")

    if state.ack_version > 0:
        confirmed = len(state.ack_records)
        pending   = len(state.pending_acks)
        lines.append(f"Ack v{state.ack_version}: {confirmed}/{confirmed + pending} confirmed | {pending} pending")
        if state.pending_acks:
            lines.append(f"  Pending: {', '.join(sorted(state.pending_acks))}")
    else:
        lines.append("Ack: no rules update issued")

    lines.append("")
    if state.announcements:
        lines.append(f"Announcements ({len(state.announcements)}):")
        for a in state.announcements:
            lines.append(f"  - {a}")
    else:
        lines.append("Announcements: none")

    ts = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    lines.append(f"\nLast updated: {ts}")

    return "\n".join(lines)


async def _refresh_loop():
    global _dashboard_message
    while True:
        try:
            await asyncio.sleep(REFRESH_SECONDS)
        except asyncio.CancelledError:
            return

        if _dashboard_message is None:
            return

        try:
            await _dashboard_message.edit_text(_build_dashboard())
        except Exception as e:
            if "not modified" not in str(e).lower():
                logger.warning("Dashboard refresh error: %s", e)


async def handle_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _dashboard_task, _dashboard_message

    if _dashboard_task and not _dashboard_task.done():
        _dashboard_task.cancel()

    _dashboard_message = await update.message.reply_text(_build_dashboard())
    _dashboard_task = asyncio.create_task(_refresh_loop())
