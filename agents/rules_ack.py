import io
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
import qrcode
from telegram import Update
from telegram.ext import ContextTypes
from state import state

logger = logging.getLogger(__name__)

BOT_USERNAME = "ariflow_bot"
OPERATORS_PATH = Path(__file__).parent.parent / "data" / "operators.json"


def _chat_id_to_name(chat_id: int) -> str | None:
    if OPERATORS_PATH.exists():
        data = json.loads(OPERATORS_PATH.read_text())
        for name, cid in data.items():
            if name != "_comment" and cid == chat_id:
                return name
    return None


async def handle_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /update [rules text]")
        return

    rules_text = " ".join(context.args)
    state.ack_version += 1
    version = state.ack_version
    state.ack_records.clear()
    state.pending_acks = set(state.operators.keys())

    deep_link = f"https://t.me/{BOT_USERNAME}?start=ack_{version}"
    img = qrcode.make(deep_link)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    await update.message.reply_photo(
        photo=buf,
        caption=(
            f"Rules update v{version}:\n{rules_text}\n\n"
            f"Operators: scan to acknowledge."
        )
    )
    logger.info("Rules update v%d issued.", version)


async def handle_ack_deeplink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or not args[0].startswith("ack_"):
        return

    try:
        version = int(args[0].split("_")[1])
    except (IndexError, ValueError):
        return

    if version != state.ack_version:
        await update.message.reply_text("This acknowledgment link has expired.")
        return

    chat_id = update.effective_user.id
    operator_name = _chat_id_to_name(chat_id)
    if not operator_name:
        await update.message.reply_text(
            "Your Telegram account is not registered in the system. "
            "Ask your supervisor to add your chat ID."
        )
        return

    ts = datetime.now(timezone.utc).isoformat()

    from state import AckRecord
    state.ack_records[operator_name] = AckRecord(name=operator_name, timestamp=ts)
    state.pending_acks.discard(operator_name)

    await update.message.reply_text(f"Acknowledged. Thank you, {operator_name}.")


async def handle_ack_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if state.ack_version == 0:
        await update.message.reply_text("No rules update issued yet.")
        return

    confirmed = list(state.ack_records.keys())
    pending = list(state.pending_acks)

    lines = [f"Rules v{state.ack_version} acknowledgment status:"]
    lines.append(f"Confirmed ({len(confirmed)}): {', '.join(confirmed) or 'none'}")
    lines.append(f"Pending ({len(pending)}): {', '.join(pending) or 'none'}")
    await update.message.reply_text("\n".join(lines))
