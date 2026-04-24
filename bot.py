import os
import re
import json
import time
import logging
import asyncio
import requests

from collections import defaultdict
from datetime import datetime, timedelta

from telegram import (
    Update, ChatPermissions,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ================= CONFIG =================

TOKEN = os.getenv("TOKEN")
LOG_CHAT = os.getenv("LOG_CHAT")  # opsiyonel (chat id)

DB_FILE = "db.json"
LOCK = asyncio.Lock()

DEFAULT_SETTINGS = {
    "link_filter": True,
    "anti_flood": True,
    "music": True
}

MAX_WARN = 3
MUTE_TIME = 300
FLOOD_LIMIT = 5
FLOOD_TIME = 10

logging.basicConfig(level=logging.INFO)

# ================= DB =================

def _ensure_db():
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w") as f:
            json.dump({"warns": {}, "settings": {}}, f)

def load_db():
    _ensure_db()
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)

db = load_db()

async def db_set_warn(chat_id, user_id, val):
    async with LOCK:
        db["warns"].setdefault(str(chat_id), {})[str(user_id)] = val
        save_db(db)

def db_get_warn(chat_id, user_id):
    return db["warns"].get(str(chat_id), {}).get(str(user_id), 0)

async def db_set_setting(chat_id, key, val):
    async with LOCK:
        db["settings"].setdefault(str(chat_id), DEFAULT_SETTINGS.copy())[key] = val
        save_db(db)

def db_get_setting(chat_id, key):
    return db["settings"].get(str(chat_id), DEFAULT_SETTINGS).get(key, DEFAULT_SETTINGS[key])

# ================= HELPERS =================

async def is_admin(update: Update, user_id: int) -> bool:
    member = await update.effective_chat.get_member(user_id)
    return member.status in ("administrator", "creator")

async def get_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.reply_to_message:
        return msg.reply_to_message.from_user.id

    if context.args:
        arg = context.args[0]
        if arg.isdigit():
            return int(arg)
        if arg.startswith("@"):
            try:
                member = await update.effective_chat.get_member(arg)
                return member.user.id
            except:
                return None
    return None

def has_link(text: str) -> bool:
    if not text:
        return False
    return bool(re.search(r"(https?://|t\.me|www\.)", text.lower()))

flood = defaultdict(lambda: defaultdict(list))

def is_flood(chat_id, user_id):
    now = time.time()
    arr = flood[chat_id][user_id]
    flood[chat_id][user_id] = [t for t in arr if now - t < FLOOD_TIME]
    flood[chat_id][user_id].append(now)
    return len(flood[chat_id][user_id]) > FLOOD_LIMIT

async def log(context: ContextTypes.DEFAULT_TYPE, text: str):
    if not LOG_CHAT:
        return
    try:
        await context.bot.send_message(LOG_CHAT, text)
    except Exception:
        pass

# ================= ACTIONS =================

async def warn_user(update, context, user_id, reason="Yok"):
    if await is_admin(update, user_id):
        return "❌ Adminlere işlem yapılamaz"

    chat = update.effective_chat.id
    w = db_get_warn(chat, user_id) + 1
    await db_set_warn(chat, user_id, w)

    if w >= MAX_WARN:
        await db_set_warn(chat, user_id, 0)
        r = await mute_user(update, context, user_id, "Warn limiti")
        return f"🔇 3 warn → mute\nSebep: {reason}"

    await log(context, f"⚠️ {user_id} warnlandı ({w}/{MAX_WARN}) | {reason}")
    return f"⚠️ Warn {w}/{MAX_WARN}\nSebep: {reason}"

async def mute_user(update, context, user_id, reason="Yok"):
    if await is_admin(update, user_id):
        return "❌ Admin susturulamaz"

    until = datetime.now() + timedelta(seconds=MUTE_TIME)
    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        user_id,
        ChatPermissions(can_send_messages=False),
        until_date=until
    )
    await log(context, f"🔇 {user_id} mute | {reason}")
    return f"🔇 Mute atıldı\nSebep: {reason}"

async def unmute_user(update, context, user_id):
    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        user_id,
        ChatPermissions(can_send_messages=True)
    )
    await log(context, f"🔊 {user_id} unmute")
    return "🔊 Unmute"

async def ban_user(update, context, user_id, reason="Yok"):
    if await is_admin(update, user_id):
        return "❌ Admin banlanamaz"

    await context.bot.ban_chat_member(update.effective_chat.id, user_id)
    await log(context, f"⛔ {user_id} ban | {reason}")
    return f"⛔ Banlandı\nSebep: {reason}"

async def unban_user(update, context, user_id):
    await context.bot.unban_chat_member(update.effective_chat.id, user_id)
    await log(context, f"✅ {user_id} unban")
    return "✅ Unban"

# ================= PANELS =================

def panel_markup(uid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚠️ Warn", callback_data=f"warn:{uid}")],
        [InlineKeyboardButton("🔇 Mute", callback_data=f"mute:{uid}")],
        [InlineKeyboardButton("🔊 Unmute", callback_data=f"unmute:{uid}")],
        [InlineKeyboardButton("⛔ Ban", callback_data=f"ban:{uid}")],
        [InlineKeyboardButton("✅ Unban", callback_data=f"unban:{uid}")]
    ])

