import os
import discord
from discord.ext import commands
from discord import app_commands
from bot.utils.logger import send_log


class VerifyView(discord.ui.View):
    """認証ボタンのView（永続化対応）"""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ 認証する", style=discord.ButtonStyle.success, custom_id="verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        role_id = os.getenv("VERIFY_ROLE_ID")
        if not role_id:
            return await interaction.response.send_message("❌ 認証ロールが設定されていません。管理者に連絡してください。", ephemeral=True)

        role = interaction.guild.get_role(int(role_id))
        if not role:
            return await interaction.response.send_message("❌ ロールが見つかりません。管理者に連絡してください。", ephemeral=True)

        member = interaction.user
        if role in member.roles:
            return await interaction.response.send_message("✅ すでに認証済みです！", ephemeral=True)

        try:
            await member.add_roles(role, reason="認証ボタンによる自動付与")
            await interaction.response.send_message("✅ 認証が完了しました！サーバーへようこそ！", ephemeral=True)
            await send_log(
                interaction.client,
                type="verify",
                title="認証完了",
                description="ユーザーが認証ボタンを使って認証しました。",
                user=member,
                fields=[
                    {"name": "付与ロール", "value": role.mention,                    "inline": True},
                    {"name": "チャンネル", "value": interaction.channel.mention,      "inline": True},
                ],
                guild_id=str(interaction.guild_id),
            )
        except Exception as e:
            print(f"[Verify] ロール付与エラー: {e}")
            await interaction.response.send_message("❌ ロールの付与に失敗しました。ボットの権限を確認してください。", ephemeral=True)


class Verify(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(VerifyView())  # ボット再起動後もボタンを有効に保つ

    @app_commands.command(name="verify-setup", description="認証パネルを設置します")
    @app_commands.describe(title="パネルのタイトル", description="パネルの説明文")
    @app_commands.default_permissions(administrator=True)
    async def verify_setup(
        self,
        interaction: discord.Interaction,
        title: str = "🛡️ サーバー認証",
        description: str = "下のボタンを押して認証を完了してください。\n認証するとサーバーのチャンネルにアクセスできるようになります。",
    ):
        embed = discord.Embed(
            title=title,
            description=description,
            color=0x5865F2,
        )
        embed.set_footer(text="認証ボタンを押すとロールが付与されます")

        await interaction.response.send_message("✅ 認証パネルを設置しました。", ephemeral=True)
        await interaction.channel.send(embed=embed, view=VerifyView())

        await send_log(
            self.bot,
            type="info",
            title="認証パネルを設置",
            description="管理者が認証パネルを設置しました。",
            user=interaction.user,
            fields=[{"name": "チャンネル", "value": interaction.channel.mention, "inline": True}],
            guild_id=str(interaction.guild_id),
        )

    @app_commands.command(name="verify-role", description="指定ユーザーに認証ロールを手動付与します")
    @app_commands.describe(user="認証するユーザー")
    @app_commands.default_permissions(manage_roles=True)
    async def verify_role(self, interaction: discord.Interaction, user: discord.Member):
        role_id = os.getenv("VERIFY_ROLE_ID")
        if not role_id:
            return await interaction.response.send_message("❌ 認証ロールが設定されていません。", ephemeral=True)

        role = interaction.guild.get_role(int(role_id))
        if not role:
            return await interaction.response.send_message("❌ ロールが見つかりません。", ephemeral=True)

        if role in user.roles:
            return await interaction.response.send_message(f"✅ {user.mention} はすでに認証済みです。", ephemeral=True)

        try:
            await user.add_roles(role, reason=f"手動認証: {interaction.user}")
            await interaction.response.send_message(f"✅ {user.mention} に認証ロールを付与しました。", ephemeral=True)
            await send_log(
                self.bot,
                type="verify",
                title="手動認証",
                description="管理者がユーザーを手動で認証しました。",
                user=user,
                fields=[
                    {"name": "実行者",   "value": interaction.user.mention, "inline": True},
                    {"name": "付与ロール", "value": role.mention,           "inline": True},
                ],
                guild_id=str(interaction.guild_id),
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ ロールの付与に失敗しました: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Verify(bot))
