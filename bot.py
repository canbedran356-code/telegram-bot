import os
import re
import time
import logging
import yt_dlp

from collections import defaultdict
from datetime import datetime, timedelta

from telegram import (
    Update, ChatPermissions,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, ContextTypes,
    CallbackQueryHandler, filters
)

# ================= CONFIG =================

TOKEN = os.getenv("TOKEN")

MAX_WARN = 3
MUTE_TIME = 300
FLOOD_LIMIT = 5
FLOOD_TIME = 10

logging.basicConfig(level=logging.INFO)

warns = defaultdict(lambda: defaultdict(int))
flood = defaultdict(lambda: defaultdict(list))

# ================= HELPERS =================

async def is_admin(update, user_id):
    member = await update.effective_chat.get_member(user_id)
    return member.status in ("administrator", "creator")


def has_link(message):
    if message.entities:
        for e in message.entities:
            if e.type in ["url", "text_link"]:
                return True

    if message.text:
        if re.search(r"(https?://|t\.me|www\.)", message.text.lower()):
            return True

    return False


def is_flood(chat_id, user_id):
    now = time.time()
    flood[chat_id][user_id] = [
        t for t in flood[chat_id][user_id] if now - t < FLOOD_TIME
    ]
    flood[chat_id][user_id].append(now)
    return len(flood[chat_id][user_id]) > FLOOD_LIMIT


def action_buttons(user_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚠️ Warn", callback_data=f"warn:{user_id}"),
            InlineKeyboardButton("🔇 Mute", callback_data=f"mute:{user_id}"),
            InlineKeyboardButton("⛔ Ban", callback_data=f"ban:{user_id}")
        ],
        [
            InlineKeyboardButton("👮 Panel", callback_data=f"panel:{user_id}")
        ]
    ])


def admin_panel(user_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚠️ Warn", callback_data=f"warn:{user_id}"),
            InlineKeyboardButton("➖ Unwarn", callback_data=f"unwarn:{user_id}")
        ],
        [
            InlineKeyboardButton("🔇 Mute", callback_data=f"mute:{user_id}"),
            InlineKeyboardButton("🔊 Unmute", callback_data=f"unmute:{user_id}")
        ],
        [
            InlineKeyboardButton("⛔ Ban", callback_data=f"ban:{user_id}"),
            InlineKeyboardButton("✅ Unban", callback_data=f"unban:{user_id}")
        ],
        [
            InlineKeyboardButton("♻️ Reset", callback_data=f"reset:{user_id}")
        ]
    ])

# ================= CORE =================

async def mute(update, context, user_id):
    if await is_admin(update, user_id):
        return

    until = datetime.now() + timedelta(seconds=MUTE_TIME)

    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        user_id,
        ChatPermissions(can_send_messages=False),
        until_date=until
    )


async def unmute(update, context, user_id):
    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        user_id,
        ChatPermissions(can_send_messages=True)
    )


async def ban(update, context, user_id):
    if await is_admin(update, user_id):
        return
    await context.bot.ban_chat_member(update.effective_chat.id, user_id)


async def unban(update, context, user_id):
    await context.bot.unban_chat_member(update.effective_chat.id, user_id)


async def warn(update, context, user_id):
    chat = update.effective_chat.id
    warns[chat][user_id] += 1
    count = warns[chat][user_id]

    if count >= MAX_WARN:
        await mute(update, context, user_id)
        warns[chat][user_id] = 0
        return "🔇 3 warn → mute"

    return f"⚠️ Warn {count}/{MAX_WARN}"


async def unwarn(update, context, user_id):
    chat = update.effective_chat.id
    warns[chat][user_id] = max(0, warns[chat][user_id] - 1)


async def reset_warn(update, context, user_id):
    chat = update.effective_chat.id
    warns[chat][user_id] = 0

# ================= CALLBACK =================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, user_id = query.data.split(":")
    user_id = int(user_id)

    member = await query.message.chat.get_member(query.from_user.id)
    if member.status not in ("administrator", "creator"):
        return await query.answer("Yetkin yok!", show_alert=True)

    fake_update = Update(update.update_id, message=query.message)

    if action == "panel":
        return await query.edit_message_text(
            "👮 Admin Panel",
            reply_markup=admin_panel(user_id)
        )

    if action == "warn":
        msg = await warn(fake_update, context, user_id)
        return await query.edit_message_text(msg)

    if action == "unwarn":
        await unwarn(fake_update, context, user_id)
        return await query.edit_message_text("➖ Warn azaltıldı")

    if action == "reset":
        await reset_warn(fake_update, context, user_id)
        return await query.edit_message_text("♻️ Warn sıfırlandı")

    if action == "mute":
        await mute(fake_update, context, user_id)
        return await query.edit_message_text("🔇 Mute")

    if action == "unmute":
        await unmute(fake_update, context, user_id)
        return await query.edit_message_text("🔊 Unmute")

    if action == "ban":
        await ban(fake_update, context, user_id)
        return await query.edit_message_text("⛔ Ban")

    if action == "unban":
        await unban(fake_update, context, user_id)
        return await query.edit_message_text("✅ Unban")

# ================= MUSIC =================

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Kullanım: /play şarkı")

    query = " ".join(context.args)
    msg = await update.message.reply_text("🎧 İndiriliyor...")

    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "noplaylist": True,
        "sleep_interval": 2,
        "max_sleep_interval": 5,
        "extractor_args": {
            "youtube": {
                "player_client": ["android"]
            }
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=True)
            video = info["entries"][0]
            file = ydl.prepare_filename(video)

        await update.message.reply_audio(
            audio=open(file, "rb"),
            title=video["title"]
        )

        os.remove(file)
        await msg.delete()

    except Exception as e:
        await msg.edit_text("❌ Müzik indirilemedi")

# ================= AUTO =================

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user = update.effective_user
    chat = update.effective_chat.id

    if await is_admin(update, user.id):
        return

    if is_flood(chat, user.id):
        await mute(update, context, user.id)
        return

    if has_link(update.message):
        try:
            await update.message.delete()
        except:
            pass

        await update.message.reply_text(
            f"🚫 {user.first_name} kural ihlali!",
            reply_markup=action_buttons(user.id)
        )

# ================= MAIN =================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("play", play))
    app.add_handler(MessageHandler(filters.ALL, message_handler))

    print("Bot aktif 🚀")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
