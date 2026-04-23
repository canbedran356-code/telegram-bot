import os
import time
import random
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

settings = {
    "link": True,
    "spam": True,
    "ai": True
}

# Basit AI cevap sistemi
ai_replies = [
    "Anladım 👍",
    "Bu konuda yardımcı olabilirim",
    "Detay verir misin?",
    "İlginç bir konu 🤔",
    "Bunu biraz açar mısın?",
]

# Basit AI filtre kelimeleri
bad_patterns = ["aptal", "salak", "orospu", "amk"]

# START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users.add(update.effective_chat.id)
    await update.message.reply_text("🤖 AI BOT AKTİF")

# STATS
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👥 Kullanıcı: {len(users)}\n⚠️ Uyarı: {sum(warnings.values())}"
    )

# AYAR
async def ayar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if len(context.args) >= 2:
        key = context.args[0]
        val = context.args[1]

        if key in settings:
            settings[key] = (val == "on")
            await update.message.reply_text(f"{key} → {settings[key]}")
            return

    await update.message.reply_text(
        f"Ayarlar:\n{settings}\nKullanım: /ayar link off"
    )

# AI MODERASYON
async def ai_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not settings["ai"]:
        return

    if not update.message.text:
        return

    text = update.message.text.lower()
    user_id = update.effective_user.id

    for bad in bad_patterns:
        if bad in text:
            warnings[user_id] += 1

            try:
                await update.message.delete()
            except:
                pass

            if warnings[user_id] >= 3:
                await context.bot.ban_chat_member(update.effective_chat.id, user_id)
                await update.message.reply_text("👢 AI: 3 uyarı → ban")
            else:
                await update.message.reply_text(f"⚠️ AI Uyarı {warnings[user_id]}/3")
            return

# AI CHAT
async def ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not settings["ai"]:
        return

    if not update.message.text:
        return

    # sadece mention veya reply ise cevap ver
    if "@"+context.bot.username.lower() in update.message.text.lower() or update.message.reply_to_message:
        reply = random.choice(ai_replies)
        await update.message.reply_text(reply)

# LINK
async def link_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not settings["link"]:
        return

    if update.message.text and "http" in update.message.text:
        try:
            await update.message.delete()
        except:
            pass

# SPAM
async def spam_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not settings["spam"]:
        return

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
        await update.message.reply_text("🚫 Spam → mute")

# BAN
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not update.message.reply_to_message:
        return

    user_id = update.message.reply_to_message.from_user.id
    await context.bot.ban_chat_member(update.effective_chat.id, user_id)

# UNBAN
async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not update.message.reply_to_message:
        return

    user_id = update.message.reply_to_message.from_user.id
    await context.bot.unban_chat_member(update.effective_chat.id, user_id)

# MUTE
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not update.message.reply_to_message:
        return

    user_id = update.message.reply_to_message.from_user.id
    duration = 60

    if context.args:
        arg = context.args[0]
        if "m" in arg:
            duration = int(arg.replace("m",""))*60
        elif "h" in arg:
            duration = int(arg.replace("h",""))*3600

    until = datetime.utcnow() + timedelta(seconds=duration)

    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        user_id,
        permissions={},
        until_date=until
    )

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

# SAVE
async def save_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users.add(update.effective_chat.id)

# APP
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("ban", ban))
app.add_handler(CommandHandler("unban", unban))
app.add_handler(CommandHandler("mute", mute))
app.add_handler(CommandHandler("unmute", unmute))
app.add_handler(CommandHandler("duyuru", duyuru))
app.add_handler(CommandHandler("ayar", ayar))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_filter))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, link_filter))
app.add_handler(MessageHandler(filters.ALL, spam_filter))
app.add_handler(MessageHandler(filters.TEXT, ai_chat))
app.add_handler(MessageHandler(filters.ALL, save_user))

app.run_polling()
