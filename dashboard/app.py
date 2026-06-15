import os
import json
import requests
from datetime import datetime
from functools import wraps
from flask import Flask, redirect, request, session, url_for, render_template, jsonify, flash
from bot.utils.settings_store import get_settings, update_settings
from bot.utils.logger import get_logs, get_file_logs

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("SESSION_SECRET", "changeme")

CLIENT_ID     = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
CALLBACK_URL  = os.getenv("CALLBACK_URL", "http://localhost:3000/auth/callback")
DISCORD_API   = "https://discord.com/api/v10"
BOT_INVITE    = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&permissions=8&scope=bot%20applications.commands"


# ===== ヘルパー =====

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("auth_login"))
        return f(*args, **kwargs)
    return decorated


def guild_admin_required(f):
    @wraps(f)
    def decorated(*args, guild_id, **kwargs):
        if "user" not in session:
            return redirect(url_for("auth_login"))
        guilds = session.get("guilds", [])
        guild  = next((g for g in guilds if g["id"] == guild_id), None)
        if not guild:
            return render_template("error.html", code=403, message="このサーバーへのアクセス権がありません"), 403
        perms = int(guild["permissions"])
        if not ((perms & 0x8) or (perms & 0x20)):
            return render_template("error.html", code=403, message="このサーバーの管理権限がありません"), 403
        return f(*args, guild_id=guild_id, guild=guild, **kwargs)
    return decorated


