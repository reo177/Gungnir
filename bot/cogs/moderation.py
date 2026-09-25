import os
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from bot.utils.logger import send_log

CREATOR_LINKS = [
    "https://discord.gg/g8ZfR8ZyTx",
    "https://discord.gg/Rjekxj6Cea",
    "https://discord.gg/PHKYM6Bt8t",
    "https://lwa70d3.com",
]


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _send_reason_dm(self, user: discord.abc.User, action: str, reason: str):
        try:
            await user.send(f"{action}\nReason: {reason}")
        except Exception:
            pass

    @app_commands.command(name="creator", description="作成者情報と招待URLをDMで送信します")
    async def creator(self, interaction: discord.Interaction):
        owner_id = os.getenv("OWNER_ID")
        owner_text = f"<@{owner_id}>" if owner_id else "未設定"
        embed = discord.Embed(
            title="作成者情報 / 招待リンク",
            description=f"作成者: {owner_text}\n以下のリンクを送信しました。",
            color=0x5865F2,
        )
        embed.add_field(
            name="招待リンク",
            value="\n".join(f"[{i + 1}]({url})" for i, url in enumerate(CREATOR_LINKS)),
            inline=False,
        )

        try:
            await interaction.user.send(embed=embed)
            await interaction.response.send_message("DMに作成者情報と招待URLを送信しました。", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("DMの送信に失敗しました。ユーザー設定でDM受信を許可してください。", ephemeral=True)

    @app_commands.command(name="warn", description="ユーザーに警告を付け、理由をDMで送信します")
    @app_commands.describe(user="対象ユーザー", reason="警告理由")
    @app_commands.default_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, user: discord.Member, reason: str = "理由なし"):
        if user.bot:
            return await interaction.response.send_message("BOTには警告を付けられません。", ephemeral=True)

        await self._send_reason_dm(user, "あなたは警告を受けました。", reason)
        await interaction.response.send_message(f"{user.mention} に警告を送信しました。", ephemeral=True)
        await send_log(
            self.bot,
            type="warn",
            title="警告",
            description=f"{user.mention} に警告を発行しました。",
            user=interaction.user,
            fields=[
                {"name": "対象ユーザー", "value": user.mention, "inline": True},
                {"name": "Reason", "value": reason, "inline": False},
            ],
            guild_id=str(interaction.guild_id),
        )

    @app_commands.command(name="mute", description="ユーザーをミュートし、理由をDMで送信します")
    @app_commands.describe(user="対象ユーザー", minutes="ミュート時間（分）", reason="理由")
    @app_commands.default_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, user: discord.Member, minutes: int = 10, reason: str = "理由なし"):
        if minutes <= 0:
            return await interaction.response.send_message("ミュート時間は1分以上を指定してください。", ephemeral=True)

        until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        await user.timeout(until, reason=reason)
        await self._send_reason_dm(user, f"{minutes}分のミュートが適用されました。", reason)
        await interaction.response.send_message(f"{user.mention} を {minutes} 分ミュートしました。", ephemeral=True)
        await send_log(
            self.bot,
            type="action",
            title="ミュート",
            description=f"{user.mention} がミュートされました。",
            user=interaction.user,
            fields=[
                {"name": "対象ユーザー", "value": user.mention, "inline": True},
                {"name": "時間", "value": f"{minutes}分", "inline": True},
                {"name": "Reason", "value": reason, "inline": False},
            ],
            guild_id=str(interaction.guild_id),
        )

    @app_commands.command(name="timeout", description="ユーザーにタイムアウトを付与し、理由をDMで送信します")
    @app_commands.describe(user="対象ユーザー", minutes="タイムアウト時間（分）", reason="理由")
    @app_commands.default_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, user: discord.Member, minutes: int = 10, reason: str = "理由なし"):
        await self.mute.callback(self, interaction, user, minutes, reason)

    @app_commands.command(name="kick", description="ユーザーをキックし、理由をDMで送信します")
    @app_commands.describe(user="対象ユーザー", reason="理由")
    @app_commands.default_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, user: discord.Member, reason: str = "理由なし"):
        await interaction.guild.kick(user, reason=reason)
        await self._send_reason_dm(user, "あなたはキックされました。", reason)
        await interaction.response.send_message(f"{user.mention} をキックしました。", ephemeral=True)
        await send_log(
            self.bot,
            type="warn",
            title="キック",
            description=f"{user.mention} がキックされました。",
            user=interaction.user,
            fields=[
                {"name": "対象ユーザー", "value": user.mention, "inline": True},
                {"name": "Reason", "value": reason, "inline": False},
            ],
            guild_id=str(interaction.guild_id),
        )

    @app_commands.command(name="ban", description="ユーザーをBANし、理由をDMで送信します")
    @app_commands.describe(user="対象ユーザー", reason="理由", delete_days="メッセージ削除日数")
    @app_commands.default_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, user: discord.Member, reason: str = "理由なし", delete_days: int = 0):
        if not 0 <= delete_days <= 7:
            return await interaction.response.send_message("削除日数は0〜7の範囲で指定してください。", ephemeral=True)

        await interaction.guild.ban(user, reason=reason, delete_message_days=delete_days)
        await self._send_reason_dm(user, "あなたはBANされました。", reason)
        await interaction.response.send_message(f"{user.mention} をBANしました。", ephemeral=True)
        await send_log(
            self.bot,
            type="warn",
            title="BAN",
            description=f"{user.mention} がBANされました。",
            user=interaction.user,
            fields=[
                {"name": "対象ユーザー", "value": user.mention, "inline": True},
                {"name": "Reason", "value": reason, "inline": False},
                {"name": "削除日数", "value": str(delete_days), "inline": True},
            ],
            guild_id=str(interaction.guild_id),
        )

    @app_commands.command(name="banlist", description="BAN一覧と理由を表示します")
    @app_commands.default_permissions(ban_members=True)
    async def banlist(self, interaction: discord.Interaction):
        bans = await interaction.guild.bans(limit=1000)
        if not bans:
            return await interaction.response.send_message("対象が存在しません。BANされているユーザーはいません。", ephemeral=True)

        entries = []
        for entry in bans:
            reason = entry.reason or "理由なし"
            entries.append(f"{entry.user.mention} | {entry.user.id} | Reason: {reason}")

        embed = discord.Embed(title="BAN一覧", description="\n".join(entries[:15]), color=0x5865F2)
        if len(entries) > 15:
            embed.set_footer(text=f"他 {len(entries) - 15} 件")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="audit", description="直近の監査ログを表示します")
    @app_commands.default_permissions(administrator=True)
    async def audit(self, interaction: discord.Interaction):
        lines = []
        async for entry in interaction.guild.audit_logs(limit=10):
            target = entry.target.mention if hasattr(entry.target, "mention") else str(entry.target)
            lines.append(f"{entry.action.name} | {entry.user.mention if entry.user else '不明'} | {target} | Reason: {entry.reason or '理由なし'}")

        if not lines:
            return await interaction.response.send_message("対象が存在しません。監査ログがありません。", ephemeral=True)

        embed = discord.Embed(title="監査ログ", description="\n".join(lines), color=0x5865F2)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="join-log", description="直近の入室ログを表示します")
    @app_commands.default_permissions(administrator=True)
    async def join_log(self, interaction: discord.Interaction):
        join_cog = self.bot.get_cog("EventLog")
        if not join_cog:
            return await interaction.response.send_message("入室ログが利用できません。", ephemeral=True)

        rows = []
        for item in getattr(join_cog, "recent_joins", [])[:10]:
            if item.get("guild_id") != str(interaction.guild_id):
                continue
            user = self.bot.get_user(item["user_id"])
            name = user.mention if user else f"<@{item['user_id']}>"
            rows.append(f"{name} | <t:{int(item['timestamp'])}:F>")

        if not rows:
            return await interaction.response.send_message("対象が存在しません。直近の入室記録はありません。", ephemeral=True)

        embed = discord.Embed(title="入室ログ", description="\n".join(rows), color=0x5865F2)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="server-info", description="サーバーの基本情報を表示します")
    @app_commands.default_permissions(administrator=True)
    async def server_info(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(title=guild.name, color=0x5865F2)
        embed.add_field(name="所属人数", value=str(guild.member_count), inline=True)
        embed.add_field(name="オーナー", value=guild.owner.mention if guild.owner else "不明", inline=True)
        embed.add_field(name="作成日", value=f"<t:{int(guild.created_at.timestamp())}:F>", inline=True)
        embed.add_field(name="ベースレベル", value=str(guild.premium_tier), inline=True)
        embed.add_field(name="ブースト数", value=str(guild.premium_subscription_count or 0), inline=True)
        embed.add_field(name="認証レベル", value=str(guild.verification_level).replace("_", " "), inline=True)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="purge", description="メッセージをまとめて削除します")
    @app_commands.describe(count="削除件数", reason="削除理由")
    @app_commands.default_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, count: int, reason: str = "整理"):
        if count < 1 or count > 100:
            return await interaction.response.send_message("削除件数は1〜100の範囲で指定してください。", ephemeral=True)

        await interaction.channel.purge(limit=count, reason=reason)
        await interaction.response.send_message(f"{count}件のメッセージを削除しました。", ephemeral=True)

    @app_commands.command(name="lockdown", description="サーバーのロックダウンを手動で切り替えます")
    @app_commands.describe(enable="True=ロックダウン有効 / False=解除")
    @app_commands.default_permissions(administrator=True)
    async def lockdown(self, interaction: discord.Interaction, enable: bool):
        await interaction.response.defer(ephemeral=True)

        everyone = interaction.guild.default_role
        success = failed = 0

        for channel in interaction.guild.text_channels:
            try:
                overwrite = channel.overwrites_for(everyone)
                overwrite.send_messages = False if enable else None
                await channel.set_permissions(everyone, overwrite=overwrite)
                success += 1
            except Exception:
                failed += 1

        status = "ロックダウン有効" if enable else "ロックダウン解除"
        await interaction.followup.send(
            f"{status} — 成功: {success}チャンネル / 失敗: {failed}チャンネル",
            ephemeral=True,
        )
        await send_log(
            self.bot,
            type="warn" if enable else "info",
            title=status,
            description=f"管理者がロックダウンを{'有効' if enable else '解除'}しました。",
            user=interaction.user,
            fields=[
                {"name": "成功", "value": f"{success}チャンネル", "inline": True},
                {"name": "失敗", "value": f"{failed}チャンネル", "inline": True},
            ],
            guild_id=str(interaction.guild_id),
        )

    @app_commands.command(name="unban", description="BANされたユーザーのBANを解除します")
    @app_commands.describe(userid="解除するユーザーのID", reason="解除理由")
    @app_commands.default_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, userid: str, reason: str = "理由なし"):
        try:
            user = await self.bot.fetch_user(int(userid))
            await interaction.guild.unban(user, reason=reason)
            await interaction.response.send_message(f"{user.mention} のBANを解除しました。", ephemeral=True)
            await send_log(
                self.bot,
                type="action",
                title="BAN解除",
                description="管理者がBAN解除を実行しました。",
                user=interaction.user,
                fields=[
                    {"name": "対象ユーザーID", "value": userid, "inline": True},
                    {"name": "理由", "value": reason, "inline": False},
                ],
                guild_id=str(interaction.guild_id),
            )
        except Exception as e:
            await interaction.response.send_message(f"BAN解除に失敗しました: {e}", ephemeral=True)

    @app_commands.command(name="status", description="ボットの現在の設定・状態を確認します")
    @app_commands.default_permissions(administrator=True)
    async def status(self, interaction: discord.Interaction):
        from bot.utils.settings_store import get_settings

        s = get_settings(str(interaction.guild_id))
        embed = discord.Embed(title="SecurityBot ステータス", color=0x00CC66)
        log_ch = f"<#{s['logs']['channelId']}>" if s['logs']['channelId'] else "未設定"
        verify_r = f"<@&{s['verify']['roleId']}>" if s['verify']['roleId'] else "未設定"
        owner = f"<@{os.getenv('OWNER_ID')}>" if os.getenv('OWNER_ID') else "未設定"

        embed.add_field(name="ログチャンネル", value=log_ch, inline=True)
        embed.add_field(name="認証ロール", value=verify_r, inline=True)
        embed.add_field(name="オーナー", value=owner, inline=True)
        embed.add_field(
            name="アンチヌーク",
            value=f"{'有効' if s['antiNuke']['enabled'] else '無効'} — しきい値: {s['antiNuke']['threshold']}回 / {s['antiNuke']['interval']//1000}秒",
            inline=False,
        )
        embed.add_field(
            name="アンチレイド",
            value=f"{'有効' if s['antiRaid']['enabled'] else '無効'} — しきい値: {s['antiRaid']['threshold']}人 / {s['antiRaid']['interval']//1000}秒",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
