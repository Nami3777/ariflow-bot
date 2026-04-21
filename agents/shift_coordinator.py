import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes
from state import state

logger = logging.getLogger(__name__)

CAPABILITIES_PATH = Path(__file__).parent.parent / "data" / "capabilities.json"
OPERATORS_PATH = Path(__file__).parent.parent / "data" / "operators.json"
AUDIT_LOG = Path(__file__).parent.parent / "logs" / "audit.log"

_pending_swaps: dict[str, tuple[str, str]] = {}


def _load_capabilities() -> dict[str, list[str]]:
    if CAPABILITIES_PATH.exists():
        return json.loads(CAPABILITIES_PATH.read_text())
    return {}


def _load_operator_ids() -> dict[str, int]:
    if OPERATORS_PATH.exists():
        return json.loads(OPERATORS_PATH.read_text())
    return {}


def _audit(message: str):
    ts = datetime.now(timezone.utc).isoformat()
    with open(AUDIT_LOG, "a") as f:
        f.write(f"[{ts}] {message}\n")


async def handle_trn_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /trn_start [operator_name]")
        return

    name = " ".join(context.args).strip()
    if name not in state.operators:
        await update.message.reply_text(f"Operator not found: {name}")
        return

    op = state.operators[name]
    op.status = "trn"
    station = op.station
    station_type = op.station_type

    capabilities = _load_capabilities()
    operator_ids = _load_operator_ids()
    unassigned = state.get_unassigned()

    cover = None
    for candidate in unassigned:
        if station_type in capabilities.get(candidate, []):
            cover = candidate
            break

    if cover:
        state.operators[cover].status = "active"
        state.trn_covers[name] = cover
        _audit(f"TRN_START: {name} on training slot. {cover} covering {station} ({station_type}).")
        chat_id = operator_ids.get(cover)
        if chat_id:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"Please cover station {station} ({station_type}) while {name} is on training slot."
            )
        await update.message.reply_text(
            f"{name} started training slot. {cover} covering station {station}."
        )
    else:
        _audit(f"TRN_START: {name} on training slot. No cover found for {station} ({station_type}). GAP.")
        await update.message.reply_text(
            f"COVERAGE GAP: {name} on training slot, no compatible cover for {station} ({station_type})."
        )


async def handle_trn_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /trn_end [operator_name]")
        return

    name = " ".join(context.args).strip()
    if name not in state.operators:
        await update.message.reply_text(f"Operator not found: {name}")
        return

    op = state.operators[name]
    op.status = "active"

    cover = state.trn_covers.pop(name, None)
    if cover and cover in state.operators:
        state.operators[cover].status = "unassigned"
        _audit(f"TRN_END: {name} returned to station {op.station}. {cover} released to standby.")
    else:
        _audit(f"TRN_END: {name} returned to station {op.station}.")

    await update.message.reply_text(f"{name} returned from training slot. Back on station {op.station}.")


def _split_two_operators(args: list[str]) -> tuple[str, str] | None:
    """Try all splits to find two valid operator names (supports multi-word names)."""
    for i in range(1, len(args)):
        name1 = " ".join(args[:i])
        name2 = " ".join(args[i:])
        if name1 in state.operators and name2 in state.operators:
            return name1, name2
    return None


async def handle_swap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /swap [name1] [name2]")
        return

    pair = _split_two_operators(context.args)
    if not pair:
        await update.message.reply_text(
            "Could not match two operators from those names. Check spelling and try again."
        )
        return
    name1, name2 = pair

    swap_id = f"{name1}_{name2}"
    _pending_swaps[swap_id] = (name1, name2)
    await update.message.reply_text(
        f"Swap requested: {name1} ↔ {name2}.\n"
        f"Supervisor: approve with /approve_swap {swap_id} or cancel with /cancel_swap {swap_id}"
    )


async def handle_approve_swap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /approve_swap [swap_id]")
        return

    swap_id = context.args[0]
    if swap_id not in _pending_swaps:
        await update.message.reply_text("No pending swap with that ID.")
        return

    name1, name2 = _pending_swaps.pop(swap_id)
    op1, op2 = state.operators[name1], state.operators[name2]
    op1.station, op2.station = op2.station, op1.station
    op1.station_type, op2.station_type = op2.station_type, op1.station_type

    _audit(f"SWAP approved: {name1} ↔ {name2}.")
    await update.message.reply_text(f"Swap approved: {name1} ↔ {name2}.")


async def handle_cancel_swap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /cancel_swap [swap_id]")
        return

    swap_id = context.args[0]
    if _pending_swaps.pop(swap_id, None):
        await update.message.reply_text(f"Swap {swap_id} cancelled.")
    else:
        await update.message.reply_text("No pending swap with that ID.")