def settings_markup(chat_id):
    def t(key):
        return "✅" if db_get_setting(chat_id, key) else "❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Link Filter {t('link_filter')}", callback_data="set:link_filter")],
        [InlineKeyboardButton(f"Anti Flood {t('anti_flood')}", callback_data="set:anti_flood")],
        [InlineKeyboardButton(f"Music {t('music')}", callback_data="set:music")]
    ])

# ================= BUTTON HANDLER =================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    data = q.data

    # settings toggle
    if data.startswith("set:"):
        key = data.split(":")[1]
        chat = update.effective_chat.id
        val = not db_get_setting(chat, key)
        await db_set_setting(chat, key, val)
        return await q.edit_message_reply_markup(reply_markup=settings_markup(chat))

    # admin actions
    action, uid = data.split(":")
    uid = int(uid)

    if not await is_admin(update, q.from_user.id):
        return await q.edit_message_text("❌ Bu işlem sana göre değil")

    if action == "warn":
        r = await warn_user(update, context, uid)
    elif action == "mute":
        r = await mute_user(update, context, uid)
    elif action == "unmute":
        r = await unmute_user(update, context, uid)
    elif action == "ban":
        r = await ban_user(update, context, uid)
    elif action == "unban":
        r = await unban_user(update, context, uid)
    else:
        r = "❌ Bilinmeyen işlem"

    await q.edit_message_text(r)

# ================= MUSIC =================

music_cache = {}

def music_api_primary(q):
    return f"https://api.vevioz.com/api/button/mp3/{q}"

def music_api_fallback(q):
    # basit alternatif (aynı endpointin farklı kullanımı)
    return f"https://api.vevioz.com/api/button/mp3/{q}"

def get_music(q):
    if q in music_cache:
        return music_cache[q]
    link = music_api_primary(q)
    music_cache[q] = link
    return link

async def play(update, context):
    chat = update.effective_chat.id
    if not db_get_setting(chat, "music"):
        return await update.message.reply_text("❌ Müzik kapalı")

    if not context.args:
        return await update.message.reply_text("🎧 /play şarkı adı")

    q = " ".join(context.args)
    msg = await update.message.reply_text("🎧 aranıyor...")

    try:
        link = get_music(q)
        await update.message.reply_audio(link)
        await msg.delete()
    except Exception:
        try:
            link = music_api_fallback(q)
            await update.message.reply_audio(link)
            await msg.delete()
        except Exception as e:
            await msg.edit_text(f"❌ Müzik alınamadı: {e}")

# ================= COMMANDS =================

async def panel_cmd(update, context):
    uid = await get_target(update, context)
    if not uid:
        return await update.message.reply_text("❌ Kullanıcı seç (reply / @user / id)")
    await update.message.reply_text("👮 Panel", reply_markup=panel_markup(uid))

async def settings_cmd(update, context):
    chat = update.effective_chat.id
    await update.message.reply_text("⚙️ Ayarlar", reply_markup=settings_markup(chat))

async def warn_cmd(update, context):
    uid = await get_target(update, context)
    if not uid:
        return await update.message.reply_text("❌ Kullanıcı bulunamadı")
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Yok"
    await update.message.reply_text(await warn_user(update, context, uid, reason))

async def mute_cmd(update, context):
    uid = await get_target(update, context)
    if not uid:
        return await update.message.reply_text("❌ Kullanıcı bulunamadı")
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Yok"
    await update.message.reply_text(await mute_user(update, context, uid, reason))

async def ban_cmd(update, context):
    uid = await get_target(update, context)
    if not uid:
        return await update.message.reply_text("❌ Kullanıcı bulunamadı")
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Yok"
    await update.message.reply_text(await ban_user(update, context, uid, reason))

async def unban_cmd(update, context):
    uid = await get_target(update, context)
    if not uid:
        return await update.message.reply_text("❌ Kullanıcı bulunamadı")
    await update.message.reply_text(await unban_user(update, context, uid))

async def unmute_cmd(update, context):
    uid = await get_target(update, context)
    if not uid:
        return await update.message.reply_text("❌ Kullanıcı bulunamadı")
    await update.message.reply_text(await unmute_user(update, context, uid))

# ================= AUTO =================

async def auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user = update.effective_user
    chat = update.effective_chat.id

    if await is_admin(update, user.id):
        return

    # anti-flood
    if db_get_setting(chat, "anti_flood") and is_flood(chat, user.id):
        await mute_user(update, context, user.id, "Flood")
        return

    # link filter
    if db_get_setting(chat, "link_filter") and has_link(update.message.text):
        try:
            await update.message.delete()
        except Exception:
            pass

        await update.message.reply_text(
            "🚫 Link yasak",
            reply_markup=panel_markup(user.id)
        )

# ================= MAIN =================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("panel", panel_cmd))
    app.add_handler(CommandHandler("settings", settings_cmd))
    app.add_handler(CommandHandler("warn", warn_cmd))
    app.add_handler(CommandHandler("mute", mute_cmd))
    app.add_handler(CommandHandler("unmute", unmute_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("play", play))

    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL, auto))

    print("👑 GOD MODE BOT AKTİF")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
