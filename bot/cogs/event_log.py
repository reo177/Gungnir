import asyncio
import time
import discord
from discord.ext import commands
from bot.utils.logger import send_log


class EventLog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ===== ロール付与 / 削除 / タイムアウト =====
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # ロール変化
        added   = [r for r in after.roles  if r not in before.roles]
        removed = [r for r in before.roles if r not in after.roles]
        if added:
            await send_log(self.bot, type="info", title="ロール付与",
                description=f"{after.mention} にロールが付与されました。",
                fields=[{"name": "付与ロール", "value": " ".join(r.mention for r in added), "inline": True}],
                user=after, guild_id=str(after.guild.id))
        if removed:
            await send_log(self.bot, type="info", title="ロール削除",
                description=f"{after.mention} からロールが削除されました。",
                fields=[{"name": "削除ロール", "value": " ".join(r.mention for r in removed), "inline": True}],
                user=after, guild_id=str(after.guild.id))

        # タイムアウト変化
        before_to = before.timed_out_until
        after_to  = after.timed_out_until
        if before_to != after_to:
            if after_to:
                await send_log(self.bot, type="warn", title="タイムアウト付与",
                    description=f"{after.mention} にタイムアウトが付与されました。",
                    fields=[{"name": "解除予定", "value": f"<t:{int(after_to.timestamp())}:R>", "inline": True}],
                    user=after, guild_id=str(after.guild.id))
            else:
                await send_log(self.bot, type="info", title="タイムアウト解除",
                    description=f"{after.mention} のタイムアウトが解除されました。",
                    user=after, guild_id=str(after.guild.id))

    # ===== サーバー情報更新 =====
    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        changes = []
        if before.name != after.name:
            changes.append(f"名前: `{before.name}` → `{after.name}`")
        if before.icon != after.icon:
            changes.append("アイコンが変更されました")
        if before.owner_id != after.owner_id:
            changes.append(f"オーナー: <@{before.owner_id}> → <@{after.owner_id}>")
        if not changes:
            return
        await send_log(self.bot, type="info", title="サーバー情報更新",
            description="\n".join(changes),
            guild_id=str(after.id))

    # ===== チャンネル更新 / 権限更新 =====
    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        changes = []
        if before.name != after.name:
            changes.append(f"名前: `{before.name}` → `{after.name}`")
        if hasattr(before, 'topic') and before.topic != after.topic:
            changes.append("トピックが変更されました")
        if before.overwrites != after.overwrites:
            changes.append("権限設定が変更されました")
        if not changes:
            return
        await send_log(self.bot, type="info", title="チャンネル更新",
            description="\n".join(changes),
            fields=[{"name": "チャンネル", "value": after.mention, "inline": True}],
            guild_id=str(after.guild.id))

    # ===== チャンネル作成 =====
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        await send_log(self.bot, type="info", title="チャンネル作成",
            description="新しいチャンネルが作成されました。",
            fields=[{"name": "チャンネル", "value": channel.mention, "inline": True},
                    {"name": "種類", "value": str(channel.type), "inline": True}],
            guild_id=str(channel.guild.id))

    # ===== チャンネル削除 =====
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        await send_log(self.bot, type="warn", title="チャンネル削除",
            description="チャンネルが削除されました。",
            fields=[{"name": "チャンネル名", "value": f"`#{channel.name}`", "inline": True}],
            guild_id=str(channel.guild.id))

    # ===== ロール作成 =====
    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        await send_log(self.bot, type="info", title="ロール作成",
            description="新しいロールが作成されました。",
            fields=[{"name": "ロール", "value": role.mention, "inline": True}],
            guild_id=str(role.guild.id))

    # ===== ロール削除 =====
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        await send_log(self.bot, type="warn", title="ロール削除",
            description="ロールが削除されました。",
            fields=[{"name": "ロール名", "value": f"`{role.name}`", "inline": True}],
            guild_id=str(role.guild.id))

    # ===== メンバーBAN =====
    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        await send_log(self.bot, type="warn", title="メンバーBAN",
            description="メンバーがBANされました。",
            user=user, guild_id=str(guild.id))

    # ===== メンバーBAN解除 =====
    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        await send_log(self.bot, type="info", title="メンバーBAN解除",
            description="メンバーのBANが解除されました。",
            user=user, guild_id=str(guild.id))

    # ===== メンバーキック / 退出 =====
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await asyncio.sleep(0.5)
        try:
            async for entry in member.guild.audit_logs(action=discord.AuditLogAction.kick, limit=1):
                if entry.target.id == member.id and (time.time() - entry.created_at.timestamp()) < 3:
                    await send_log(self.bot, type="warn", title="メンバーキック",
                        description="メンバーがキックされました。",
                        user=member,
                        fields=[{"name": "実行者", "value": entry.user.mention, "inline": True}],
                        guild_id=str(member.guild.id))
                    return
        except Exception:
            pass
        await send_log(self.bot, type="info", title="メンバー退出",
            description="メンバーがサーバーを退出しました。",
            user=member, guild_id=str(member.guild.id))

    # ===== メッセージ編集 =====
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or before.content == after.content or not after.guild:
            return
        await send_log(self.bot, type="info", title="メッセージ編集",
            description=f"{after.channel.mention} でメッセージが編集されました。",
            user=after.author,
            fields=[
                {"name": "編集前", "value": before.content[:512] or "*(空)*", "inline": False},
                {"name": "編集後", "value": after.content[:512] or "*(空)*", "inline": False},
                {"name": "ジャンプ", "value": f"[メッセージを見る]({after.jump_url})", "inline": True},
            ],
            guild_id=str(after.guild.id))

    # ===== メッセージ削除 =====
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        await send_log(self.bot, type="warn", title="メッセージ削除",
            description=f"{message.channel.mention} でメッセージが削除されました。",
            user=message.author,
            fields=[{"name": "内容", "value": message.content[:512] or "*(空)*", "inline": False}],
            guild_id=str(message.guild.id))

    # ===== スラッシュコマンド使用 =====
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.application_command:
            return
        cmd = interaction.data.get("name", "不明")
        await send_log(self.bot, type="action", title="管理コマンド使用",
            description=f"`/{cmd}` が使用されました。",
            user=interaction.user,
            fields=[{"name": "チャンネル", "value": interaction.channel.mention if interaction.channel else "不明", "inline": True}],
            guild_id=str(interaction.guild_id) if interaction.guild_id else None)


async def setup(bot: commands.Bot):
    await bot.add_cog(EventLog(bot))
