import os
import asyncio
import threading

# ===== 設定値 =====
os.environ.setdefault("DISCORD_TOKEN",   " TOKEN ")
os.environ.setdefault("CLIENT_ID",       " CLIENT ID ")
os.environ.setdefault("CLIENT_SECRET",   " CLIENT SECRET ")
os.environ.setdefault("SESSION_SECRET",  " SESSION SECRET ")
os.environ.setdefault("CALLBACK_URL",    "http://YOU DOMAIN/auth/callback")
os.environ.setdefault("DASHBOARD_PORT",  "3001")
os.environ.setdefault("LOG_CHANNEL_ID",  " LOG CHANNER ID ")
os.environ.setdefault("VERIFY_ROLE_ID",  " VERIFY ROLE ID ")
os.environ.setdefault("VERIFY_CHANNEL_ID"," VERIFY CHANNEL ID")
os.environ.setdefault("OWNER_ID",        " OWNER USID ")
os.environ.setdefault("RAID_THRESHOLD",  "5")
os.environ.setdefault("RAID_INTERVAL",   "10000")
os.environ.setdefault("NUKE_THRESHOLD",  "3")
os.environ.setdefault("NUKE_INTERVAL",   "5000")
os.environ.setdefault("START_DASHBOARD", "true")

import discord
from discord.ext import commands

# ===== Bot設定 =====
intents = discord.Intents.default()
intents.members         = True
intents.message_content = True
intents.moderation      = True

bot = commands.Bot(command_prefix="!", intents=intents)

COGS = [
    "bot.cogs.anti_nuke",
    "bot.cogs.anti_raid",
    "bot.cogs.verify",
    "bot.cogs.moderation",
    "bot.cogs.event_log",
]


@bot.event
async def on_ready():
    print(f"[Bot] {bot.user} としてログインしました")
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name="サーバーを監視中 🛡️"
    ))
    try:
        synced = await bot.tree.sync()
        print(f"[Bot] {len(synced)}個のスラッシュコマンドを同期しました")
    except Exception as e:
        print(f"[Bot] コマンド同期エラー: {e}")


async def load_cogs():
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"[Cog] {cog} を読み込みました")
        except Exception as e:
            print(f"[Cog] {cog} の読み込み失敗: {e}")


def run_dashboard():
    from dashboard.app import app
    port = int(os.environ["DASHBOARD_PORT"])
    print(f"[Dashboard] ポート {port} で起動しました")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


async def main():
    token = os.environ["DISCORD_TOKEN"]
    print(f"[Bot] トークン確認: {token[:20]}...")

    await load_cogs()

    if os.environ.get("START_DASHBOARD", "true").lower() == "true":
        t = threading.Thread(target=run_dashboard, daemon=True)
        t.start()

    await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
