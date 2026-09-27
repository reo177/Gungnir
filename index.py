import asyncio
import os

from bot.bot import start_bot

os.environ.setdefault("DISCORD_TOKEN", "TOKEN")
os.environ.setdefault("LOG_CHANNEL_ID", "")
os.environ.setdefault("VERIFY_ROLE_ID", "")
os.environ.setdefault("VERIFY_CHANNEL_ID", "")
os.environ.setdefault("OWNER_ID", "")
os.environ.setdefault("RAID_THRESHOLD", "5")
os.environ.setdefault("RAID_INTERVAL", "10000")
os.environ.setdefault("NUKE_THRESHOLD", "3")
os.environ.setdefault("NUKE_INTERVAL", "5000")


async def main():
    await start_bot()


if __name__ == "__main__":
    asyncio.run(main())
