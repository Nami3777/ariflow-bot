import asyncio
import logging
from config import BOT_TOKEN
from orchestrator import build_application

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)


async def main():
    app = build_application(BOT_TOKEN)
    print("ariflow_bot is running. Press Ctrl+C to stop.")
    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass
        finally:
            await app.updater.stop()
            await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
