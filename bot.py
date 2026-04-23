import os
import time
from collections import defaultdict
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

TOKEN = os.getenv("TOKEN")
ADMIN_ID = 8739789412

users = set()
warnings = defaultdict(int)
message_log = defaultdict(list)

bad_words = ["küfür1", "küfür2"]

# START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users.add(update.effective_chat.id)
    await update.message.reply_text("🤖 Ultimate Bot Aktif")

# KÜFÜR + WARNING
async def bad_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        return

    text = update.message.text.lower()
    user_id = update.effective_user.id

    for word in bad_words:
        if word in text:
            warnings[user_id] += 1

            try:
                await update.message.delete()
            except:
                pass

            if warnings[user_id] >= 3:
                await context.bot.ban_chat_member(update.effective_chat.id, user_id)
                await update.message.reply_text("👢 3 uyarı → banlandı")
            else:
                await update.message.reply_text(f"⚠️ Uyarı {warnings[user_id]}/3")
            return

# LINK ENGEL
async def link_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text and "http" in update.message.text:
        try:
            await update.message.delete()
        except:
            pass

# SPAM
async def spam_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = time.time()

    message_log[user_id].append(now)
    message_log[user_id] = [t for t in message_log[user_id] if now - t < 5]

    if len(message_log[user_id]) > 6:
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            user_id,
            permissions={}
        )
        await update.message.reply_text("🚫 Spam → susturuldun")

# BAN
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not update.message.reply_to_message:
        return

    user_id = update.message.reply_to_message.from_user.id
    await context.bot.ban_chat_member(update.effective_chat.id, user_id)
    await update.message.reply_text("👢 Banlandı")

# UNBAN
async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not update.message.reply_to_message:
        return

    user_id = update.message.reply_to_message.from_user.id
    await context.bot.unban_chat_member(update.effective_chat.id, user_id)
    await update.message.reply_text("✅ Ban kaldırıldı")

# SÜRELİ MUTE
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not update.message.reply_to_message:
        return

    args = context.args
    user_id = update.message.reply_to_message.from_user.id

    duration = 60  # default 1 dk

    if args:
        arg = args[0]
        if "m" in arg:
            duration = int(arg.replace("m", "")) * 60
        elif "h" in arg:
            duration = int(arg.replace("h", "")) * 3600

    until = datetime.utcnow() + timedelta(seconds=duration)

    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        user_id,
        permissions={},
        until_date=until
    )

    await update.message.reply_text(f"🔇 Susturuldu ({duration} saniye)")

# UNMUTE
async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not update.message.reply_to_message:
        return

    user_id = update.message.reply_to_message.from_user.id

    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        user_id,
        permissions={
            "can_send_messages": True,
            "can_send_media_messages": True,
            "can_send_other_messages": True,
            "can_add_web_page_previews": True
        }
    )

    await update.message.reply_text("🔊 Susturma kaldırıldı")

# DUYURU
async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    msg = " ".join(context.args)

    for user in users:
        try:
            await context.bot.send_message(user, msg)
        except:
            pass

    await update.message.reply_text("📢 Gönderildi")

# KAYIT
async def save_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users.add(update.effective_chat.id)

# APP
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("ban", ban))
app.add_handler(CommandHandler("unban", unban))
app.add_handler(CommandHandler("mute", mute))
app.add_handler(CommandHandler("unmute", unmute))
app.add_handler(CommandHandler("duyuru", duyuru))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bad_filter))
app.add_handler(MessageHandler(filters.TEXT, link_filter))
app.add_handler(MessageHandler(filters.ALL, spam_filter))
app.add_handler(MessageHandler(filters.ALL, save_user))

app.run_polling()
