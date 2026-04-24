import os
import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import TelegramError
from telegram.constants import ParseMode

TOKEN = os.getenv("TOKEN")

FLOOD_MAX_MESSAGES = 5
FLOOD_TIME_WINDOW = 10
MUTE_DURATION_SEC = 60
MAX_WARNINGS = 3

BANNED_WORDS = [
    "spam", "reklam", "kazan", "kripto", "forex",
    "casino", "bahis", "hack", "sifre", "kirmak",
]

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

flood_tracker = defaultdict(lambda: defaultdict(list))
user_warnings = defaultdict(lambda: defaultdict(int))


# ================= HELPERS =================

def is_admin(member):
    return member.status in ("administrator", "creator")


async def get_member_status(update, user_id):
    try:
        return await update.effective_chat.get_member(user_id)
    except TelegramError:
        return None


async def is_user_admin(update, user_id):
    member = await get_member_status(update, user_id)
    return member and is_admin(member)


def contains_banned_word(text):
    lower = text.lower()
    for word in BANNED_WORDS:
        if word in lower:
            return word
    return None


def check_flood(chat_id, user_id):
    now = time.time()
    flood_tracker[chat_id][user_id] = [
        t for t in flood_tracker[chat_id][user_id] if now - t < FLOOD_TIME_WINDOW
    ]
    flood_tracker[chat_id][user_id].append(now)
    return len(flood_tracker[chat_id][user_id]) > FLOOD_MAX_MESSAGES


# ================= CORE ACTIONS =================

async def warn_user(update, context, user_id, reason):
    if await is_user_admin(update, user_id):
        return

    chat_id = update.effective_chat.id
    user_warnings[chat_id][user_id] += 1
    count = user_warnings[chat_id][user_id]

    user = await get_member_status(update, user_id)
    name = user.user.first_name if user else str(user_id)

    if count >= MAX_WARNINGS:
        try:
            await context.bot.ban_chat_member(chat_id, user_id)
            await update.effective_chat.send_message(
                f"<b>{name}</b> {MAX_WARNINGS} uyarı aldı ve banlandı.\nSebep: {reason}",
                parse_mode=ParseMode.HTML,
            )
            user_warnings[chat_id][user_id] = 0
        except TelegramError as e:
            logger.warning(f"Ban hatası: {e}")
    else:
        remaining = MAX_WARNINGS - count
        await update.effective_chat.send_message(
            f"<b>{name}</b> uyarıldı ({count}/{MAX_WARNINGS})\nSebep: {reason}\nKalan: {remaining}",
            parse_mode=ParseMode.HTML,
        )


async def mute_user(update, context, user_id, duration_sec, reason):
    if await is_user_admin(update, user_id):
        return

    chat_id = update.effective_chat.id
    until = datetime.now() + timedelta(seconds=duration_sec)

    try:
        await context.bot.restrict_chat_member(
            chat_id,
            user_id,
            ChatPermissions(can_send_messages=False),
            until_date=until
        )

        user = await get_member_status(update, user_id)
        name = user.user.first_name if user else str(user_id)

        await update.effective_chat.send_message(
            f"<b>{name}</b> {duration_sec} saniye susturuldu.\nSebep: {reason}",
            parse_mode=ParseMode.HTML,
        )

    except TelegramError as e:
        logger.warning(f"Mute hatası: {e}")


# ================= COMMANDS =================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Yardım", callback_data="help")],
        [InlineKeyboardButton("Durum", callback_data="status")],
    ]
    await update.message.reply_text(
        "🤖 Güvenlik Botu Aktif!",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/ban /unban /mute /unmute /warn /warnings /admins /all /rules"
    )


async def cmd_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admins = await context.bot.get_chat_administrators(update.effective_chat.id)

    text = "👮 Adminler:\n\n"
    for admin in admins:
        text += f"- {admin.user.first_name}\n"

    await update.message.reply_text(text)


async def cmd_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bu özellik Telegram API kısıtlı (tüm üyeleri çekemezsin).")


async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return

    user_id = update.message.reply_to_message.from_user.id

    if await is_user_admin(update, user_id):
        await update.message.reply_text("Admin uyarı alamaz.")
        return

    await warn_user(update, context, user_id, "Admin uyarısı")


async def cmd_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return

    user_id = update.message.reply_to_message.from_user.id
    chat_id = update.effective_chat.id

    count = user_warnings[chat_id][user_id]
    await update.message.reply_text(f"Uyarı: {count}/{MAX_WARNINGS}")


async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return

    user_id = update.message.reply_to_message.from_user.id

    if await is_user_admin(update, user_id):
        await update.message.reply_text("Admin banlanamaz.")
        return

    await context.bot.ban_chat_member(update.effective_chat.id, user_id)
    await update.message.reply_text("Banlandı")


async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return

    user_id = int(context.args[0])
    await context.bot.unban_chat_member(update.effective_chat.id, user_id)
    await update.message.reply_text("Unban")


async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return

    user_id = update.message.reply_to_message.from_user.id

    if await is_user_admin(update, user_id):
        await update.message.reply_text("Admin susturulamaz.")
        return

    await mute_user(update, context, user_id, 300, "Admin")


async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return

    user_id = update.message.reply_to_message.from_user.id

    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        user_id,
        ChatPermissions(can_send_messages=True)
    )

    await update.message.reply_text("Unmute")


async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Kurallar: Spam yasak, saygılı ol.")


# ================= MESSAGE HANDLER =================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    chat_id = update.effective_chat.id
    text = update.message.text

    member = await get_member_status(update, user.id)
    if member and is_admin(member):
        return

    if check_flood(chat_id, user.id):
        await mute_user(update, context, user.id, MUTE_DURATION_SEC, "Flood")
        return

    bad = contains_banned_word(text)
    if bad:
        await warn_user(update, context, user.id, f"Kelime: {bad}")
        return


# ================= BUTTON =================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "help":
        await query.message.reply_text("Komutlar: /help")
    elif query.data == "status":
        await query.message.reply_text("Bot aktif ✔️")


# ================= MAIN =================

def main():
    if not TOKEN:
        raise ValueError("TOKEN yok!")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("admins", cmd_admins))
    app.add_handler(CommandHandler("all", cmd_all))
    app.add_handler(CommandHandler("warn", cmd_warn))
    app.add_handler(CommandHandler("warnings", cmd_warnings))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("mute", cmd_mute))
    app.add_handler(CommandHandler("unmute", cmd_unmute))
    app.add_handler(CommandHandler("rules", cmd_rules))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("Bot çalışıyor...")
    app.run_polling()


if __name__ == "__main__":
    main()
