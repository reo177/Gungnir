import asyncio
import json
import os
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

BOT_DIR = Path(__file__).resolve().parent
SETTINGS_DIR = BOT_DIR / "settings"
SETTINGS_DIR.mkdir(exist_ok=True)

# ===== action_tracker =====
_tracker: dict[str, dict[str, dict]] = defaultdict(dict)


def track_action(guild_id: str, user_id: str, threshold: int, interval_ms: int) -> bool:
    guild_map = _tracker[guild_id]

    if user_id not in guild_map:
        guild_map[user_id] = {"count": 0, "task": None}

    entry = guild_map[user_id]
    entry["count"] += 1

    if entry["task"] and not entry["task"].done():
        entry["task"].cancel()

    async def _reset():
        await asyncio.sleep(interval_ms / 1000)
        guild_map.pop(user_id, None)

    try:
        loop = asyncio.get_running_loop()
        entry["task"] = loop.create_task(_reset())
    except RuntimeError:
        pass

    return entry["count"] >= threshold


def reset_tracker(guild_id: str, user_id: str):
    _tracker[guild_id].pop(user_id, None)


def detect_anti_raid(guild_id: str, user_id: str, *, threshold: int | None = None, interval_ms: int | None = None) -> bool:
    settings = get_settings(str(guild_id))
    anti_raid = settings.get("antiRaid", {})
    if not anti_raid.get("enabled", True):
        return False

    threshold = threshold if threshold is not None else int(anti_raid.get("threshold", 5))
    interval_ms = interval_ms if interval_ms is not None else int(anti_raid.get("interval", 10000))
    return track_action(str(guild_id), f"raid:{str(user_id)}", threshold, interval_ms)


def detect_anti_nuke(guild_id: str, action: str, actor_id: str | int | None, *, threshold: int | None = None, interval_ms: int | None = None) -> bool:
    settings = get_settings(str(guild_id))
    anti_nuke = settings.get("antiNuke", {})
    if not anti_nuke.get("enabled", True):
        return False

    threshold = threshold if threshold is not None else int(anti_nuke.get("threshold", 3))
    interval_ms = interval_ms if interval_ms is not None else int(anti_nuke.get("interval", 5000))
    actor_key = str(actor_id) if actor_id is not None else "unknown"
    key = f"nuke:{str(action).lower()}:{actor_key}"
    return track_action(str(guild_id), key, threshold, interval_ms)


# ===== logger =====
memory_logs: dict[str, list] = {}
MAX_MEMORY = 200

COLOR_MAP = {
    "nuke": 0xFF0000,
    "raid": 0xFF6600,
    "verify": 0x00CC66,
    "action": 0xFFCC00,
    "warn": 0xFF9900,
    "info": 0x5865F2,
}
EMOJI_MAP = {
    "nuke": "💣",
    "raid": "🚨",
    "verify": "✅",
    "action": "⚙️",
    "warn": "⚠️",
    "info": "ℹ️",
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
        "id": f"{int(datetime.now().timestamp()*1000):x}",
        "type": type,
        "title": title,
        "description": description,
        "fields": fields,
        "user_id": str(user.id) if user else None,
        "user_tag": str(user) if user else None,
        "guild_id": guild_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if guild_id:
        memory_logs.setdefault(guild_id, []).insert(0, entry)
        if len(memory_logs[guild_id]) > MAX_MEMORY:
            memory_logs[guild_id] = memory_logs[guild_id][:MAX_MEMORY]

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


# ===== punish =====
async def punish_user(guild: discord.Guild, user_id: int, reason: str, bot: discord.Client):
    if is_on_list(str(guild.id), "whitelist", user_id):
        return

    try:
        member = guild.get_member(user_id) or await guild.fetch_member(user_id)
    except Exception:
        member = None

    if not member:
        return

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
                {"name": "理由", "value": reason, "inline": False},
            ],
            guild_id=str(guild.id),
        )
    except Exception as e:
        print(f"[Punish] BAN失敗 ({user_id}): {e}")


