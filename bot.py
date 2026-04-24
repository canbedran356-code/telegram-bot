import os
import re
import time
import logging
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
<b>📌 {action}</b>
👤 {user.first_name}
🆔 <code>{user.id}</code>
💬 {chat.title}
📝 {reason}
"""
    try:
        await context.bot.send_message(LOG_CHAT_ID, msg, parse_mode=ParseMode.HTML)
    except:
        pass


# 🔥 USER BULMA (REPLY / ID / USERNAME)
async def resolve_user(update, context):
    # reply
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        return user.id, user.first_name

    if context.args:
        arg = context.args[0]

        # ID
        if arg.isdigit():
            try:
                member = await update.effective_chat.get_member(int(arg))
                return member.user.id, member.user.first_name
            except:
                return None, None

        # username
        if arg.startswith("@"):
            username = arg.replace("@", "").lower()

            # chat members cache yok → sadece adminlerde garanti
            admins = await update.effective_chat.get_administrators()
            for m in admins:
                if m.user.username and m.user.username.lower() == username:
                    return m.user.id, m.user.first_name

    return None, None


# ================= CORE =================

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
    await update.message.reply_text("🤖 Guard Bot aktif")

# WARN
async def warn_cmd(update, context):
    uid, name = await resolve_user(update, context)
    if not uid:
        await update.message.reply_text("Kullanıcı bulunamadı")
        return
    await warn_user(update, context, uid, "admin")


async def unwarn_cmd(update, context):
    uid, name = await resolve_user(update, context)
    if not uid:
        return

    chat = update.effective_chat.id
    if warns[chat][uid] > 0:
        warns[chat][uid] -= 1

    await update.message.reply_text("✅ Warn silindi")
    await log_action(context, update, "UNWARN")


async def resetwarn_cmd(update, context):
    uid, name = await resolve_user(update, context)
    if not uid:
        return

    chat = update.effective_chat.id
    warns[chat][uid] = 0

    await update.message.reply_text("♻️ Warn sıfırlandı")
    await log_action(context, update, "RESET WARN")


async def warnings_cmd(update, context):
    uid, name = await resolve_user(update, context)
    if not uid:
        return

    chat = update.effective_chat.id
    count = warns[chat][uid]

    await update.message.reply_text(f"⚠️ Warn: {count}/{MAX_WARN}")


# MUTE
async def mute_cmd(update, context):
    uid, name = await resolve_user(update, context)
    if not uid:
        return

    await mute_user(update, context, uid, "admin")


async def unmute_cmd(update, context):
    uid, name = await resolve_user(update, context)
    if not uid:
        return

    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        uid,
        ChatPermissions(can_send_messages=True)
    )

    await update.message.reply_text("🔊 Unmute")
    await log_action(context, update, "UNMUTE")


# BAN
async def ban_cmd(update, context):
    uid, name = await resolve_user(update, context)
    if not uid:
        return

    if await is_admin(update, uid):
        await update.message.reply_text("Admin banlanamaz")
        return

    await context.bot.ban_chat_member(update.effective_chat.id, uid)
    await update.message.reply_text("🚫 Banlandı")
    await log_action(context, update, "BAN")


async def unban_cmd(update, context):
    if context.args and context.args[0].isdigit():
        uid = int(context.args[0])
    else:
        await update.message.reply_text("ID gir")
        return

    await context.bot.unban_chat_member(update.effective_chat.id, uid)
    await update.message.reply_text("✅ Unban")
    await log_action(context, update, "UNBAN")


# ================= AUTO SYSTEM =================

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    chat = update.effective_chat.id
    text = update.message.text

    if await is_admin(update, user.id):
        return

    # flood
    if is_flood(chat, user.id):
        await mute_user(update, context, user.id, "flood")
        return

    # link
    if has_link(text):
        await update.message.delete()
        await warn_user(update, context, user.id, "link")
        return


# ================= WELCOME =================

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for m in update.message.new_chat_members:
        await update.message.reply_text(f"👋 Hoş geldin {m.first_name}")


# ================= MAIN =================

def main():
    if not TOKEN:
        raise ValueError("TOKEN yok")

    app = ApplicationBuilder().token(TOKEN).build()

    # commands
    app.add_handler(CommandHandler("start", start))

    app.add_handler(CommandHandler("warn", warn_cmd))
    app.add_handler(CommandHandler("unwarn", unwarn_cmd))
    app.add_handler(CommandHandler("resetwarn", resetwarn_cmd))
    app.add_handler(CommandHandler("warnings", warnings_cmd))

    app.add_handler(CommandHandler("mute", mute_cmd))
    app.add_handler(CommandHandler("unmute", unmute_cmd))

    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))

    # auto
    app.add_handler(MessageHandler(filters.TEXT, message_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

    print("Bot aktif 🚀")
    app.run_polling()


if __name__ == "__main__":
    main()
