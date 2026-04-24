import os
import time
import re
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from telegram import Update, ChatPermissions
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError
from telegram.constants import ParseMode

TOKEN = os.getenv("TOKEN")
LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", "0"))

FLOOD_MAX_MESSAGES = 5
FLOOD_TIME_WINDOW = 10
MUTE_DURATION_SEC = 60
MAX_WARNINGS = 3

BANNED_WORDS = [
    "spam", "reklam", "kripto", "forex",
    "casino", "bahis", "hack"
]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

flood_tracker = defaultdict(lambda: defaultdict(list))
user_warnings = defaultdict(lambda: defaultdict(int))


# ================= HELPERS =================

def is_admin(member):
    return member.status in ("administrator", "creator")


async def get_member(update, user_id):
    try:
        return await update.effective_chat.get_member(user_id)
    except:
        return None


async def is_user_admin(update, user_id):
    member = await get_member(update, user_id)
    return member and is_admin(member)


def contains_link(text):
    return bool(re.search(r"(https?://|t\.me/|www\.)", text.lower()))


def contains_banned_word(text):
    for w in BANNED_WORDS:
        if w in text.lower():
            return w
    return None


def check_flood(chat_id, user_id):
    now = time.time()
    flood_tracker[chat_id][user_id] = [
        t for t in flood_tracker[chat_id][user_id] if now - t < FLOOD_TIME_WINDOW
    ]
    flood_tracker[chat_id][user_id].append(now)
    return len(flood_tracker[chat_id][user_id]) > FLOOD_MAX_MESSAGES


async def log(context, text):
    if LOG_CHAT_ID != 0:
        try:
            await context.bot.send_message(LOG_CHAT_ID, text, parse_mode=ParseMode.HTML)
        except:
            pass


# ================= ACTIONS =================

async def warn_user(update, context, user_id, reason):
    if await is_user_admin(update, user_id):
        return

    chat_id = update.effective_chat.id
    user_warnings[chat_id][user_id] += 1
    count = user_warnings[chat_id][user_id]

    name = update.effective_user.first_name

    await log(context, f"⚠️ {name} warn aldı ({count}) - {reason}")

    if count >= MAX_WARNINGS:
        await context.bot.ban_chat_member(chat_id, user_id)
        await update.message.reply_text("🚫 Kullanıcı banlandı (warn limiti)")
        await log(context, f"⛔ {name} banlandı (warn limit)")
        user_warnings[chat_id][user_id] = 0
    else:
        await update.message.reply_text(f"⚠️ Warn: {count}/{MAX_WARNINGS}")


async def unwarn_user(update, context, user_id):
    chat_id = update.effective_chat.id

    if user_warnings[chat_id][user_id] > 0:
        user_warnings[chat_id][user_id] -= 1

    await update.message.reply_text("✅ Warn silindi")


async def reset_warnings(update, context, user_id):
    chat_id = update.effective_chat.id
    user_warnings[chat_id][user_id] = 0
    await update.message.reply_text("♻️ Warnlar sıfırlandı")


async def mute_user(update, context, user_id, reason):
    if await is_user_admin(update, user_id):
        return

    until = datetime.now() + timedelta(seconds=MUTE_DURATION_SEC)

    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        user_id,
        ChatPermissions(can_send_messages=False),
        until_date=until
    )

    await update.message.reply_text("🔇 Susturuldu")
    await log(context, f"🔇 {user_id} mute - {reason}")


# ================= COMMANDS (KÜRTÇE) =================

async def ban(update, context):
    if not update.message.reply_to_message:
        return

    user_id = update.message.reply_to_message.from_user.id

    if await is_user_admin(update, user_id):
        await update.message.reply_text("Admin ban nabe")
        return

    await context.bot.ban_chat_member(update.effective_chat.id, user_id)
    await update.message.reply_text("🚫 Hat ban kirin")
    await log(context, f"🚫 {user_id} ban")


async def unban(update, context):
    if not context.args:
        return

    user_id = int(context.args[0])
    await context.bot.unban_chat_member(update.effective_chat.id, user_id)
    await update.message.reply_text("✅ Unban")


async def mute(update, context):
    if not update.message.reply_to_message:
        return

    user_id = update.message.reply_to_message.from_user.id
    await mute_user(update, context, user_id, "admin")


async def unmute(update, context):
    if not update.message.reply_to_message:
        return

    user_id = update.message.reply_to_message.from_user.id

    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        user_id,
        ChatPermissions(can_send_messages=True)
    )

    await update.message.reply_text("🔊 Unmute")


async def warn(update, context):
    if not update.message.reply_to_message:
        return

    user_id = update.message.reply_to_message.from_user.id
    await warn_user(update, context, user_id, "admin")


async def unwarn(update, context):
    if not update.message.reply_to_message:
        return

    user_id = update.message.reply_to_message.from_user.id
    await unwarn_user(update, context, user_id)


async def resetwarn(update, context):
    if not update.message.reply_to_message:
        return

    user_id = update.message.reply_to_message.from_user.id
    await reset_warnings(update, context, user_id)


# ================= MESSAGE =================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    chat_id = update.effective_chat.id
    text = update.message.text

    if await is_user_admin(update, user.id):
        return

    # FLOOD
    if check_flood(chat_id, user.id):
        await mute_user(update, context, user.id, "flood")
        return

    # LINK
    if contains_link(text):
        await update.message.delete()
        await warn_user(update, context, user.id, "link")
        return

    # BAD WORD
    bad = contains_banned_word(text)
    if bad:
        await warn_user(update, context, user.id, bad)
        return


# ================= MAIN =================

def main():
    if not TOKEN:
        raise ValueError("TOKEN yok")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("unmute", unmute))

    app.add_handler(CommandHandler("warn", warn))
    app.add_handler(CommandHandler("unwarn", unwarn))
    app.add_handler(CommandHandler("resetwarn", resetwarn))

    app.add_handler(MessageHandler(filters.TEXT, handle))

    print("Bot aktif...")
    app.run_polling()


if __name__ == "__main__":
    main()
