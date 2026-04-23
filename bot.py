import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📜 Kurallar", callback_data="rules")],
        [InlineKeyboardButton("👮 Admin", callback_data="admin")],
        [InlineKeyboardButton("ℹ️ Yardım", callback_data="help")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Hoş geldin 👋\nBir seçenek seç:",
        reply_markup=reply_markup
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "rules":
        await query.edit_message_text("📜 Grup kuralları:\n- Spam yasak\n- Küfür yasak")

    elif query.data == "admin":
        await query.edit_message_text("👮 Admin: @kullanici_adin")

    elif query.data == "help":
        await query.edit_message_text("ℹ️ Yardım için adminle iletişime geç")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))

app.run_polling()
