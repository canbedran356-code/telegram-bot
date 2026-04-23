import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

TOKEN = os.getenv("TOKEN")

ADMIN_ID = 123456789  # kendi ID

bad_words = ["küfür1", "küfür2"]

# START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 GroupHelp tarzı bot aktif!")

# HOŞGELDİN
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        await update.message.reply_text(f"👋 Hoş geldin {user.first_name}")

# KÜFÜR FİLTRE
async def filter_bad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()

    for word in bad_words:
        if word in text:
            await update.message.delete()
            break

# LINK ENGEL
async def link_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "http" in update.message.text:
        await update.message.delete()

# BAN
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return
    
    if update.message.reply_to_message:
        user_id = update.message.reply_to_message.from_user.id
        await context.bot.ban_chat_member(update.message.chat_id, user_id)

# MUTE
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    if update.message.reply_to_message:
        user_id = update.message.reply_to_message.from_user.id
        await context.bot.restrict_chat_member(
            update.message.chat_id,
            user_id,
            permissions={}
        )

# DUYURU
users = set()

async def save_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users.add(update.message.chat_id)

async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    msg = " ".join(context.args)

    for user in users:
        try:
            await context.bot.send_message(user, msg)
        except:
            pass

# APP
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("ban", ban))
app.add_handler(CommandHandler("mute", mute))
app.add_handler(CommandHandler("duyuru", duyuru))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, filter_bad))
app.add_handler(MessageHandler(filters.TEXT, link_block))
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
app.add_handler(MessageHandler(filters.ALL, save_user))

app.run_polling()
