import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

TOKEN = os.getenv("TOKEN")

# KENDİ ID'İNİ BURAYA KOY
ADMIN_ID = 8739789412

# Küfür listesi
bad_words = ["küfür1", "küfür2"]

users = set()

# START MENU
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📰 Nûçe", callback_data="news")],
        [InlineKeyboardButton("👮 Admin", callback_data="admin")],
        [InlineKeyboardButton("ℹ️ Bilgi", callback_data="info")]
    ]

    await update.message.reply_text(
        " Berxwedan Nûçe Bot\nHoş geldin!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# BUTON SİSTEMİ
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "news":
        await query.edit_message_text("📰 Son haberler yakında...")

    elif query.data == "info":
        await query.edit_message_text("ℹ️ Bu bot Berxwedan Nûçe içindir.")

    elif query.data == "admin":
        if query.from_user.id != ADMIN_ID:
            await query.edit_message_text("❌ Yetkin yok")
            return

        keyboard = [
            [InlineKeyboardButton("📢 Duyuru Gönder", callback_data="broadcast")]
        ]
        await query.edit_message_text(
            "⚙️ Admin Panel",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "broadcast":
        await query.edit_message_text("📢 /duyuru mesaj yaz")

# HOŞGELDİN
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        await update.message.reply_text(f"👋 Hoş geldin {user.first_name}")

# KÜFÜR FİLTRE
async def filter_bad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text:
        text = update.message.text.lower()
        for word in bad_words:
            if word in text:
                await update.message.delete()
                return

# LINK ENGEL
async def link_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text and "http" in update.message.text:
        await update.message.delete()

# BAN
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    if update.message.reply_to_message:
        user_id = update.message.reply_to_message.from_user.id
        await context.bot.ban_chat_member(update.effective_chat.id, user_id)

# MUTE
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    if update.message.reply_to_message:
        user_id = update.message.reply_to_message.from_user.id
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            user_id,
            permissions={}
        )

# KULLANICI KAYIT
async def save_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users.add(update.effective_chat.id)

# DUYURU
async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    msg = " ".join(context.args)

    for user in users:
        try:
            await context.bot.send_message(user, msg)
        except:
            pass

    await update.message.reply_text("📢 Gönderildi")

# APP
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("ban", ban))
app.add_handler(CommandHandler("mute", mute))
app.add_handler(CommandHandler("duyuru", duyuru))

app.add_handler(CallbackQueryHandler(buttons))

app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, filter_bad))
app.add_handler(MessageHandler(filters.TEXT, link_block))
app.add_handler(MessageHandler(filters.ALL, save_user))

app.run_polling()
