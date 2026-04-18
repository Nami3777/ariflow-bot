import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set in .env")

# Comma-separated Telegram chat IDs allowed to issue supervisor commands.
# Example .env entry: SUPERVISOR_IDS=1234567890,9876543210
_raw_ids = os.getenv("SUPERVISOR_IDS", "")
SUPERVISOR_IDS: set[int] = {int(x.strip()) for x in _raw_ids.split(",") if x.strip().isdigit()}
if not SUPERVISOR_IDS:
    raise RuntimeError("SUPERVISOR_IDS not set in .env")
