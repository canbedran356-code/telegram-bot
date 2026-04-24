import os
import time
import re
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from telegram import Update, ChatPermissions
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

TOKEN = os.getenv("TOKEN")
LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", "0"))

FLOOD_MAX = 5
FLOOD_TIME = 10
MUTE_TIME = 120
MAX_WARN = 3

logging.basicConfig(level=logging.INFO)

flood = defaultdict(lambda: defaultdict(list))
warns = defaultdict(lambda: defaultdict(int))


# ================= HELPERS =================

async def is_admin(update, user_id):
    member = await update.effective_chat.get_member(user_id)
    return member.status in ("administrator", "creator")


def has_link(text):
    return bool(re.search(r"(https?://|t\.me|www\.)", text.lower()))


def check_flood(chat_id, user_id):
    now = time.time()
    flood[chat_id][user_id] = [
        t for t in flood[chat_id][user_id] if now - t < FLOOD_TIME
    ]
    flood[chat_id][user_id].append(now)
    return len(flood[chat_id][user_id]) > FLOOD_MAX


async def log_action(context, update, action, reason=""):
    if not LOG_CHAT_ID:
        return

    user = update.effective_user
    chat = update.effective_chat

    text = f"""
<b>📌 ACTION:</b> {action}
<b>👤 USER:</b> {user.first_name}
<b>🆔 ID:</b> <code>{user.id}</code>
<b>💬 CHAT:</b> {chat.title}
<b>🆔 CHAT ID:</b> <code>{chat.id}</code>
<b>📝 REASON:</b> {reason}
"""

    try:
        await context.bot.send_message(LOG_CHAT_ID, text, parse_mode=ParseMode.HTML)
    except:
        pass


# ================= ACTIONS =================

async def warn_user(update, context, user_id, reason):
    if await is_admin(update, user_id):
        return

    chat_id = update.effective_chat.id
    warns[chat_id][user_id] += 1
    count = warns[chat_id][user_id]

    await log_action(context, update, "WARN", reason)

    if count >= MAX_WARN:
        await mute_user(update, context, user_id, "3 warn")
        warns[chat_id][user_id] = 0
        await update.message.reply_text("🔇 3 warn → mute kirin")
    else:
        await update.message.reply_text(f"⚠️ Warn: {count}/{MAX_WARN}")


async def mute_user(update, context, user_id, reason):
    if await is_admin(update, user_id):
        return

    until = datetime.now() + timedelta(seconds=MUTE_TIME)

    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        user_id,
        ChatPermissions(can_send_messages=False),
        until_date=until
    )

    await update.message.reply_text("🔇 Mute kirin")
    await log_action(context, update, "MUTE", reason)


# ================= COMMANDS =================

async def warn_cmd(update, context):
    if not update.message.reply_to_message:
        return

    user_id = update.message.reply_to_message.from_user.id
    await warn_user(update, context, user_id, "admin")


async def unwarn_cmd(update, context):
    if not update.message.reply_to_message:
        return

    user_id = update.message.reply_to_message.from_user.id
    chat_id = update.effective_chat.id

    if warns[chat_id][user_id] > 0:
        warns[chat_id][user_id] -= 1

    await update.message.reply_text("✅ Unwarn")
    await log_action(context, update, "UNWARN")


async def mute_cmd(update, context):
    if not update.message.reply_to_message:
        return

    user_id = update.message.reply_to_message.from_user.id
    await mute_user(update, context, user_id, "admin")


# ================= MESSAGE =================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    chat_id = update.effective_chat.id
    text = update.message.text

    if await is_admin(update, user.id):
        return

    # FLOOD
    if check_flood(chat_id, user.id):
        await mute_user(update, context, user.id, "flood")
        return

    # LINK
    if has_link(text):
        await update.message.delete()
        await warn_user(update, context, user.id, "link")
        return


# ================= WELCOME =================

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for m in update.message.new_chat_members:
        await update.message.reply_text(f"👋 Tu hatî {m.first_name}")


# ================= MAIN =================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("warn", warn_cmd))
    app.add_handler(CommandHandler("unwarn", unwarn_cmd))
    app.add_handler(CommandHandler("mute", mute_cmd))

    app.add_handler(MessageHandler(filters.TEXT, handle))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

    print("Bot aktif 🔥")
    app.run_polling()


if __name__ == "__main__":
    main()
