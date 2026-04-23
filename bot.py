import os
import time
from collections import defaultdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

TOKEN = os.getenv("TOKEN")
ADMIN_ID = 8739789412

users = set()
message_log = defaultdict(list)

bad_words = ["küfür1", "küfür2"]

# START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users.add(update.effective_chat.id)

    keyboard = [
        [InlineKeyboardButton("📜 Kurallar", callback_data="rules")],
        [InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin")]
    ]

    await update.message.reply_text(
        "🤖 Berxwedan Nûçe Ultimate Bot",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# BUTON
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "rules":
        await query.edit_message_text("📜 Kurallar:\nSpam yasak\nLink yasak")

    elif query.data == "admin":
        if query.from_user.id != ADMIN_ID:
            await query.edit_message_text("❌ Yetki yok")
            return

        await query.edit_message_text(
            "⚙️ Admin Panel\n/ban /mute /duyuru"
        )

# HOŞGELDİN + CAPTCHA
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        await update.message.reply_text(
            f"👋 Hoş geldin {user.first_name}\nLütfen konuşmadan önce 5 saniye bekle"
        )

# KÜFÜR
async def bad_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        return

    text = update.message.text.lower()
    for word in bad_words:
        if word in text:
            await update.message.delete()
            return

# LINK ENGEL
async def link_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text and "http" in update.message.text:
        await update.message.delete()

# SPAM KORUMA
async def spam_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = time.time()

    message_log[user_id].append(now)

    # son 5 saniyede 5 mesaj
    message_log[user_id] = [
        t for t in message_log[user_id] if now - t < 5
    ]

    if len(message_log[user_id]) > 5:
        try:
            await context.bot.restrict_chat_member(
                update.effective_chat.id,
                user_id,
                permissions={}
            )
            await update.message.reply_text("🚫 Spam yaptın, susturuldun")
        except:
            pass

# BAN
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not update.message.reply_to_message:
        return

    user_id = update.message.reply_to_message.from_user.id

    await context.bot.ban_chat_member(update.effective_chat.id, user_id)
    await update.message.reply_text("👢 Banlandı")

# MUTE
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not update.message.reply_to_message:
        return

    user_id = update.message.reply_to_message.from_user.id

    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        user_id,
        permissions={}
    )
    await update.message.reply_text("🔇 Susturuldu")

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
app.add_handler(CommandHandler("mute", mute))
app.add_handler(CommandHandler("duyuru", duyuru))

app.add_handler(CallbackQueryHandler(button))

app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bad_filter))
app.add_handler(MessageHandler(filters.TEXT, link_filter))
app.add_handler(MessageHandler(filters.ALL, spam_filter))
app.add_handler(MessageHandler(filters.ALL, save_user))

app.run_polling()
