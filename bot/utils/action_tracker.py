import asyncio
from collections import defaultdict

# {guild_id: {user_id: {"count": int, "task": asyncio.Task}}}
_tracker: dict[str, dict[str, dict]] = defaultdict(dict)


def track_action(guild_id: str, user_id: str, threshold: int, interval_ms: int) -> bool:
    """
    アクションを記録してしきい値を超えたか返す。
    interval_ms ミリ秒後にカウントをリセットする。
    """
    guild_map = _tracker[guild_id]

    if user_id not in guild_map:
        guild_map[user_id] = {"count": 0, "task": None}

    entry = guild_map[user_id]
    entry["count"] += 1

    # 既存タイマーをキャンセル
    if entry["task"] and not entry["task"].done():
        entry["task"].cancel()

    async def _reset():
        await asyncio.sleep(interval_ms / 1000)
        guild_map.pop(user_id, None)

    try:
        loop = asyncio.get_event_loop()
        entry["task"] = loop.create_task(_reset())
    except RuntimeError:
        pass

    return entry["count"] >= threshold


def reset_tracker(guild_id: str, user_id: str):
    _tracker[guild_id].pop(user_id, None)
