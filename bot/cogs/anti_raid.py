import os
import asyncio
import discord
from discord.ext import commands
from bot.utils.logger import send_log

THRESHOLD = int(os.getenv("RAID_THRESHOLD", 5))
INTERVAL  = int(os.getenv("RAID_INTERVAL",  10000))

# {guild_id: {"count": int, "members": [id,...], "task": Task, "locked": bool}}
_raid_state: dict[str, dict] = {}


class AntiRaid(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild_id = str(member.guild.id)

        if guild_id not in _raid_state:
            _raid_state[guild_id] = {"count": 0, "members": [], "task": None, "locked": False}

        state = _raid_state[guild_id]
        state["count"]   += 1
        state["members"].append(member.id)

        # タイマーリセット
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
                title="🚨 アンチレイド発動",
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

            # クールダウン後にロック解除
            async def _unlock():
                await asyncio.sleep(INTERVAL * 2 / 1000)
                if guild_id in _raid_state:
                    _raid_state[guild_id]["locked"] = False

            asyncio.create_task(_unlock())


async def setup(bot: commands.Bot):
    await bot.add_cog(AntiRaid(bot))
