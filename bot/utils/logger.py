import os
import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import discord

LOGS_DIR = Path(__file__).parent.parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# メモリログ {guild_id: [entry, ...]}
memory_logs: dict[str, list] = {}
MAX_MEMORY = 200

COLOR_MAP = {
    "nuke":   0xFF0000,
    "raid":   0xFF6600,
    "verify": 0x00CC66,
    "action": 0xFFCC00,
    "warn":   0xFF9900,
    "info":   0x5865F2,
}
EMOJI_MAP = {
    "nuke":   "💣",
    "raid":   "🚨",
    "verify": "✅",
    "action": "⚙️",
    "warn":   "⚠️",
    "info":   "ℹ️",
}


async def send_log(
    bot: discord.Client,
    *,
    type: str,
    title: str,
    description: str,
    fields: list[dict] = None,
    user: discord.User | discord.Member = None,
    guild_id: str = None,
):
    fields = fields or []
    entry = {
        "id":          f"{int(datetime.now().timestamp()*1000):x}",
        "type":        type,
        "title":       title,
        "description": description,
        "fields":      fields,
        "user_id":     str(user.id)  if user else None,
        "user_tag":    str(user)     if user else None,
        "guild_id":    guild_id,
        "timestamp":   datetime.now(timezone.utc).isoformat(),
    }

    # メモリ保存
    if guild_id:
        memory_logs.setdefault(guild_id, []).insert(0, entry)
        if len(memory_logs[guild_id]) > MAX_MEMORY:
            memory_logs[guild_id] = memory_logs[guild_id][:MAX_MEMORY]

        today = datetime.now().strftime("%Y-%m-%d")
        log_file = LOGS_DIR / f"{guild_id}_{today}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Discordチャンネルに送信
    channel_id = os.getenv("LOG_CHANNEL_ID")
    if channel_id and bot:
        channel = bot.get_channel(int(channel_id))
        if channel:
            embed = discord.Embed(
                title=f"{EMOJI_MAP.get(type, 'ℹ️')} {title}",
                description=description,
                color=COLOR_MAP.get(type, 0x5865F2),
                timestamp=datetime.now(timezone.utc),
            )
            if user:
                embed.set_author(name=str(user), icon_url=user.display_avatar.url)
                embed.add_field(name="ユーザーID", value=str(user.id), inline=True)
            for f in fields:
                embed.add_field(name=f["name"], value=f["value"], inline=f.get("inline", False))
            try:
                await channel.send(embed=embed)
            except Exception as e:
                print(f"[Logger] Embed送信エラー: {e}")


def get_logs(guild_id: str, limit: int = 50) -> list:
    return memory_logs.get(guild_id, [])[:limit]


def get_file_logs(guild_id: str, date: str) -> list:
    log_file = LOGS_DIR / f"{guild_id}_{date}.jsonl"
    if not log_file.exists():
        return []
    entries = []
    with open(log_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass
    return list(reversed(entries))