def _discord_get(endpoint: str, token: str):
    r = requests.get(f"{DISCORD_API}{endpoint}", headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()


def _guild_icon(g: dict) -> str:
    if g.get("icon"):
        return f"https://cdn.discordapp.com/icons/{g['id']}/{g['icon']}.png"
    return f"https://ui-avatars.com/api/?name={requests.utils.quote(g['name'])}&background=5865F2&color=fff"


# ===== テンプレートグローバル =====

@app.context_processor
def inject_globals():
    return {
        "user":       session.get("user"),
        "bot_invite": BOT_INVITE,
        "now":        datetime.utcnow(),
    }


# ===== ルート =====

@app.route("/")
def index():
    return render_template("index.html", invite_url=BOT_INVITE)


# ===== OAuth2 =====

@app.route("/auth/login")
def auth_login():
    scope = "identify guilds"
    return redirect(
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={CLIENT_ID}&redirect_uri={requests.utils.quote(CALLBACK_URL)}"
        f"&response_type=code&scope={requests.utils.quote(scope)}"
    )


@app.route("/auth/callback")
def auth_callback():
    code = request.args.get("code")
    if not code:
        return redirect("/?error=auth_failed")

    # トークン取得
    r = requests.post(f"{DISCORD_API}/oauth2/token", data={
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type":    "authorization_code",
        "code":          code,
        "redirect_uri":  CALLBACK_URL,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})

    if not r.ok:
        return redirect("/?error=auth_failed")

    tokens = r.json()
    access_token = tokens["access_token"]

    user   = _discord_get("/users/@me", access_token)
    guilds = _discord_get("/users/@me/guilds", access_token)

    session["user"]   = user
    session["guilds"] = guilds
    return redirect("/dashboard")


@app.route("/auth/logout")
def auth_logout():
    session.clear()
    return redirect("/")


# ===== ダッシュボード =====

@app.route("/dashboard")
@login_required
def dashboard_guilds():
    guilds = session.get("guilds", [])
    admin_guilds = []
    for g in guilds:
        perms = int(g["permissions"])
        if (perms & 0x8) or (perms & 0x20):
            g["icon_url"] = _guild_icon(g)
            admin_guilds.append(g)
    return render_template("dashboard/guilds.html", guilds=admin_guilds)


@app.route("/dashboard/<guild_id>")
@login_required
@guild_admin_required
def dashboard_overview(guild_id, guild):
    settings = get_settings(guild_id)
    logs     = get_logs(guild_id, 10)
    guild["icon_url"] = _guild_icon(guild)
    return render_template("dashboard/overview.html", guild=guild, settings=settings, logs=logs, guild_id=guild_id)


@app.route("/dashboard/<guild_id>/antinuke", methods=["GET", "POST"])
@login_required
@guild_admin_required
def dashboard_antinuke(guild_id, guild):
    guild["icon_url"] = _guild_icon(guild)
    if request.method == "POST":
        update_settings(guild_id, {"antiNuke": {
            "enabled":   "enabled" in request.form,
            "threshold": max(1,  min(20,    int(request.form.get("threshold", 3)))),
            "interval":  max(1000, min(60000, int(request.form.get("interval",  5000)))),
        }})
        return redirect(url_for("dashboard_antinuke", guild_id=guild_id, saved=1))
    settings = get_settings(guild_id)
    return render_template("dashboard/antinuke.html", guild=guild, settings=settings, guild_id=guild_id, saved=request.args.get("saved"))


@app.route("/dashboard/<guild_id>/antiraid", methods=["GET", "POST"])
@login_required
@guild_admin_required
def dashboard_antiraid(guild_id, guild):
    guild["icon_url"] = _guild_icon(guild)
    if request.method == "POST":
        update_settings(guild_id, {"antiRaid": {
            "enabled":   "enabled" in request.form,
            "threshold": max(2,    min(50,    int(request.form.get("threshold", 5)))),
            "interval":  max(1000, min(60000, int(request.form.get("interval",  10000)))),
        }})
        return redirect(url_for("dashboard_antiraid", guild_id=guild_id, saved=1))
    settings = get_settings(guild_id)
    return render_template("dashboard/antiraid.html", guild=guild, settings=settings, guild_id=guild_id, saved=request.args.get("saved"))


@app.route("/dashboard/<guild_id>/verify", methods=["GET", "POST"])
@login_required
@guild_admin_required
def dashboard_verify(guild_id, guild):
    guild["icon_url"] = _guild_icon(guild)
    if request.method == "POST":
        update_settings(guild_id, {"verify": {
            "enabled":   "enabled" in request.form,
            "roleId":    request.form.get("roleId",    "").strip(),
            "channelId": request.form.get("channelId", "").strip(),
            "message":   request.form.get("message",   "ボタンを押して認証してください。")[:500],
        }})
        return redirect(url_for("dashboard_verify", guild_id=guild_id, saved=1))
    settings = get_settings(guild_id)
    return render_template("dashboard/verify.html", guild=guild, settings=settings, guild_id=guild_id, saved=request.args.get("saved"))


@app.route("/dashboard/<guild_id>/logs", methods=["GET", "POST"])
@login_required
@guild_admin_required
def dashboard_logs(guild_id, guild):
    guild["icon_url"] = _guild_icon(guild)
    if request.method == "POST":
        events = request.form.getlist("events")
        update_settings(guild_id, {"logs": {
            "channelId": request.form.get("channelId", "").strip(),
            "events":    events,
        }})
        return redirect(url_for("dashboard_logs", guild_id=guild_id, saved=1))
    settings = get_settings(guild_id)
    date     = request.args.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
    logs     = get_file_logs(guild_id, date)
    return render_template("dashboard/logs.html", guild=guild, settings=settings, logs=logs, date=date, guild_id=guild_id, saved=request.args.get("saved"))


# ===== API =====

@app.route("/api/logs/<guild_id>")
@login_required
def api_logs(guild_id):
    limit = min(100, int(request.args.get("limit", 50)))
    return jsonify({"ok": True, "logs": get_logs(guild_id, limit)})


@app.route("/api/invite")
def api_invite():
    return jsonify({"ok": True, "url": BOT_INVITE})


# ===== エラー =====

@app.errorhandler(404)
def e404(e):
    return render_template("error.html", code=404, message="ページが見つかりません"), 404

@app.errorhandler(500)
def e500(e):
    return render_template("error.html", code=500, message="サーバーエラーが発生しました"), 500
