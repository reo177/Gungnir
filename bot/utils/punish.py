import os
import discord
from .logger import send_log


async def punish_user(guild: discord.Guild, user_id: int, reason: str, bot: discord.Client):
    """対象ユーザーをBANしてログを記録する"""
    try:
        member = guild.get_member(user_id) or await guild.fetch_member(user_id)
    except Exception:
        member = None

    if not member:
        return

    # オーナーとBot自身は除外
    if member.id == guild.owner_id:
        return
    if member.bot and member.id == bot.user.id:
        return

    try:
        await guild.ban(member, reason=f"[SecurityBot] {reason}", delete_message_seconds=0)
        await send_log(
            bot,
            type="action",
            title="ユーザーをBANしました",
            description="危険なアクションを検知したため自動BANを実行しました。",
            fields=[
                {"name": "対象ユーザー", "value": f"<@{user_id}> ({user_id})", "inline": True},
                {"name": "理由",         "value": reason,                        "inline": False},
            ],
            guild_id=str(guild.id),
        )
    except Exception as e:
        print(f"[Punish] BAN失敗 ({user_id}): {e}")
