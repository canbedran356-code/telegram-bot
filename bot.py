import os
import re
import time
import logging
import yt_dlp
from collections import defaultdict
from datetime import datetime, timedelta

from telegram import (
    Update,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

# ================= CONFIG =================

TOKEN = os.getenv("TOKEN")
LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", "0"))

WELCOME_PHOTO = "https://hizliresim.com/d0rzkvv"

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

# ================= WELCOME / LEAVE =================

async def welcome_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    # Yeni gelenler
    if message.new_chat_members:
        for user in message.new_chat_members:
            name = user.first_name
            user_id = user.id

            text = f"""
🔥 Berxwedan Grubuna Hoşgeldin Heval {name}

📜 Kurallar:
🚫 Link yasak
🚫 Flood yasak
⚠️ 3 warn = mute

Keyifli sohbetler ✌️
"""

            keyboard = [
                [InlineKeyboardButton("📜 Kurallar", url="https://t.me/your_rules_link")],
                [InlineKeyboardButton("👤 Profil", url=f"tg://user?id={user_id}")]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)

            await message.reply_photo(
                photo=WELCOME_PHOTO,
                caption=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )

    # Çıkanlar
    if message.left_chat_member:
        user = message.left_chat_member
        name = user.first_name

        await message.reply_text(f"😢 Güle güle git Heval {name}")

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
    await update.message.reply_text("🤖 Bot aktif")

# ================= MÜZİK =================

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

    # welcome handler
    app.add_handler(MessageHandler(filters.StatusUpdate.ALL, welcome_leave))

    app.add_handler(CommandHandler("play", play))

    app.add_handler(MessageHandler(filters.TEXT, message_handler))

    print("Bot aktif 🚀")
    app.run_polling()

if __name__ == "__main__":
    main()
