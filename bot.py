import os
import re
import time
import logging
import requests

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


async def get_target(update, context):
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


def has_link(message):
    if message.text and re.search(r"(https?://|t\.me|www\.)", message.text.lower()):
        return True
    return False


def is_flood(chat_id, user_id):
    now = time.time()
    flood[chat_id][user_id] = [t for t in flood[chat_id][user_id] if now - t < FLOOD_TIME]
    flood[chat_id][user_id].append(now)
    return len(flood[chat_id][user_id]) > FLOOD_LIMIT

# ================= BUTTON =================

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
        ]
    ])

# ================= CORE =================

async def warn_user(update, context, user_id):
    if await is_admin(update, user_id):
        return "❌ Adminlere warn atamazsın"

    chat = update.effective_chat.id
    warns[chat][user_id] += 1

    if warns[chat][user_id] >= MAX_WARN:
        warns[chat][user_id] = 0
        await mute_user(update, context, user_id)
        return "🔇 3 warn → mute"

    return f"⚠️ Warn {warns[chat][user_id]}/{MAX_WARN}"


async def mute_user(update, context, user_id):
    if await is_admin(update, user_id):
        return "❌ Admin susturulamaz"

    until = datetime.now() + timedelta(seconds=MUTE_TIME)

    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        user_id,
        ChatPermissions(can_send_messages=False),
        until_date=until
    )
    return "🔇 Mute atıldı"


async def unmute_user(update, context, user_id):
    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        user_id,
        ChatPermissions(can_send_messages=True)
    )
    return "🔊 Unmute"


async def ban_user(update, context, user_id):
    if await is_admin(update, user_id):
        return "❌ Adminleri banlayamazsın"

    await context.bot.ban_chat_member(update.effective_chat.id, user_id)
    return "⛔ Banlandı"


async def unban_user(update, context, user_id):
    await context.bot.unban_chat_member(update.effective_chat.id, user_id)
    return "✅ Ban kaldırıldı"

# ================= COMMANDS =================

async def warn_cmd(update, context):
    user_id = await get_target(update, context)
    if not user_id:
        return await update.message.reply_text("❌ Kullanıcı bulunamadı")

    await update.message.reply_text(await warn_user(update, context, user_id))


async def mute_cmd(update, context):
    user_id = await get_target(update, context)
    if not user_id:
        return await update.message.reply_text("❌ Kullanıcı bulunamadı")

    await update.message.reply_text(await mute_user(update, context, user_id))


async def ban_cmd(update, context):
    user_id = await get_target(update, context)
    if not user_id:
        return await update.message.reply_text("❌ Kullanıcı bulunamadı")

    await update.message.reply_text(await ban_user(update, context, user_id))


async def unban_cmd(update, context):
    user_id = await get_target(update, context)
    await update.message.reply_text(await unban_user(update, context, user_id))


async def panel_cmd(update, context):
    user_id = await get_target(update, context)
    await update.message.reply_text("👮 Panel", reply_markup=admin_panel(user_id))

# ================= API MUSIC =================

def search_music(query):
    try:
        url = f"https://api.vevioz.com/api/button/mp3/{query}"
        return url
    except:
        return None


async def play(update, context):
    if not context.args:
        return await update.message.reply_text("🎧 /play şarkı adı")

    query = " ".join(context.args)
    msg = await update.message.reply_text("🎧 aranıyor...")

    try:
        link = search_music(query)

        if not link:
            return await msg.edit_text("❌ Şarkı bulunamadı")

        await update.message.reply_audio(audio=link)
        await msg.delete()

    except Exception as e:
        await msg.edit_text(f"❌ Hata: {str(e)}")

# ================= AUTO =================

async def message_handler(update, context):
    if not update.message:
        return

    user = update.effective_user
    chat = update.effective_chat.id

    if await is_admin(update, user.id):
        return

    if is_flood(chat, user.id):
        await mute_user(update, context, user.id)
        return

    if has_link(update.message):
        try:
            await update.message.delete()
        except:
            pass

        await update.message.reply_text(
            "🚫 Kural ihlali",
            reply_markup=action_buttons(user.id)
        )

# ================= MAIN =================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("warn", warn_cmd))
    app.add_handler(CommandHandler("mute", mute_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("panel", panel_cmd))
    app.add_handler(CommandHandler("play", play))

    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL, message_handler))

    print("Bot aktif 🚀")
    app.run_polling()

if __name__ == "__main__":
    main()
