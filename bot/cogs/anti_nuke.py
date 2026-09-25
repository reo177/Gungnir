import os
import asyncio
import discord
from discord.ext import commands
from bot.utils.action_tracker import track_action
from bot.utils.punish import punish_user
from bot.utils.logger import send_log

THRESHOLD = int(os.getenv("NUKE_THRESHOLD", 3))
INTERVAL  = int(os.getenv("NUKE_INTERVAL",  5000))
OWNER_ID  = int(os.getenv("OWNER_ID", 0))


async def _check_nuke(guild: discord.Guild, action_label: str, bot: discord.Client, audit_action: discord.AuditLogAction):
    await asyncio.sleep(0.5)  # 監査ログ反映待ち

    try:
        entry = None
        async for log in guild.audit_logs(action=audit_action, limit=1):
            entry = log
            break
        if not entry:
            return

        import time
        if (time.time() * 1000 - entry.created_at.timestamp() * 1000) > 3000:
            return

        executor: discord.User = entry.user
    except Exception:
        return

    if not executor:
        return
    if executor.id == bot.user.id:
        return
    if executor.id == OWNER_ID:
        return
    if executor.id == guild.owner_id:
        return

    triggered = track_action(str(guild.id), str(executor.id), THRESHOLD, INTERVAL)

    await send_log(
        bot,
        type="warn",
        title=f"アンチヌーク検知: {action_label}",
        description="危険なアクションを検知しました。",
        user=executor,
        fields=[
            {"name": "アクション", "value": action_label, "inline": True},
            {"name": "サーバー",   "value": guild.name,   "inline": True},
        ],
        guild_id=str(guild.id),
    )

    if triggered:
        await send_log(
            bot,
            type="nuke",
            title="🚨 アンチヌーク発動",
            description=f"しきい値({THRESHOLD}回 / {INTERVAL}ms)を超えたためBANを実行しました。",
            user=executor,
            fields=[{"name": "最後のアクション", "value": action_label, "inline": True}],
            guild_id=str(guild.id),
        )
        await punish_user(guild, executor.id, f"アンチヌーク: {action_label}を繰り返し実行", bot)


class AntiNuke(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        await _check_nuke(channel.guild, "チャンネル削除", self.bot, discord.AuditLogAction.channel_delete)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        await _check_nuke(channel.guild, "チャンネル作成", self.bot, discord.AuditLogAction.channel_create)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        await _check_nuke(role.guild, "ロール削除", self.bot, discord.AuditLogAction.role_delete)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        await _check_nuke(role.guild, "ロール作成", self.bot, discord.AuditLogAction.role_create)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        await _check_nuke(guild, "メンバーBAN", self.bot, discord.AuditLogAction.ban)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await asyncio.sleep(0.5)
        try:
            entry = None
            async for log in member.guild.audit_logs(action=discord.AuditLogAction.kick, limit=1):
                entry = log
                break
            if not entry or entry.target.id != member.id:
                return

            import time
            if (time.time() * 1000 - entry.created_at.timestamp() * 1000) > 3000:
                return

            executor = entry.user
            if not executor or executor.id == self.bot.user.id:
                return
            if executor.id == OWNER_ID or executor.id == member.guild.owner_id:
                return

            triggered = track_action(str(member.guild.id), str(executor.id), THRESHOLD, INTERVAL)

            await send_log(
                self.bot,
                type="warn",
                title="アンチヌーク検知: メンバーキック",
                description="危険なアクションを検知しました。",
                user=executor,
                fields=[{"name": "キック対象", "value": f"{member} ({member.id})", "inline": True}],
                guild_id=str(member.guild.id),
            )

            if triggered:
                await send_log(
                    self.bot,
                    type="nuke",
                    title="🚨 アンチヌーク発動",
                    description="しきい値を超えたためBANを実行しました。",
                    user=executor,
                    guild_id=str(member.guild.id),
                )
                await punish_user(member.guild, executor.id, "アンチヌーク: メンバーキックを繰り返し実行", self.bot)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        await _check_nuke(channel.guild, "Webhook作成", self.bot, discord.AuditLogAction.webhook_create)


async def setup(bot: commands.Bot):
    await bot.add_cog(AntiNuke(bot))
