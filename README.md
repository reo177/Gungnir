# 🛡️ Discord SecurityBot

アンチヌーク・アンチレイド・ロール認証・WebダッシュボードつきのDiscord Botです。

---

## 機能一覧

| 機能 | 説明 |
|------|------|
| 💣 アンチヌーク | チャンネル削除、ロール削除、大量BAN/KICKなどを検知して実行者をBAN |
| 🚨 アンチレイド | 短時間での大量参加を検知してレイド参加者をキック |
| ✅ ロール認証 | ボタンパネルまたはコマンドでロールを付与 |
| 📋 ログ | 全アクションをDiscordチャンネルとダッシュボードに記録 |
| 🌐 Webダッシュボード | DiscordでログインしてブラウザからBot設定・ログ確認 |

---

## セットアップ

### 1. 依存パッケージのインストール

```bash
npm install
```

### 2. 環境変数の設定

`.env.example` を `.env` にコピーして値を入力

```bash
copy .env.example .env
```

| 変数名 | 説明 |
|--------|------|
| `DISCORD_TOKEN` | Discord Developer Portal のボットトークン |
| `CLIENT_ID` | ボットのクライアントID |
| `CLIENT_SECRET` | OAuth2のクライアントシークレット |
| `CALLBACK_URL` | OAuth2コールバックURL (本番は `https://yourdomain.com/auth/callback`) |
| `SESSION_SECRET` | セッション暗号化キー (長いランダム文字列) |
| `DASHBOARD_PORT` | ダッシュボードのポート番号 (デフォルト: 3000) |
| `LOG_CHANNEL_ID` | ログを送信するチャンネルID |
| `VERIFY_ROLE_ID` | 認証後に付与するロールID |
| `OWNER_ID` | アンチヌーク除外対象のオーナーユーザーID |
| `RAID_THRESHOLD` | レイド検知しきい値 (デフォルト: 5人) |
| `RAID_INTERVAL` | レイド検知時間ウィンドウ (ミリ秒, デフォルト: 10000) |
| `NUKE_THRESHOLD` | ヌーク検知しきい値 (デフォルト: 3回) |
| `NUKE_INTERVAL` | ヌーク検知時間ウィンドウ (ミリ秒, デフォルト: 5000) |

### 3. Discord Developer Portal の設定

1. https://discord.com/developers/applications を開く
2. アプリ → **OAuth2** → **Redirects** に `http://localhost:3000/auth/callback` を追加
3. Bot → **Privileged Gateway Intents** で以下を有効化:
   - ✅ Server Members Intent
   - ✅ Message Content Intent

### 4. スラッシュコマンドの登録

```bash
node src/deploy-commands.js
```

### 5. 起動

**Botのみ:**
```bash
npm start
```

**ダッシュボードのみ:**
```bash
npm run dashboard
```

**両方同時 (推奨):**
`.env` に `START_DASHBOARD=true` を追加してから:
```bash
npm start
```

---

## URL一覧

| URL | 説明 |
|-----|------|
| `http://localhost:3000` | トップページ (ランディング) |
| `http://localhost:3000/auth/login` | Discordログイン |
| `http://localhost:3000/dashboard` | サーバー選択 |
| `http://localhost:3000/dashboard/:guildId` | サーバー概要 |
| `http://localhost:3000/dashboard/:guildId/antinuke` | アンチヌーク設定 |
| `http://localhost:3000/dashboard/:guildId/antiraid` | アンチレイド設定 |
| `http://localhost:3000/dashboard/:guildId/verify` | ロール認証設定 |
| `http://localhost:3000/dashboard/:guildId/logs` | ログビューア |
| `https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=8&scope=bot%20applications.commands` | ボット招待URL |

---

## スラッシュコマンド

| コマンド | 権限 | 説明 |
|----------|------|------|
| `/verify-setup` | 管理者 | 認証パネルを設置する |
| `/verify-role @user` | ロール管理 | ユーザーに手動で認証ロールを付与 |
| `/lockdown true/false` | 管理者 | サーバー全体のロック切り替え |
| `/unban <userID>` | BAN管理 | BAN済みユーザーを解除 |
| `/status` | 管理者 | ボットの現在設定を確認 |

---

## プロジェクト構造

```
src/
├── index.js
├── deploy-commands.js
├── commands/
├── events/
├── utils/
│   ├── logger.js         # ログ送信 + ファイル/メモリ保存
│   ├── punish.js
│   ├── actionTracker.js
│   └── settingsStore.js  # サーバー設定の読み書き (settings/<guildId>.json)
└── dashboard/
    ├── server.js          # Expressサーバー
    ├── auth/
    │   ├── passport.js    # Discord OAuth2
    │   └── middleware.js  # 認証ミドルウェア
    ├── routes/
    │   ├── index.js
    │   ├── auth.js
    │   ├── dashboard.js
    │   └── api.js
    ├── views/
    │   ├── index.ejs
    │   ├── error.ejs
    │   ├── partials/
    │   └── dashboard/
    └── public/
        ├── css/style.css
        └── js/main.js

settings/   ← サーバー設定JSON (自動生成)
logs/       ← ログJSONL (自動生成)
```
