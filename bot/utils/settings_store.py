import os
import json
from pathlib import Path
from copy import deepcopy

SETTINGS_DIR = Path(__file__).parent.parent.parent / "settings"
SETTINGS_DIR.mkdir(exist_ok=True)


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