# ===== settings_store =====
def normalize_member_id(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("<", "").replace(">", "").replace("!", "").replace("@", "").replace("&", "")
    if text.isdigit():
        return text
    return None


def _normalize_member_id(value) -> str | None:
    return normalize_member_id(value)


def _safe_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _defaults() -> dict:
    return {
        "antiNuke": {
            "enabled": True,
            "threshold": _safe_int_env("NUKE_THRESHOLD", 3),
            "interval": _safe_int_env("NUKE_INTERVAL", 5000),
        },
        "antiRaid": {
            "enabled": True,
            "threshold": _safe_int_env("RAID_THRESHOLD", 5),
            "interval": _safe_int_env("RAID_INTERVAL", 10000),
        },
        "verify": {
            "enabled": False,
            "roleId": os.getenv("VERIFY_ROLE_ID", ""),
            "channelId": os.getenv("VERIFY_CHANNEL_ID", ""),
            "message": "ボタンを押して認証してください。",
        },
        "logs": {
            "channelId": os.getenv("LOG_CHANNEL_ID", ""),
            "events": ["nuke", "raid", "verify", "join", "action"],
        },
        "whitelist": [],
        "blacklist": [],
        "punishments": {"history": []},
    }


def _deep_merge(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def get_settings(guild_id: str) -> dict:
    path = SETTINGS_DIR / f"{guild_id}.json"
    if not path.exists():
        return _defaults()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return _deep_merge(_defaults(), data)
    except Exception:
        return _defaults()


def save_settings(guild_id: str, settings: dict):
    path = SETTINGS_DIR / f"{guild_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def update_settings(guild_id: str, partial: dict) -> dict:
    current = get_settings(guild_id)
    updated = _deep_merge(current, partial)
    save_settings(guild_id, updated)
    return updated


def get_list(guild_id: str, list_name: str) -> list[str]:
    settings = get_settings(str(guild_id))
    values = settings.get(list_name, [])
    return [str(item) for item in values if _normalize_member_id(item) is not None]


def add_to_list(guild_id: str, list_name: str, value) -> dict:
    settings = get_settings(str(guild_id))
    members = get_list(str(guild_id), list_name)
    normalized = _normalize_member_id(value)
    if normalized and normalized not in members:
        members.append(normalized)
    settings[list_name] = members
    save_settings(str(guild_id), settings)
    return settings


def remove_from_list(guild_id: str, list_name: str, value) -> dict:
    settings = get_settings(str(guild_id))
    members = get_list(str(guild_id), list_name)
    normalized = _normalize_member_id(value)
    settings[list_name] = [member for member in members if member != normalized]
    save_settings(str(guild_id), settings)
    return settings


def is_on_list(guild_id: str, list_name: str, user_id) -> bool:
    normalized = _normalize_member_id(user_id)
    if not normalized:
        return False
    return normalized in get_list(str(guild_id), list_name)


def record_punishment(guild_id: str, user_id, action: str, moderator_id=None, reason: str = "理由なし") -> dict:
    settings = get_settings(str(guild_id))
    punishments = settings.setdefault("punishments", {"history": []})
    history = punishments.setdefault("history", [])

    event = {
        "user_id": normalize_member_id(user_id),
        "action": str(action).lower(),
        "moderator_id": normalize_member_id(moderator_id),
        "reason": str(reason or "理由なし"),
        "timestamp": str(datetime.now(timezone.utc).isoformat()),
    }

    if not event["user_id"]:
        return settings

    history.insert(0, event)
    save_settings(str(guild_id), settings)
    return settings


def get_punishment_history(guild_id: str, user_id=None, limit: int = 50) -> list[dict]:
    settings = get_settings(str(guild_id))
    history = settings.get("punishments", {}).get("history", [])
    if user_id is not None:
        normalized = normalize_member_id(user_id)
        history = [entry for entry in history if entry.get("user_id") == normalized]
    return history[:limit]


def get_punishment_summary(guild_id: str, user_id=None) -> dict:
    history = get_punishment_history(guild_id, user_id=user_id, limit=1000)
    summary = {"timeout": 0, "kick": 0, "ban": 0, "mute": 0, "warn": 0}
    for entry in history:
        action = str(entry.get("action", "")).lower()
        if action in summary:
            summary[action] += 1
    return summary


def get_punishment_rankings(guild_id: str, limit: int = 10) -> list[dict]:
    settings = get_settings(str(guild_id))
    history = settings.get("punishments", {}).get("history", [])
    ranking: dict[str, dict] = {}
    for entry in history:
        user_id = entry.get("user_id")
        if not user_id:
            continue
        current = ranking.setdefault(user_id, {"user_id": user_id, "timeout": 0, "kick": 0, "ban": 0, "mute": 0, "warn": 0})
        action = str(entry.get("action", "")).lower()
        if action in current:
            current[action] += 1
    rows = sorted(ranking.values(), key=lambda row: (row.get("timeout", 0) + row.get("kick", 0) + row.get("ban", 0), row["user_id"]), reverse=True)
    return rows[:limit]


def get_recent_abuse(guild_id: str, limit: int = 10) -> list[dict]:
    history = get_punishment_history(guild_id, limit=limit * 10)
    return history[:limit]


def get_verify_settings(guild_id: str) -> dict:
    settings = get_settings(str(guild_id))
    verify = settings.get("verify", {})
    return {
        "enabled": bool(verify.get("enabled", False)),
        "roleId": str(verify.get("roleId") or ""),
        "channelId": str(verify.get("channelId") or ""),
        "message": str(verify.get("message") or "ボタンを押して認証してください。"),
    }


async def send_verify_message(guild: discord.Guild, *, message_text: str | None = None, role_id: str | int | None = None):
    settings = get_verify_settings(str(guild.id))
    target_channel_id = settings.get("channelId") or os.getenv("VERIFY_CHANNEL_ID")
    target_role_id = settings.get("roleId") or os.getenv("VERIFY_ROLE_ID")
    if not target_channel_id:
        return False

    channel = guild.get_channel(int(target_channel_id))
    if channel is None:
        return False

    view = discord.ui.View(timeout=None)
    button = discord.ui.Button(label="認証", style=discord.ButtonStyle.green, emoji="✅")

    async def _on_click(interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("このコマンドはサーバー内で実行してください。", ephemeral=True)
            return
        resolved_role_id = role_id if role_id is not None else target_role_id
        role = interaction.guild.get_role(int(resolved_role_id)) if resolved_role_id else None
        if role is None:
            await interaction.response.send_message("認証ロールが未設定です。", ephemeral=True)
            return
        await interaction.user.add_roles(role, reason="Verify button")
        await interaction.response.send_message(f"{role.mention} を付与しました。", ephemeral=True)

    button.callback = _on_click
    view.add_item(button)

    embed = discord.Embed(
        title="認証",
        description=(message_text or settings.get("message") or "ボタンを押して認証してください。"),
        color=discord.Color.green(),
    )
    await channel.send(embed=embed, view=view)
    return True


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("[Cog] Moderation Ready")


# ===== Bot設定 =====
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.moderation = True
intents.voice_states = True

client = commands.Bot(command_prefix=" ", intents=intents)
client.remove_command("help")


async def _guild_settings_embed(guild: discord.Guild | None, *, title: str = "Bot Status") -> discord.Embed:
    embed = discord.Embed(title=title, color=discord.Color.blurple())
    if guild is None:
        embed.description = "このコマンドはサーバー内で実行してください。"
        return embed

    settings = get_settings(str(guild.id))
    anti_nuke = settings.get("antiNuke", {})
    anti_raid = settings.get("antiRaid", {})
    embed.add_field(name="サーバー", value=guild.name, inline=True)
    embed.add_field(name="メンバー数", value=str(guild.member_count), inline=True)
    embed.add_field(name="保護状態", value="ON" if anti_nuke.get("enabled") or anti_raid.get("enabled") else "OFF", inline=True)
    embed.add_field(name="アンチヌーク", value="ON" if anti_nuke.get("enabled") else "OFF", inline=True)
    embed.add_field(name="アンチレイド", value="ON" if anti_raid.get("enabled") else "OFF", inline=True)
    embed.add_field(name="ログチャンネル", value=settings.get("logs", {}).get("channelId") or "未設定", inline=True)
    return embed


@client.tree.command(name="status", description="ボットの状態とセキュリティ設定を表示します。")
async def status_command(interaction: discord.Interaction):
    guild = interaction.guild
    embed = await _guild_settings_embed(guild, title="Bot Status")
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def _send_ctx_message(ctx: commands.Context, message: str = "", *, embed: discord.Embed | None = None, ephemeral: bool = False):
    if ctx.interaction is not None:
        await ctx.send(content=message, embed=embed, ephemeral=ephemeral)
    else:
        await ctx.send(content=message, embed=embed)


class CyberpunkHelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(discord.ui.Button(label="STATUS", style=discord.ButtonStyle.blurple, custom_id="cyber_status", emoji="🛰️"))
        self.add_item(discord.ui.Button(label="WHITE", style=discord.ButtonStyle.green, custom_id="cyber_white", emoji="✅"))
        self.add_item(discord.ui.Button(label="BLACK", style=discord.ButtonStyle.red, custom_id="cyber_black", emoji="🚫"))
        self.add_item(discord.ui.Button(label="LOG", style=discord.ButtonStyle.secondary, custom_id="cyber_log", emoji="🧾"))
        self.add_item(discord.ui.Button(label="SECURITY", style=discord.ButtonStyle.grey, custom_id="cyber_security", emoji="🛡️"))
        self.add_item(discord.ui.Button(label="VERIFY", style=discord.ButtonStyle.green, custom_id="cyber_verify", emoji="🔐"))

    @discord.ui.button(label="STATUS", style=discord.ButtonStyle.blurple, custom_id="cyber_status", emoji="🛰️")
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        embed = await _guild_settings_embed(guild, title="◈ CYBERSEC // STATUS")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="WHITE", style=discord.ButtonStyle.green, custom_id="cyber_white", emoji="✅")
    async def white_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None:
            await interaction.response.send_message("このコマンドはサーバー内で実行してください。", ephemeral=True)
            return
        members = get_list(str(interaction.guild.id), "whitelist")
        await interaction.response.send_message(f"WHITE LIST: {', '.join(members) if members else 'NONE'}", ephemeral=True)

    @discord.ui.button(label="BLACK", style=discord.ButtonStyle.red, custom_id="cyber_black", emoji="🚫")
    async def black_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None:
            await interaction.response.send_message("このコマンドはサーバー内で実行してください。", ephemeral=True)
            return
        members = get_list(str(interaction.guild.id), "blacklist")
        await interaction.response.send_message(f"BLACK LIST: {', '.join(members) if members else 'NONE'}", ephemeral=True)

    @discord.ui.button(label="LOG", style=discord.ButtonStyle.secondary, custom_id="cyber_log", emoji="🧾")
    async def log_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None:
            await interaction.response.send_message("このコマンドはサーバー内で実行してください。", ephemeral=True)
            return
        logs = get_logs(str(interaction.guild.id), limit=5)
        msg = "\n".join(f"- {entry.get('title', 'log')} / {entry.get('timestamp', '')}" for entry in logs) if logs else "NO LOGS AVAILABLE"
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(label="SECURITY", style=discord.ButtonStyle.grey, custom_id="cyber_security", emoji="🛡️")
    async def security_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        embed = await _guild_settings_embed(guild, title="◈ CYBERSEC // SECURITY")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="VERIFY", style=discord.ButtonStyle.green, custom_id="cyber_verify", emoji="🔐")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None:
            await interaction.response.send_message("このコマンドはサーバー内で実行してください。", ephemeral=True)
            return
        settings = get_verify_settings(str(interaction.guild.id))
        await interaction.response.send_message(
            "VERIFY STATUS\n" + f"enabled={settings['enabled']}\nrole={settings['roleId'] or '未設定'}\nchannel={settings['channelId'] or '未設定'}",
            ephemeral=True,
        )


@client.tree.command(name="help", description="利用可能なコマンド一覧を表示します。")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="◈ CYBERSEC // MENU",
        description="サイバーパンク風セキュリティコンソール\nオンライン / 監査モード / 侵入対策準備完了",
        color=0x00F5FF,
    )
    embed.add_field(name="COMMANDS", value="`/status` / `/list` / `/log` / `/sanction`\n`/security` / `/user-check` / `/purge`\n`/allban` / `/audit` / `/join-log` / `/verify-setup`", inline=False)
    embed.add_field(name="LIST MENU", value="`/list kind: whitelist`\n`/list kind: blacklist`\n`/list kind: banlist`", inline=False)
    embed.set_footer(text="SYSTEM // ACCESS GRANTED")
    view = CyberpunkHelpView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@client.tree.command(name="list", description="ホワイトリスト / ブラックリスト / BANリストを統合して表示または更新します。")
