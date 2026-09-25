import os
import asyncio
import time
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands
from bot.utils.logger import send_log
from bot.utils.settings_store import record_punishment
from bot.utils.settings_store import is_on_list

THRESHOLD = int(os.getenv("RAID_THRESHOLD", 5))
INTERVAL  = int(os.getenv("RAID_INTERVAL",  10000))
NEW_ACCOUNT_DAYS = int(os.getenv("NEW_ACCOUNT_DAYS", 7))
SPAM_THRESHOLD = int(os.getenv("SPAM_THRESHOLD", 8))
SPAM_INTERVAL_MS = int(os.getenv("SPAM_INTERVAL_MS", 15000))

# {guild_id: {"count": int, "members": [id,...], "task": Task, "locked": bool}}
_raid_state: dict[str, dict] = {}
_spam_state: dict[str, dict[str, list[float]]] = {}


class AntiRaid(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild_id = str(member.guild.id)

        if is_on_list(guild_id, "blacklist", member.id):
            await send_log(
                self.bot,
                type="warn",
                title="ブラックリスト検知",
                description=f"{member.mention} はブラックリストに登録されているためBANしました。",
                user=member,
                fields=[
                    {"name": "対象ユーザー", "value": f"<@{member.id}> ({member.id})", "inline": True},
                    {"name": "判定", "value": "ブラックリスト", "inline": True},
                ],
                guild_id=guild_id,
            )
            try:
                await member.ban(reason="[SecurityBot] ブラックリスト登録ユーザー/ボットの自動BAN")
            except Exception:
                pass
            return

        if not member.bot and member.created_at > datetime.now(timezone.utc) - timedelta(days=NEW_ACCOUNT_DAYS):
            await send_log(
                self.bot,
                type="warn",
                title="新規アカウント参加検知",
                description=f"{member.mention} は作成から{NEW_ACCOUNT_DAYS}日以内の新規アカウントです。自動保護を実施しました。",
                user=member,
                fields=[
                    {"name": "作成日時", "value": f"<t:{int(member.created_at.timestamp())}:F>", "inline": True},
                    {"name": "判定基準", "value": f"{NEW_ACCOUNT_DAYS}日以内", "inline": True},
                ],
                guild_id=guild_id,
            )
            try:
                await member.kick(reason="[SecurityBot] 新規アカウントの自動保護")
            except Exception:
                pass

        if guild_id not in _raid_state:
            _raid_state[guild_id] = {"count": 0, "members": [], "task": None, "locked": False}

        state = _raid_state[guild_id]
        state["count"]   += 1
        state["members"].append(member.id)

        if state["task"] and not state["task"].done():
            state["task"].cancel()

        async def _reset():
            await asyncio.sleep(INTERVAL / 1000)
            _raid_state.pop(guild_id, None)

        state["task"] = asyncio.create_task(_reset())

        await send_log(
            self.bot,
            type="info",
            title="メンバー参加",
            description="新しいメンバーがサーバーに参加しました。",
            user=member,
            fields=[
                {"name": "アカウント作成日",   "value": f"<t:{int(member.created_at.timestamp())}:R>", "inline": True},
                {"name": "現在の参加カウント", "value": f"{state['count']} / {THRESHOLD} ({INTERVAL // 1000}秒内)", "inline": True},
            ],
            guild_id=guild_id,
        )

        if state["count"] >= THRESHOLD and not state["locked"]:
            state["locked"] = True
            members_mention = ", ".join(f"<@{m}>" for m in state["members"])[:1024]

            await send_log(
                self.bot,
                type="raid",
                title="アンチレイド発動",
                description=f"{INTERVAL // 1000}秒以内に{state['count']}人が参加しました。サーバーを保護します。",
                fields=[
                    {"name": "しきい値",       "value": f"{THRESHOLD}人 / {INTERVAL // 1000}秒", "inline": True},
                    {"name": "検知メンバー数", "value": f"{state['count']}人",                    "inline": True},
                    {"name": "対象メンバー",   "value": members_mention,                          "inline": False},
                ],
                guild_id=guild_id,
            )

            kicked = 0
            for mid in state["members"]:
                try:
                    m = member.guild.get_member(mid) or await member.guild.fetch_member(mid)
                    await m.kick(reason="[SecurityBot] アンチレイド: 短時間での大量参加を検知")
                    record_punishment(guild_id, mid, "kick", self.bot.user.id, "アンチレイド: 短時間での大量参加を検知")
                    kicked += 1
                except Exception as e:
                    print(f"[AntiRaid] キック失敗 ({mid}): {e}")

            await send_log(
                self.bot,
                type="action",
                title="レイド対象メンバーをキックしました",
                description=f"レイドとして検知された {kicked} 人をキックしました。",
                fields=[{"name": "対象メンバー数", "value": f"{kicked}人", "inline": True}],
                guild_id=guild_id,
            )

            async def _unlock():
                await asyncio.sleep(INTERVAL * 2 / 1000)
                if guild_id in _raid_state:
                    _raid_state[guild_id]["locked"] = False

            asyncio.create_task(_unlock())

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild_id = str(message.guild.id)
        user_id = str(message.author.id)
        now = time.time()
        guild_state = _spam_state.setdefault(guild_id, {})
        timestamps = guild_state.setdefault(user_id, [])

        timestamps.append(now)
        cutoff = now - (SPAM_INTERVAL_MS / 1000)
        timestamps[:] = [ts for ts in timestamps if ts >= cutoff]

        if len(timestamps) >= SPAM_THRESHOLD:
            await send_log(
                self.bot,
                type="warn",
                title="メッセージスパム検知",
                description=f"{message.author.mention} が短時間に大量メッセージを送信しました。",
                user=message.author,
                fields=[
                    {"name": "検知件数", "value": f"{len(timestamps)}件 / {SPAM_THRESHOLD}件", "inline": True},
                    {"name": "間隔", "value": f"{SPAM_INTERVAL_MS // 1000}秒以内", "inline": True},
                ],
                guild_id=guild_id,
            )
            try:
                await message.author.timeout(datetime.now(timezone.utc) + timedelta(minutes=10), reason="[SecurityBot] メッセージスパム検知")
                record_punishment(guild_id, message.author.id, "timeout", self.bot.user.id, "[SecurityBot] メッセージスパム検知")
            except Exception:
                pass
            guild_state.pop(user_id, None)


async def setup(bot: commands.Bot):
    await bot.add_cog(AntiRaid(bot))
