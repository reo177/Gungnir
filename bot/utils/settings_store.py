import os
import json
from pathlib import Path
from copy import deepcopy

SETTINGS_DIR = Path(__file__).parent.parent.parent / "settings"
SETTINGS_DIR.mkdir(exist_ok=True)


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


def _defaults() -> dict:
    return {
        "antiNuke": {
            "enabled":   True,
            "threshold": int(os.getenv("NUKE_THRESHOLD", 3)),
            "interval":  int(os.getenv("NUKE_INTERVAL",  5000)),
        },
        "antiRaid": {
            "enabled":   True,
            "threshold": int(os.getenv("RAID_THRESHOLD", 5)),
            "interval":  int(os.getenv("RAID_INTERVAL",  10000)),
        },
        "verify": {
            "enabled":   False,
            "roleId":    os.getenv("VERIFY_ROLE_ID", ""),
            "channelId": os.getenv("VERIFY_CHANNEL_ID", ""),
            "message":   "ボタンを押して認証してください。",
        },
        "logs": {
            "channelId": os.getenv("LOG_CHANNEL_ID", ""),
            "events":    ["nuke", "raid", "verify", "join", "action"],
        },
        "whitelist": [],
        "blacklist": [],
        "punishments": {
            "history": [],
        },
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
        "timestamp": str(__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()),
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
    summary = {
        "timeout": 0,
        "kick": 0,
        "ban": 0,
        "mute": 0,
        "warn": 0,
    }
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
