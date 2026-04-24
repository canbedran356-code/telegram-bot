import logging
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

TOKEN = "TOKENİNİ BURAYA KOY"

logging.basicConfig(level=logging.INFO)

# Hoş geldin
async def welcome_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        await update.message.reply_text(
            f"Hoş geldin {member.first_name}! 👋"
        )

# Link kontrol
def has_link(text):
    return bool(re.search(r"(https?://|t\.me|www\.)", text.lower()))

async def check_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if has_link(text):
        await update.message.delete()
        await update.message.reply_text("⚠️ Link yasak!")

# Gerçek ban
async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Birine cevap vererek kullan.")
        return

    user_id = update.message.reply_to_message.from_user.id

    await context.bot.ban_chat_member(update.effective_chat.id, user_id)
    await update.message.reply_text("🚫 Banlandı")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_member))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_messages))
    app.add_handler(CommandHandler("ban", ban_user))

    print("Bot çalışıyor...")
    app.run_polling()
