import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes
from state import state, SickReallocation

logger = logging.getLogger(__name__)

CAPABILITIES_PATH = Path(__file__).parent.parent / "data" / "capabilities.json"
OPERATORS_PATH = Path(__file__).parent.parent / "data" / "operators.json"
AUDIT_LOG = Path(__file__).parent.parent / "logs" / "audit.log"


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


async def handle_sick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /sick [operator_name]")
        return

    name = " ".join(args).strip()
    if name not in state.operators:
        await update.message.reply_text(f"Operator not found: {name}")
        return

    op = state.operators[name]
    if op.status == "sick":
        await update.message.reply_text(f"{name} is already marked sick.")
        return

    op.status = "sick"
    station = op.station
    station_type = op.station_type

    capabilities = _load_capabilities()
    operator_ids = _load_operator_ids()
    unassigned = state.get_unassigned()

    replacement = None
    for candidate in unassigned:
        qualified = capabilities.get(candidate, [])
        if station_type in qualified:
            replacement = candidate
            break

    ts = datetime.now(timezone.utc).isoformat()

    if replacement:
        state.operators[replacement].status = "active"
        state.sick_reallocations.append(SickReallocation(
            absent=name,
            replacement=replacement,
            station=station,
            station_type=station_type,
            timestamp=ts,
        ))
        _audit(f"SICK: {name} absent. {replacement} reallocated to {station} ({station_type}).")

        # Notify replacement operator
        chat_id = operator_ids.get(replacement)
        if chat_id:
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"Reallocation notice: {name} is sick.\n"
                    f"Please cover station {station} ({station_type}) for the remainder of the shift."
                )
            )

        await update.message.reply_text(
            f"{name} marked sick.\n"
            f"Station {station} ({station_type}) covered by {replacement}."
        )
    else:
        state.sick_reallocations.append(SickReallocation(
            absent=name,
            replacement="UNCOVERED",
            station=station,
            station_type=station_type,
            timestamp=ts,
        ))
        _audit(f"SICK: {name} absent. No compatible replacement for {station} ({station_type}). COVERAGE GAP.")

        await update.message.reply_text(
            f"COVERAGE GAP: {name} is sick.\n"
            f"No compatible unassigned operator found for station {station} ({station_type}).\n"
            f"Manual intervention required."
        )
