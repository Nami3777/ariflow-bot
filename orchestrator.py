import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from config import SUPERVISOR_IDS
from state import state
from agents.csv_parser import handle_csv_upload
from agents.daily_briefing import (
    handle_checkin,
    handle_entry_qr,
    handle_briefing,
    handle_preview,
    handle_announce,
    handle_clear_announcements,
    handle_remove_announcement,
)
from agents.sick_leave import handle_sick
from agents.rules_ack import handle_update, handle_ack_deeplink, handle_ack_status
from agents.shift_coordinator import (
    handle_umi_start,
    handle_umi_end,
    handle_swap,
    handle_approve_swap,
    handle_cancel_swap,
)
from agents.dashboard import handle_dashboard

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "Supervisor commands:\n"
    "/entry_qr — generate entrance check-in QR code\n"
    "/announce [text] — add an announcement to today's briefings\n"
    "/remove_announcement [number] — remove one announcement by number\n"
    "/clear_announcements — remove all announcements\n"
    "/status — system health check\n"
    "/dashboard — live shift dashboard (auto-refreshes every 30s)\n"
    "/preview [name] — see exactly what that operator's briefing looks like\n"
    "/sick [name] — mark operator sick and reallocate\n"
    "/umi_start [name] — operator starting U*I break\n"
    "/umi_end [name] — operator returned from U*I\n"
    "/swap [name1] [name2] — request station swap\n"
    "/approve_swap [id] — approve a pending swap\n"
    "/cancel_swap [id] — cancel a pending swap\n"
    "/update [rules text] — issue rules update + QR code\n"
    "/ack_status — show acknowledgment status\n\n"
    "Upload a .csv file to load the shift schedule.\n\n"
    "Operators: scan the entrance QR code to check in and receive your briefing."
)


def _supervisor_only(handler):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in SUPERVISOR_IDS:
            await update.message.reply_text("This command is restricted to supervisors.")
            return
        await handler(update, context)
    return wrapper


def _supervisor_schedule(handler):
    return _supervisor_only(_schedule_guard(handler))


def _schedule_guard(handler):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not state.schedule_loaded:
            await update.message.reply_text(
                "No schedule loaded. Upload a CSV file first."
            )
            return
        await handler(update, context)
    return wrapper


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(f"Ariflow Bot online.\n\n{HELP_TEXT}")
        return

    arg = context.args[0]
    if arg == "checkin":
        await handle_checkin(update, context)
    elif arg.startswith("ack_"):
        await handle_ack_deeplink(update, context)
    else:
        await update.message.reply_text(f"Ariflow Bot online.\n\n{HELP_TEXT}")


async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(state.summary())


async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Unknown command.\n\n{HELP_TEXT}")


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Unhandled exception", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "An internal error occurred. The supervisor has been notified."
        )


def build_application(token: str) -> Application:
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start",                handle_start))
    app.add_handler(CommandHandler("status",               handle_status))

    # Supervisor-only commands
    app.add_handler(CommandHandler("entry_qr",             _supervisor_only(handle_entry_qr)))
    app.add_handler(CommandHandler("announce",             _supervisor_only(handle_announce)))
    app.add_handler(CommandHandler("clear_announcements",  _supervisor_only(handle_clear_announcements)))
    app.add_handler(CommandHandler("remove_announcement",  _supervisor_only(handle_remove_announcement)))
    app.add_handler(CommandHandler("briefing",             _supervisor_schedule(handle_briefing)))
    app.add_handler(CommandHandler("preview",              _supervisor_schedule(handle_preview)))
    app.add_handler(CommandHandler("dashboard",            _supervisor_schedule(handle_dashboard)))
    app.add_handler(CommandHandler("sick",                 _supervisor_schedule(handle_sick)))
    app.add_handler(CommandHandler("umi_start",            _supervisor_schedule(handle_umi_start)))
    app.add_handler(CommandHandler("umi_end",              _supervisor_schedule(handle_umi_end)))
    app.add_handler(CommandHandler("approve_swap",         _supervisor_schedule(handle_approve_swap)))
    app.add_handler(CommandHandler("cancel_swap",          _supervisor_schedule(handle_cancel_swap)))
    app.add_handler(CommandHandler("update",               _supervisor_schedule(handle_update)))
    app.add_handler(CommandHandler("ack_status",           _supervisor_schedule(handle_ack_status)))

    # Open to all (schedule required)
    app.add_handler(CommandHandler("swap", _schedule_guard(handle_swap)))

    # CSV upload — supervisor only
    app.add_handler(MessageHandler(filters.Document.ALL, _supervisor_only(handle_csv_upload)))
    app.add_handler(MessageHandler(filters.COMMAND, handle_unknown))
    app.add_error_handler(handle_error)

    return app
