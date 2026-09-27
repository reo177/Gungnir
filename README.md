# 🛡️ Discord Security Bot

Discord サーバーの保護・監査・制裁を Discord 上で完結させる Bot です。

- Web ダッシュボードなし
- DB なし
- スラッシュコマンド中心
- ローカル JSON で設定と履歴を保存

---

## 主要機能

- アンチヌーク検知
- アンチレイド対策
- `/list` による whitelist / blacklist / banlist 管理
- `/sanction` による一括制裁
- 監査ログと異常履歴
- 認証ロール設定

---

## コマンド

| コマンド | 用途 |
|---|---|
| `/help` | ヘルプ表示 |
| `/status` | 保護状態確認 |
| `/list` | リスト統合管理 |
| `/allban` | ブラックリストをまとめて BAN |
| `/log` | 監査ログ表示 |
| `/audit` | 監査ログ表示 |
| `/join-log` | 入室ログ確認 |
| `/recent-abuse` | 異常行為の再確認 |
| `/security` | セキュリティ状態表示 |
| `/user-check` | 制裁履歴確認 |
| `/lockdown` | 緊急保護モード |
| `/verify-setup` | 認証設定 |
| `/verify-role` | 認証ロール付与 |
| `/sanction` | 制裁実行（warn / mute / timeout / kick / ban） |
| `/purge` | メッセージ一括削除 |

### `/list` の例

```text
/list kind:whitelist action:list
/list kind:blacklist action:add member:@user
/list kind:banlist action:remove member:@user
```

---

## 依存関係

```txt
discord.py>=2.3.2
pytest>=8.0
```

---

## インストール

```bash
pip install -r requirements.txt
```

---

## 環境変数

```text
DISCORD_TOKEN
LOG_CHANNEL_ID
VERIFY_ROLE_ID
VERIFY_CHANNEL_ID
OWNER_ID
RAID_THRESHOLD
RAID_INTERVAL
NUKE_THRESHOLD
NUKE_INTERVAL
```

---

## 起動

```bash
python index.py
```

- [index.py](index.py) が起動入口
- [bot/bot.py](bot/bot.py) が実体
- Discord コマンドツリーを同期して `/help` を利用可能にする

---

## 補足

- スラッシュコマンドのみを利用する構成です
- `whitelist` / `blacklist` / `banlist` は `/list` に統合されています
- `applications.commands` の権限が必要です
- ローカル JSON で設定と履歴を保管します
