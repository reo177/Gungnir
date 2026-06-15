import discord
from discord.ext import commands
from discord import app_commands
from bot.utils.logger import send_log


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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

        status = "🔒 ロックダウン有効" if enable else "🔓 ロックダウン解除"
        await interaction.followup.send(
            f"✅ {status} — 成功: {success}チャンネル / 失敗: {failed}チャンネル",
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
                {"name": "失敗", "value": f"{failed}チャンネル",  "inline": True},
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
            await interaction.response.send_message(f"✅ {user.mention} のBANを解除しました。", ephemeral=True)
            await send_log(
                self.bot,
                type="action",
                title="BAN解除",
                description="管理者がBAN解除を実行しました。",
                user=interaction.user,
                fields=[
                    {"name": "対象ユーザーID", "value": userid, "inline": True},
                    {"name": "理由",           "value": reason, "inline": False},
                ],
                guild_id=str(interaction.guild_id),
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ BAN解除に失敗しました: {e}", ephemeral=True)

    @app_commands.command(name="status", description="ボットの現在の設定・状態を確認します")
    @app_commands.default_permissions(administrator=True)
    async def status(self, interaction: discord.Interaction):
        import os
        from bot.utils.settings_store import get_settings
        s = get_settings(str(interaction.guild_id))

        embed = discord.Embed(title="🛡️ SecurityBot ステータス", color=0x00CC66)
        log_ch   = f"<#{s['logs']['channelId']}>"   if s['logs']['channelId']   else "❌ 未設定"
        verify_r = f"<@&{s['verify']['roleId']}>"   if s['verify']['roleId']    else "❌ 未設定"
        owner    = f"<@{os.getenv('OWNER_ID')}>"    if os.getenv('OWNER_ID')    else "❌ 未設定"

        embed.add_field(name="📋 ログチャンネル", value=log_ch,   inline=True)
        embed.add_field(name="✅ 認証ロール",      value=verify_r, inline=True)
        embed.add_field(name="👑 オーナー",        value=owner,    inline=True)
        embed.add_field(
            name="💣 アンチヌーク",
            value=f"{'有効' if s['antiNuke']['enabled'] else '無効'} — しきい値: {s['antiNuke']['threshold']}回 / {s['antiNuke']['interval']//1000}秒",
            inline=False,
        )
        embed.add_field(
            name="🚨 アンチレイド",
            value=f"{'有効' if s['antiRaid']['enabled'] else '無効'} — しきい値: {s['antiRaid']['threshold']}人 / {s['antiRaid']['interval']//1000}秒",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