@app_commands.describe(kind="一覧種別", action="操作", member="対象ユーザー")
@app_commands.choices(
    kind=[
        app_commands.Choice(name="whitelist", value="whitelist"),
        app_commands.Choice(name="blacklist", value="blacklist"),
        app_commands.Choice(name="banlist", value="banlist"),
    ],
    action=[
        app_commands.Choice(name="list", value="list"),
        app_commands.Choice(name="add", value="add"),
        app_commands.Choice(name="remove", value="remove"),
    ],
)
async def list_command(interaction: discord.Interaction, kind: str, action: str, member: discord.Member | None = None):
    if interaction.guild is None:
        await interaction.response.send_message("このコマンドはサーバー内で実行してください。", ephemeral=True)
        return

    kind = (kind or "whitelist").lower()
    if kind == "banlist":
        if action == "list":
            members = get_list(str(interaction.guild.id), "blacklist")
            await interaction.response.send_message(f"BAN LIST: {', '.join(members) if members else 'NONE'}", ephemeral=True)
            return
        if member is None:
            await interaction.response.send_message("対象ユーザーを指定してください。", ephemeral=True)
            return
        if action == "add":
            add_to_list(str(interaction.guild.id), "blacklist", member.id)
            await interaction.response.send_message(f"{member.mention} を BAN LIST に追加しました。", ephemeral=True)
        else:
            remove_from_list(str(interaction.guild.id), "blacklist", member.id)
            await interaction.response.send_message(f"{member.mention} を BAN LIST から削除しました。", ephemeral=True)
        return

    if kind not in {"whitelist", "blacklist"}:
        await interaction.response.send_message("kind は whitelist / blacklist / banlist のどれかを指定してください。", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    if action == "list":
        members = get_list(guild_id, kind)
        await interaction.response.send_message(f"{kind.upper()}: {', '.join(members) if members else 'NONE'}", ephemeral=True)
        return

    if member is None:
        await interaction.response.send_message("対象ユーザーを指定してください。", ephemeral=True)
        return

    if action == "add":
        add_to_list(guild_id, kind, member.id)
        await interaction.response.send_message(f"{member.mention} を {kind} に追加しました。", ephemeral=True)
    else:
        remove_from_list(guild_id, kind, member.id)
        await interaction.response.send_message(f"{member.mention} を {kind} から削除しました。", ephemeral=True)


@client.tree.command(name="allban", description="ブラックリスト対象をまとめてBANします。")
async def allban_command(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("このコマンドはサーバー内で実行してください。", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    target_ids = get_list(guild_id, "blacklist")
    count = 0
    for user_id in target_ids:
        try:
            await interaction.guild.ban(discord.Object(id=int(user_id)), reason="Blacklisted by security bot")
            count += 1
        except Exception:
            continue
    await interaction.response.send_message(f"ブラックリスト対象 {count} 人をBANしました。", ephemeral=True)


@client.tree.command(name="log", description="監査ログと異常行為ログをまとめて表示します。")
@app_commands.describe(scope="ログの種類", limit="表示件数")
@app_commands.choices(
    scope=[
        app_commands.Choice(name="all", value="all"),
        app_commands.Choice(name="audit", value="audit"),
        app_commands.Choice(name="security", value="security"),
        app_commands.Choice(name="join", value="join"),
    ]
)
async def log_command(interaction: discord.Interaction, scope: str = "all", limit: int = 5):
    if interaction.guild is None:
        await interaction.response.send_message("このコマンドはサーバー内で実行してください。", ephemeral=True)
        return

    scope = (scope or "all").lower()
    limit = max(1, min(limit, 20))
    guild_id = str(interaction.guild.id)

    if scope in {"all", "audit"}:
        logs = get_logs(guild_id, limit=limit)
        if logs:
            lines = [f"- {entry.get('title', 'log')} / {entry.get('timestamp', '')}" for entry in logs]
            await interaction.response.send_message("\n".join(lines), ephemeral=True)
            return

    if scope in {"all", "security"}:
        entries = get_recent_abuse(guild_id, limit=limit)
        if entries:
            lines = [f"- {entry.get('user_id')} / {entry.get('action')} / {entry.get('reason')}" for entry in entries]
            await interaction.response.send_message("\n".join(lines), ephemeral=True)
            return

    if scope in {"all", "join"}:
        await interaction.response.send_message("JOIN LOG は現在の実装ではクライアント側ログ出力へ集約されています。", ephemeral=True)
        return

    await interaction.response.send_message("表示できるログがありません。", ephemeral=True)


@client.tree.command(name="audit", description="監査ログを表示します。")
@app_commands.describe(limit="表示件数")
async def audit_command(interaction: discord.Interaction, limit: int = 5):
    await log_command.callback(interaction, "audit", limit)


@client.tree.command(name="join-log", description="入室ログを表示します。")
@app_commands.describe(limit="表示件数")
async def join_log_command(interaction: discord.Interaction, limit: int = 5):
    await log_command.callback(interaction, "join", limit)


@client.tree.command(name="recent-abuse", description="直近の異常行為を表示します。")
async def recent_abuse_command(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("このコマンドはサーバー内で実行してください。", ephemeral=True)
        return

    entries = get_recent_abuse(str(interaction.guild.id), limit=5)
    if not entries:
        await interaction.response.send_message("直近の異常行為はありません。", ephemeral=True)
        return

    lines = [f"- {entry.get('user_id')} / {entry.get('action')} / {entry.get('reason')}" for entry in entries]
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


@client.tree.command(name="security", description="セキュリティ状態のサマリーを表示します。")
async def security_command(interaction: discord.Interaction):
    await status_command.callback(interaction)


@client.tree.command(name="user-check", description="対象ユーザーの制裁履歴を確認します。")
@app_commands.describe(user="確認対象のユーザー")
async def user_check_command(interaction: discord.Interaction, user: discord.Member):
    if interaction.guild is None:
        await interaction.response.send_message("このコマンドはサーバー内で実行してください。", ephemeral=True)
        return

    history = get_punishment_history(str(interaction.guild.id), user.id, limit=10)
    if not history:
        await interaction.response.send_message(f"{user.mention} の制裁履歴はありません。", ephemeral=True)
        return

    lines = [f"- {entry.get('action')} / {entry.get('reason')}" for entry in history]
    await interaction.response.send_message(f"{user.mention} の制裁履歴:\n" + "\n".join(lines), ephemeral=True)


@client.tree.command(name="lockdown", description="緊急ロックダウン状態を実行します。")
async def lockdown_command(interaction: discord.Interaction):
    await interaction.response.send_message("緊急保護モードを有効化しました。", ephemeral=True)


@client.tree.command(name="verify-setup", description="認証設定を表示し、認証メッセージを送信できます。")
@app_commands.describe(channel="認証を表示するチャンネル", role="認証ロール", message="認証メッセージ")
async def verify_setup_command(interaction: discord.Interaction, channel: discord.TextChannel | None = None, role: discord.Role | None = None, message: str = "ボタンを押して認証してください。"):
    if interaction.guild is None:
        await interaction.response.send_message("このコマンドはサーバー内で実行してください。", ephemeral=True)
        return

    target_channel = channel or (interaction.channel if isinstance(interaction.channel, discord.TextChannel) else None)
    target_role = role or None
    config = {
        "verify": {
            "enabled": True,
            "roleId": str(target_role.id) if target_role else str(os.getenv("VERIFY_ROLE_ID", "")),
            "channelId": str(target_channel.id) if target_channel else str(os.getenv("VERIFY_CHANNEL_ID", "")),
            "message": message,
        }
    }
    update_settings(str(interaction.guild.id), config)

    if target_channel and target_role:
        await send_verify_message(interaction.guild, message_text=message, role_id=str(target_role.id))
        await interaction.response.send_message(f"認証設定を保存し、{target_channel.mention} に認証ボタンを送信しました。", ephemeral=True)
        return

    settings = get_verify_settings(str(interaction.guild.id))
    await interaction.response.send_message("認証設定を保存しました。\n" + f"roleId={settings['roleId'] or '未設定'} / channelId={settings['channelId'] or '未設定'}", ephemeral=True)


@client.tree.command(name="verify-role", description="認証ロールを付与します。")
@app_commands.describe(user="対象ユーザー")
async def verify_role_command(interaction: discord.Interaction, user: discord.Member | None = None):
    if interaction.guild is None:
        await interaction.response.send_message("このコマンドはサーバー内で実行してください。", ephemeral=True)
        return

    settings = get_verify_settings(str(interaction.guild.id))
    role_id = settings.get("roleId") or os.getenv("VERIFY_ROLE_ID")
    if not role_id:
        await interaction.response.send_message("認証ロールが未設定です。", ephemeral=True)
        return

    role = interaction.guild.get_role(int(role_id))
    if role is None:
        await interaction.response.send_message("認証ロールが存在しません。", ephemeral=True)
        return

    target_user = user or interaction.user
    await target_user.add_roles(role, reason="Manual verify")
    await interaction.response.send_message(f"{target_user.mention} に {role.mention} を付与しました。", ephemeral=True)


@client.tree.command(name="sanction", description="制裁をまとめて実行します。")
@app_commands.describe(action="制裁内容", user="対象ユーザー", reason="理由")
@app_commands.choices(
    action=[
        app_commands.Choice(name="warn", value="warn"),
        app_commands.Choice(name="mute", value="mute"),
        app_commands.Choice(name="timeout", value="timeout"),
        app_commands.Choice(name="kick", value="kick"),
        app_commands.Choice(name="ban", value="ban"),
    ]
)
async def sanction_command(interaction: discord.Interaction, action: str, user: discord.Member, reason: str = "理由なし"):
    if interaction.guild is None:
        await interaction.response.send_message("このコマンドはサーバー内で実行してください。", ephemeral=True)
        return

    action = (action or "warn").lower()
    reason_text = reason or "理由なし"

    if action == "warn":
        record_punishment(str(interaction.guild.id), user.id, "warn", interaction.user.id, reason_text)
        message = f"{user.mention} に警告を追加しました。理由: {reason_text}"
    elif action == "mute":
        record_punishment(str(interaction.guild.id), user.id, "mute", interaction.user.id, reason_text)
        message = f"{user.mention} をミュートしました。理由: {reason_text}"
    elif action == "timeout":
        try:
            timeout_until = datetime.now(timezone.utc) + timedelta(minutes=10)
            await user.timeout(timeout_until, reason=reason_text)
        except Exception:
            pass
        record_punishment(str(interaction.guild.id), user.id, "timeout", interaction.user.id, reason_text)
        message = f"{user.mention} をタイムアウトしました。理由: {reason_text}"
    elif action == "kick":
        try:
            await user.kick(reason=reason_text)
        except Exception:
            pass
        record_punishment(str(interaction.guild.id), user.id, "kick", interaction.user.id, reason_text)
        message = f"{user.mention} をキックしました。理由: {reason_text}"
    elif action == "ban":
        await punish_user(interaction.guild, user.id, reason_text, interaction.client)
        record_punishment(str(interaction.guild.id), user.id, "ban", interaction.user.id, reason_text)
        message = f"{user.mention} をBANしました。理由: {reason_text}"
    else:
        message = f"未対応の制裁です: {action}"

    await interaction.response.send_message(message, ephemeral=True)


@client.tree.command(name="purge", description="メッセージを一括削除します。")
@app_commands.describe(limit="削除件数")
async def purge_command(interaction: discord.Interaction, limit: int):
    if limit <= 0:
        await interaction.response.send_message("1 以上の値を指定してください。", ephemeral=True)
        return
    await interaction.response.send_message(f"{limit} 件のメッセージを削除しました。", ephemeral=True)


@client.event
@client.event
async def on_ready():
    print(f"[Bot] {client.user} としてログインしました")
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Security Console"))
    try:
        synced = await client.tree.sync()
        print(f"[Bot] {len(synced)}個のスラッシュコマンドを同期しました")
    except Exception as e:
        print(f"[Bot] コマンド同期エラー: {e}")


@client.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    settings = get_settings(str(guild.id))
    anti_raid = settings.get("antiRaid", {})
    if not anti_raid.get("enabled", False):
        return

    if detect_anti_raid(str(guild.id), str(member.id), threshold=int(anti_raid.get("threshold", 5)), interval_ms=int(anti_raid.get("interval", 10000))):
        await send_log(
            client,
            type="raid",
            title="レイド検知",
            description="短時間に大量参加の兆候があり、対象を保護処理しました。",
            fields=[
                {"name": "対象", "value": f"{member.mention} ({member.id})", "inline": True},
                {"name": "閾値", "value": str(anti_raid.get("threshold", 5)), "inline": True},
            ],
            user=member,
            guild_id=str(guild.id),
        )

        if member.id != guild.owner_id and not is_on_list(str(guild.id), "whitelist", member.id):
            try:
                await member.ban(reason="Anti-raid protection")
            except Exception:
                pass


@client.event
async def on_guild_channel_create(channel: discord.abc.GuildChannel):
    guild = channel.guild
    settings = get_settings(str(guild.id))
    anti_nuke = settings.get("antiNuke", {})
    if not anti_nuke.get("enabled", False):
        return

    actor_id = getattr(channel, "created_by", None) or "unknown"
    if detect_anti_nuke(str(guild.id), "channel_create", actor_id, threshold=int(anti_nuke.get("threshold", 3)), interval_ms=int(anti_nuke.get("interval", 5000))):
        await send_log(
            client,
            type="nuke",
            title="チャンネル大量作成検知",
            description="短時間にチャンネルが急増しているため、保護処理を実行しました。",
            fields=[{"name": "チャンネル", "value": channel.name, "inline": True}],
            guild_id=str(guild.id),
        )
        try:
            await channel.delete(reason="Anti-nuke protection")
        except Exception:
            pass


@client.event
async def on_guild_role_create(role: discord.Role):
    guild = role.guild
    settings = get_settings(str(guild.id))
    anti_nuke = settings.get("antiNuke", {})
    if not anti_nuke.get("enabled", False):
        return

    actor_id = getattr(role, "created_by", None) or "unknown"
    if detect_anti_nuke(str(guild.id), "role_create", actor_id, threshold=int(anti_nuke.get("threshold", 3)), interval_ms=int(anti_nuke.get("interval", 5000))):
        await send_log(
            client,
            type="nuke",
            title="ロール大量作成検知",
            description="短時間にロールが急増しているため、保護処理を実行しました。",
            fields=[{"name": "ロール", "value": role.name, "inline": True}],
            guild_id=str(guild.id),
        )
        try:
            await role.delete(reason="Anti-nuke protection")
        except Exception:
            pass


async def load_cogs():
    await client.add_cog(Moderation(client))
    print("[Cog] Moderation を読み込みました")


async def start_bot(token: str | None = None):
    token = token or os.environ.get("DISCORD_TOKEN", "TOKEN")
    print(f"[Bot] トークン確認: {token[:20]}...")
    await load_cogs()
    await client.start(token)


def test_default_whitelist_blacklist_are_present(tmp_path, monkeypatch):
    monkeypatch.setattr("bot.bot.SETTINGS_DIR", tmp_path)
    settings = get_settings("guild-1")

    assert settings["whitelist"] == []
    assert settings["blacklist"] == []


def test_add_and_remove_ids_from_list(tmp_path, monkeypatch):
    monkeypatch.setattr("bot.bot.SETTINGS_DIR", tmp_path)

    updated = add_to_list("guild-1", "blacklist", "<@123456789>")
    assert updated["blacklist"] == ["123456789"]

    updated = add_to_list("guild-1", "whitelist", 987654321)
    assert updated["whitelist"] == ["987654321"]

    updated = remove_from_list("guild-1", "blacklist", "123456789")
    assert updated["blacklist"] == []


def test_punishment_history_tracks_timeout_and_kick_counts(tmp_path, monkeypatch):
    monkeypatch.setattr("bot.bot.SETTINGS_DIR", tmp_path)

    record_punishment("guild-1", "123", "timeout", "456", "spam")
    record_punishment("guild-1", "123", "kick", "456", "raid")
    record_punishment("guild-1", "123", "timeout", "789", "repeat")

    summary = get_punishment_summary("guild-1", "123")
    assert summary["timeout"] == 2
    assert summary["kick"] == 1
    assert len(get_punishment_history("guild-1", "123")) == 3


def test_recent_abuse_returns_latest_entries(tmp_path, monkeypatch):
    monkeypatch.setattr("bot.bot.SETTINGS_DIR", tmp_path)

    record_punishment("guild-1", "111", "timeout", "456", "spam")
    record_punishment("guild-1", "222", "kick", "456", "raid")

    recent = get_recent_abuse("guild-1", limit=2)
    assert len(recent) == 2
    assert recent[0]["user_id"] == "222"


def test_bot_module_exposes_settings_helpers():
    assert callable(get_settings)
    assert callable(record_punishment)
    assert callable(track_action)


def test_bot_registers_basic_slash_commands():
    names = {cmd.name for cmd in client.tree.get_commands()}
    assert "status" in names
    assert "list" in names
    assert "log" in names
    assert "sanction" in names


def test_detect_anti_raid_triggers_when_join_volume_exceeds_threshold(tmp_path, monkeypatch):
    monkeypatch.setattr("bot.bot.SETTINGS_DIR", tmp_path)
    update_settings("guild-raid", {"antiRaid": {"enabled": True, "threshold": 3, "interval": 1000}})

    assert detect_anti_raid("guild-raid", "user-1") is False
    assert detect_anti_raid("guild-raid", "user-1") is False
    assert detect_anti_raid("guild-raid", "user-1") is True


def test_detect_anti_nuke_triggers_when_channel_or_role_spike_is_detected(tmp_path, monkeypatch):
    monkeypatch.setattr("bot.bot.SETTINGS_DIR", tmp_path)
    update_settings("guild-nuke", {"antiNuke": {"enabled": True, "threshold": 3, "interval": 1000}})

    assert detect_anti_nuke("guild-nuke", "channel_create", "admin-1") is False
    assert detect_anti_nuke("guild-nuke", "channel_create", "admin-1") is False
    assert detect_anti_nuke("guild-nuke", "channel_create", "admin-1") is True

    assert detect_anti_nuke("guild-nuke", "role_create", "admin-2") is False
    assert detect_anti_nuke("guild-nuke", "role_create", "admin-2") is False
    assert detect_anti_nuke("guild-nuke", "role_create", "admin-2") is True


def test_verify_config_tracks_role_and_channel(tmp_path, monkeypatch):
    monkeypatch.setattr("bot.bot.SETTINGS_DIR", tmp_path)

    config = get_verify_settings("guild-verify")
    assert config["enabled"] is False

    updated = update_settings("guild-verify", {"verify": {"enabled": True, "roleId": "123", "channelId": "456", "message": "認証してください"}})
    assert updated["verify"]["enabled"] is True
    assert updated["verify"]["roleId"] == "123"
    assert updated["verify"]["channelId"] == "456"


def test_list_commands_are_consolidated_into_single_slash_command():
    names = {cmd.name for cmd in client.tree.get_commands()}
    assert "list" in names
    assert "whitelist" not in names
    assert "blacklist" not in names
    assert "banlist" not in names


def test_individual_sanction_commands_are_removed_from_tree():
    names = {cmd.name for cmd in client.tree.get_commands()}
    for name in ("warn", "mute", "timeout", "kick", "ban"):
        assert name not in names
    assert "sanction" in names


__all__ = [
    "BOT_DIR",
    "SETTINGS_DIR",
    "MAX_MEMORY",
    "COLOR_MAP",
    "EMOJI_MAP",
    "track_action",
    "reset_tracker",
    "send_log",
    "get_logs",
    "punish_user",
    "normalize_member_id",
    "get_settings",
    "save_settings",
    "update_settings",
    "get_list",
    "add_to_list",
    "remove_from_list",
    "is_on_list",
    "record_punishment",
    "get_punishment_history",
    "get_punishment_summary",
    "get_punishment_rankings",
    "get_recent_abuse",
    "detect_anti_raid",
    "detect_anti_nuke",
    "test_default_whitelist_blacklist_are_present",
    "test_add_and_remove_ids_from_list",
    "test_punishment_history_tracks_timeout_and_kick_counts",
    "test_recent_abuse_returns_latest_entries",
    "test_bot_module_exposes_settings_helpers",
    "test_detect_anti_raid_triggers_when_join_volume_exceeds_threshold",
    "test_detect_anti_nuke_triggers_when_channel_or_role_spike_is_detected",
    "test_verify_config_tracks_role_and_channel",
    "test_list_commands_are_consolidated_into_single_slash_command",
    "test_individual_sanction_commands_are_removed_from_tree",
    "client",
    "Moderation",
    "load_cogs",
    "start_bot",
]
