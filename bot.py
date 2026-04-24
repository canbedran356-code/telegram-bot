import os
import re
import time
import logging
import yt_dlp
from collections import defaultdict
from datetime import datetime, timedelta

from telegram import Update, ChatPermissions
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

# ================= CONFIG =================

TOKEN = os.getenv("TOKEN")
LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", "0"))

MAX_WARN = 3
MUTE_TIME = 120
FLOOD_LIMIT = 5
FLOOD_TIME = 10

logging.basicConfig(level=logging.INFO)

warns = defaultdict(lambda: defaultdict(int))
flood = defaultdict(lambda: defaultdict(list))

# ================= HELPERS =================

async def is_admin(update, user_id):
    member = await update.effective_chat.get_member(user_id)
    return member.status in ("administrator", "creator")


def has_link(text):
    return bool(re.search(r"(https?://|t\.me|www\.)", text.lower()))


def is_flood(chat_id, user_id):
    now = time.time()
    flood[chat_id][user_id] = [
        t for t in flood[chat_id][user_id] if now - t < FLOOD_TIME
    ]
    flood[chat_id][user_id].append(now)
    return len(flood[chat_id][user_id]) > FLOOD_LIMIT


async def log_action(context, update, action, reason=""):
    if not LOG_CHAT_ID:
        return

    user = update.effective_user
    chat = update.effective_chat

    msg = f"""
<b>{action}</b>
👤 {user.first_name}
🆔 <code>{user.id}</code>
💬 {chat.title}
📝 {reason}
"""
    try:
        await context.bot.send_message(LOG_CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except:
        pass


# ================= USER BUL =================

async def resolve_user(update, context):
    if update.message.reply_to_message:
        u = update.message.reply_to_message.from_user
        return u.id, u.first_name

    if context.args:
        arg = context.args[0]

        if arg.isdigit():
            try:
                m = await update.effective_chat.get_member(int(arg))
                return m.user.id, m.user.first_name
            except:
                return None, None

        if arg.startswith("@"):
            username = arg.replace("@", "").lower()
            admins = await update.effective_chat.get_administrators()
            for m in admins:
                if m.user.username and m.user.username.lower() == username:
                    return m.user.id, m.user.first_name

    return None, None


# ================= CORE =================

async def mute_user(update, context, user_id, reason):
    if await is_admin(update, user_id):
        await update.message.reply_text("⚠️ Admin sessize alınamaz.")
        return

    until = datetime.now() + timedelta(seconds=MUTE_TIME)

    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        user_id,
        ChatPermissions(can_send_messages=False),
        until_date=until
    )

    await update.message.reply_text("🔇 Susturuldu")
    await log_action(context, update, "MUTE", reason)


async def warn_user(update, context, user_id, reason):
    if await is_admin(update, user_id):
        await update.message.reply_text("⚠️ Admin uyarı alamaz.")
        return

    chat = update.effective_chat.id
    warns[chat][user_id] += 1
    count = warns[chat][user_id]

    await log_action(context, update, "WARN", reason)

    if count >= MAX_WARN:
        await mute_user(update, context, user_id, "3 warn")
        warns[chat][user_id] = 0
        await update.message.reply_text("🔇 3 warn → mute")
    else:
        await update.message.reply_text(f"⚠️ Warn: {count}/{MAX_WARN}")


# ================= COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Guard + Müzik Bot aktif")


# WARN
async def warn_cmd(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ Bu işlem size göre değil.")
        return

    uid, _ = await resolve_user(update, context)
    if uid:
        await warn_user(update, context, uid, "admin")


async def unwarn_cmd(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ Bu işlem size göre değil.")
        return

    uid, _ = await resolve_user(update, context)
    if uid:
        chat = update.effective_chat.id
        if warns[chat][uid] > 0:
            warns[chat][uid] -= 1
        await update.message.reply_text("✅ Unwarn")


# MUTE
async def mute_cmd(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ Bu işlem size göre değil.")
        return

    uid, _ = await resolve_user(update, context)
    if uid:
        await mute_user(update, context, uid, "admin")


async def unmute_cmd(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ Bu işlem size göre değil.")
        return

    uid, _ = await resolve_user(update, context)
    if uid:
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            uid,
            ChatPermissions(can_send_messages=True)
        )
        await update.message.reply_text("🔊 Unmute")


# BAN
async def ban_cmd(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ Bu işlem size göre değil.")
        return

    uid, _ = await resolve_user(update, context)
    if uid:
        if await is_admin(update, uid):
            await update.message.reply_text("⚠️ Admin banlanamaz.")
            return

        await context.bot.ban_chat_member(update.effective_chat.id, uid)
        await update.message.reply_text("🚫 Ban")


async def unban_cmd(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ Bu işlem size göre değil.")
        return

    if context.args and context.args[0].isdigit():
        uid = int(context.args[0])
        await context.bot.unban_chat_member(update.effective_chat.id, uid)
        await update.message.reply_text("✅ Unban")


# ================= 🎵 MÜZİK =================

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("🎧 Kullanım: /play şarkı adı")
        return

    query = " ".join(context.args)
    await update.message.reply_text("🔍 Aranıyor...")

    ydl_opts = {
        "format": "bestaudio",
        "noplaylist": True,
        "quiet": True,
        "outtmpl": "song.%(ext)s",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=True)
            video = info["entries"][0]
            file_path = ydl.prepare_filename(video)

        await update.message.reply_audio(
            audio=open(file_path, "rb"),
            title=video["title"]
        )

        os.remove(file_path)

    except:
        await update.message.reply_text("❌ Müzik indirilemedi")


# ================= AUTO =================

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    chat = update.effective_chat.id
    text = update.message.text

    if await is_admin(update, user.id):
        return

    if is_flood(chat, user.id):
        await mute_user(update, context, user.id, "flood")
        return

    if has_link(text):
        await update.message.delete()
        await warn_user(update, context, user.id, "link")


# ================= MAIN =================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(CommandHandler("warn", warn_cmd))
    app.add_handler(CommandHandler("unwarn", unwarn_cmd))

    app.add_handler(CommandHandler("mute", mute_cmd))
    app.add_handler(CommandHandler("unmute", unmute_cmd))

    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))

    app.add_handler(CommandHandler("play", play))

    app.add_handler(MessageHandler(filters.TEXT, message_handler))

    print("Bot aktif 🚀")
    app.run_polling()


if __name__ == "__main__":
    main()
