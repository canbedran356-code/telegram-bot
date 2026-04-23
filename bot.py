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
verified = set()
message_log = defaultdict(list)

bad_words = ["küfür1", "küfür2"]

# START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users.add(update.effective_chat.id)

    keyboard = [
        [InlineKeyboardButton("🔐 Doğrula", callback_data="verify")],
        [InlineKeyboardButton("⚙️ Panel", callback_data="panel")]
    ]

    await update.message.reply_text(
        "🤖 Berxwedan Nûçe PRO Bot\nDevam etmek için doğrula",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# BUTON
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if query.data == "verify":
        verified.add(user_id)
        await query.edit_message_text("✅ Doğrulandı! Artık konuşabilirsin")

    elif query.data == "panel":
        if user_id != ADMIN_ID:
            await query.edit_message_text("❌ Yetki yok")
            return

        keyboard = [
            [InlineKeyboardButton("📢 Duyuru", callback_data="broadcast")],
            [InlineKeyboardButton("👢 Ban", callback_data="baninfo")]
        ]

        await query.edit_message_text(
            "⚙️ Admin Panel",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "broadcast":
        await query.edit_message_text("📢 /duyuru mesaj")

    elif query.data == "baninfo":
        await query.edit_message_text("👢 Ban için reply + /ban")

# DOĞRULAMA KONTROL
async def check_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in verified:
        try:
            await update.message.delete()
        except:
            pass

# HOŞGELDİN
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        keyboard = [[InlineKeyboardButton("✅ Doğrula", callback_data="verify")]]
        await update.message.reply_text(
            f"👋 Hoş geldin {user.first_name}\nButona basarak doğrulan",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# KÜFÜR
async def bad_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text:
        text = update.message.text.lower()
        for word in bad_words:
            if word in text:
                await update.message.delete()

# LINK ENGEL
async def link_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text and "http" in update.message.text:
        await update.message.delete()

# SPAM
async def spam_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = time.time()

    message_log[user_id].append(now)
    message_log[user_id] = [t for t in message_log[user_id] if now - t < 5]

    if len(message_log[user_id]) > 5:
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            user_id,
            permissions={}
        )
        await update.message.reply_text("🚫 Spam tespit edildi")

# BAN
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not update.message.reply_to_message:
        return

    user_id = update.message.reply_to_message.from_user.id

    await context.bot.ban_chat_member(update.effective_chat.id, user_id)
    await update.message.reply_text("👢 Banlandı")

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

# KAYIT
async def save_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users.add(update.effective_chat.id)

# APP
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("ban", ban))
app.add_handler(CommandHandler("duyuru", duyuru))

app.add_handler(CallbackQueryHandler(button))

app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
app.add_handler(MessageHandler(filters.ALL, check_verify))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bad_filter))
app.add_handler(MessageHandler(filters.TEXT, link_filter))
app.add_handler(MessageHandler(filters.ALL, spam_filter))
app.add_handler(MessageHandler(filters.ALL, save_user))

app.run_polling()
