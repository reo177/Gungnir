# 🛡️ Discord Anti Nuke & Anti Raid Bot

Discord サーバー保護用のBotです。アンチヌーク、アンチレイド、認証、ログ、管理コマンドを統合しています。

---

## 主な機能

- アンチヌーク検知
  - チャンネル作成/削除
  - ロール作成/削除
  - BAN / KICK の異常検知
  - Webhook 作成検知
- アンチレイド対策
  - 短時間に大量参加したユーザーを検知
  - 作成から短期間の新規アカウントを自動保護
  - メッセージスパム検知
- 認証機能
  - ボタン認証パネル
  - 管理者による手動認証ロール付与
- 運用コマンド
  - warn / mute / timeout / kick / ban / banlist / audit / join-log
- ログ機能
  - VC接続 / 退出 / 移動
  - メッセージ編集 / 削除
  - サーバー情報変更
  - 管理者操作ログ
- Webダッシュボード
  - OAuth2ログイン
  - サーバー一覧
  - 設定画面
  - ログ確認

---

## 必要環境

- Python 3.10 以上
- Discord Bot Token
- Discord Application の Client ID / Secret

---

## 依存関係のインストール

```bash
pip install -r requirements.txt
```

---

## 環境変数

`index.py` 内で `os.environ.setdefault(...)` している値を必要に応じて変更してください。

| 変数名 | 説明 |
|--------|------|
| `DISCORD_TOKEN` | Botのトークン |
| `CLIENT_ID` | DiscordアプリケーションのClient ID |
| `CLIENT_SECRET` | DiscordアプリケーションのClient Secret |
| `SESSION_SECRET` | Flaskセッション用の秘密鍵 |
| `CALLBACK_URL` | OAuth2のコールバックURL |
| `DASHBOARD_PORT` | ダッシュボード起動ポート |
| `LOG_CHANNEL_ID` | ログ送信先チャンネルID |
| `VERIFY_ROLE_ID` | 認証完了時に付与するロールID |
| `VERIFY_CHANNEL_ID` | 認証パネルを設置するチャンネルID |
| `OWNER_ID` | アンチヌーク除外対象のオーナーID |
| `RAID_THRESHOLD` | レイド検知人数 |
| `RAID_INTERVAL` | レイド検知時間（ms） |
| `NUKE_THRESHOLD` | ヌーク検知回数 |
| `NUKE_INTERVAL` | ヌーク検知時間（ms） |
| `START_DASHBOARD` | ダッシュボードを同時起動するかどうか |

---

## 起動方法

```bash
python index.py
```

Bot起動時に自動で cogs を読み込み、ダッシュボードも起動します。  
`START_DASHBOARD` を `true` にしている場合のみ、Flaskダッシュボードが起動します。

---

## ダッシュボード URL

デフォルトでは以下のURLが使われます。

- `http://localhost:3001`
- `http://localhost:3001/auth/login`
- `http://localhost:3001/dashboard`

---

## 代表的なスラッシュコマンド

| コマンド | 権限 | 説明 |
|----------|------|------|
| `/creator` | すべて | 作成者情報と招待URLをDM送信 |
| `/warn` | モデレーション | 警告＋理由をDM送信 |
| `/mute` | モデレーション | ミュート＋理由をDM送信 |
| `/timeout` | モデレーション | タイムアウト＋理由をDM送信 |
| `/kick` | キック権限 | キック＋理由をDM送信 |
| `/ban` | BAN権限 | BAN＋理由をDM送信 |
| `/banlist` | BAN権限 | BAN一覧とReason表示 |
| `/audit` | 管理者 | 監査ログ表示 |
| `/join-log` | 管理者 | 入室ログ表示 |
| `/verify-setup` | 管理者 | 認証パネル設置 |
| `/verify-role` | ロール管理 | 手動認証付与 |
| `/lockdown` | 管理者 | サーバーロック切り替え |
| `/unban` | BAN管理 | BAN解除 |
| `/status` | 管理者 | 設定状況確認 |
| `/server-info` | 管理者 | サーバー情報確認 |
| `/purge` | メッセージ管理 | 一括削除 |

---

## 追加の連携URL

作成者コマンドで送信されるURLです。

- https://discord.gg/g8ZfR8ZyTx
- https://discord.gg/Rjekxj6Cea
- https://discord.gg/PHKYM6Bt8t
- https://lwa70d3.com

---

## プロジェクト構成

```text
.
├── index.py
├── README.md
├── requirements.txt
├── bot/
│   ├── __init__.py
│   ├── cogs/
│   │   ├── anti_nuke.py
│   │   ├── anti_raid.py
│   │   ├── event_log.py
│   │   ├── moderation.py
│   │   ├── verify.py
│   │   └── __init__.py
│   └── utils/
│       ├── action_tracker.py
│       ├── logger.py
│       ├── punish.py
│       ├── settings_store.py
│       └── __init__.py
├── dashboard/
│   ├── __init__.py
│   ├── app.py
│   ├── static/
│   └── templates/
└── logs/
```

---

## 補足

- `warn` / `kick` / `ban` / `timeout` 系では `Reason: ...` をDMに送信するようにしています。
- `banlist` ではBANされたユーザーと理由を表示できます。
- `audit` では監査ログを確認し、理由を見られるようにしています。
- `event_log.py` で VC接続 / 退出 / 移動ログも記録されます。

---

## 開発メモ

このBotはセキュリティ用途を前提に設計されており、管理者向けの実行コマンドと自動検知ロジックを統合しています。  
必要に応じて、追加の防御機能や管理機能も今後拡張可能です。個人個人の技量に任せます。
- https://discord.gg/g8ZfR8ZyTx
- https://discord.gg/Rjekxj6Cea
- https://lwa70d3.com
