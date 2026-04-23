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

verified_users = set()
new_users = set()
message_log = defaultdict(list)

bad_words = ["küfür1", "küfür2"]

# START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot aktif")

# HOŞGELDİN + DOĞRULAMA
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        new_users.add(user.id)

        keyboard = [[InlineKeyboardButton("✅ Doğrula", callback_data=f"verify_{user.id}")]]
        await update.message.reply_text(
            f"👋 Hoş geldin {user.first_name}\nButona basarak doğrulan",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# BUTON
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("verify_"):
        user_id = int(data.split("_")[1])

        if query.from_user.id != user_id:
            await query.answer("Bu senin değil", show_alert=True)
            return

        verified_users.add(user_id)
        if user_id in new_users:
            new_users.remove(user_id)

        await query.edit_message_text("✅ Doğrulandın!")

# DOĞRULAMA KONTROL (SADECE YENİLER)
async def check_new_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # admin geçsin
    if user_id == ADMIN_ID:
        return

    # özel mesajda çalışmasın
    if update.effective_chat.type == "private":
        return

    # sadece yeni gelenler
    if user_id in new_users and user_id not in verified_users:
        try:
            await update.message.delete()
        except:
            pass

# KÜFÜR
async def bad_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        return

    text = update.message.text.lower()
    for word in bad_words:
        if word in text:
            try:
                await update.message.delete()
            except:
                pass

# LINK ENGEL (AKILLI)
async def link_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        return

    if "http" in update.message.text:
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
        try:
            await context.bot.restrict_chat_member(
                update.effective_chat.id,
                user_id,
                permissions={}
            )
            await update.message.reply_text("🚫 Spam yaptın")
        except:
            pass

# BAN
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("❗ Reply yap")
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
users = set()

async def save_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users.add(update.effective_chat.id)

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

# APP
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("ban", ban))
app.add_handler(CommandHandler("mute", mute))
app.add_handler(CommandHandler("duyuru", duyuru))

app.add_handler(CallbackQueryHandler(button))

app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
app.add_handler(MessageHandler(filters.ALL, check_new_user))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bad_filter))
app.add_handler(MessageHandler(filters.TEXT, link_filter))
app.add_handler(MessageHandler(filters.ALL, spam_filter))
app.add_handler(MessageHandler(filters.ALL, save_user))

app.run_polling()
