import csv
import io
import logging
from telegram import Update
from telegram.ext import ContextTypes
from state import state, Operator

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {
    "operator_name", "station_type", "shift_start", "shift_end",
    "umi_start", "umi_end", "umi_sop", "sop1", "sop2", "sop3", "sop4", "status"
}


async def handle_csv_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.endswith(".csv"):
        await update.message.reply_text("Please upload a .csv file.")
        return

    file = await doc.get_file()
    raw = await file.download_as_bytearray()
    text = raw.decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(text))
    columns = set(reader.fieldnames or [])
    missing = REQUIRED_COLUMNS - columns
    if missing:
        await update.message.reply_text(
            f"CSV missing columns: {', '.join(sorted(missing))}"
        )
        return

    state.reset()
    rows = list(reader)
    shift_dates = set()

    for row in rows:
        name = row["operator_name"].strip()
        status = row["status"].strip()
        is_unassigned = status == "unassigned"

        state.operators[name] = Operator(
            station=row.get("station", "").strip(),
            station_type=row["station_type"].strip(),
            shift_start=row["shift_start"].strip(),
            shift_end=row["shift_end"].strip(),
            umi_start=row["umi_start"].strip(),
            umi_end=row["umi_end"].strip(),
            umi_sop=row["umi_sop"].strip() if not is_unassigned else "",
            sop1=row["sop1"].strip() if not is_unassigned else "",
            sop2=row["sop2"].strip() if not is_unassigned else "",
            sop3=row["sop3"].strip() if not is_unassigned else "",
            sop4=row["sop4"].strip() if not is_unassigned else "",
            status=status,
        )
        if "shift_date" in row:
            shift_dates.add(row["shift_date"].strip())

    state.shift_date = ", ".join(sorted(shift_dates)) if shift_dates else "unknown"
    state.schedule_loaded = True

    total = len(state.operators)
    assigned = sum(1 for op in state.operators.values() if op.status == "active")
    standby = total - assigned

    logger.info("Schedule loaded: %d operators (%d active, %d standby)", total, assigned, standby)
    await update.message.reply_text(
        f"Schedule loaded: {total} operators for {state.shift_date}.\n"
        f"Active: {assigned} | Standby: {standby}"
    )
