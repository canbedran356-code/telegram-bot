import os
import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import TelegramError
from telegram.constants import ParseMode

TOKEN = os.getenv(“TOKEN”)

FLOOD_MAX_MESSAGES = 5
FLOOD_TIME_WINDOW = 10
MUTE_DURATION_SEC = 60
MAX_WARNINGS = 3

BANNED_WORDS = [
“spam”, “reklam”, “kazan”, “kripto”, “forex”,
“casino”, “bahis”, “hack”, “sifre”, “kirmak”,
]

logging.basicConfig(format=”%(asctime)s | %(levelname)s | %(message)s”, level=logging.INFO)
logger = logging.getLogger(**name**)

flood_tracker = defaultdict(lambda: defaultdict(list))
user_warnings = defaultdict(lambda: defaultdict(int))

def is_admin(member):
return member.status in (“administrator”, “creator”)

async def get_member_status(update, user_id):
try:
return await update.effective_chat.get_member(user_id)
except TelegramError:
return None

def contains_banned_word(text):
lower = text.lower()
for word in BANNED_WORDS:
if word in lower:
return word
return None

async def warn_user(update, context, user_id, reason):
chat_id = update.effective_chat.id
user_warnings[chat_id][user_id] += 1
count = user_warnings[chat_id][user_id]
user = await get_member_status(update, user_id)
name = user.user.first_name if user else str(user_id)
if count >= MAX_WARNINGS:
try:
await context.bot.ban_chat_member(chat_id, user_id)
await update.effective_chat.send_message(
“<b>” + name + “</b> “ + str(MAX_WARNINGS) + “ uyari aldigi icin banlandi.\nSon ihlal: “ + reason,
parse_mode=ParseMode.HTML,
)
user_warnings[chat_id][user_id] = 0
except TelegramError as e:
logger.warning(“Ban hatasi: %s”, e)
else:
remaining = MAX_WARNINGS - count
await update.effective_chat.send_message(
“<b>” + name + “</b> uyarildi (” + str(count) + “/” + str(MAX_WARNINGS) + “)\nSebep: “ + reason + “\nDaha “ + str(remaining) + “ uyari ban.”,
parse_mode=ParseMode.HTML,
)

async def mute_user(update, context, user_id, duration_sec, reason):
chat_id = update.effective_chat.id
until = datetime.now() + timedelta(seconds=duration_sec)
no_perms = ChatPermissions(can_send_messages=False)
try:
await context.bot.restrict_chat_member(chat_id, user_id, no_perms, until_date=until)
user = await get_member_status(update, user_id)
name = user.user.first_name if user else str(user_id)
await update.effective_chat.send_message(
“<b>” + name + “</b> “ + str(duration_sec) + “ saniye susturuldu.\nSebep: “ + reason,
parse_mode=ParseMode.HTML,
)
except TelegramError as e:
logger.warning(“Mute hatasi: %s”, e)

def check_flood(chat_id, user_id):
now = time.time()
flood_tracker[chat_id][user_id] = [t for t in flood_tracker[chat_id][user_id] if now - t < FLOOD_TIME_WINDOW]
flood_tracker[chat_id][user_id].append(now)
return len(flood_tracker[chat_id][user_id]) > FLOOD_MAX_MESSAGES

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
keyboard = [
[InlineKeyboardButton(“Yardim”, callback_data=“help”)],
[InlineKeyboardButton(“Guvenlik Durumu”, callback_data=“status”)],
]
await update.message.reply_text(
“Guvenlik Botuna Hos Geldin!\n\nBen bu grubu koruyorum:\n- Spam ve flood engelleme\n- Yasakli kelime tespiti\n- Otomatik uyari ve ban”,
reply_markup=InlineKeyboardMarkup(keyboard),
)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
text = (
“Komut Listesi\n\n”
“Kullanici Komutlari\n”
“/start - Karsilama\n”
“/help - Yardim menusu\n”
“/rules - Grup kurallari\n\n”
“Admin Komutlari\n”
“/ban - Kullaniciy banla\n”
“/unban - Bani kaldir\n”
“/mute - 5 dk sustur\n”
“/unmute - Susturmay kaldir\n”
“/warn - Manuel uyari\n”
“/warnings - Uyari sayisi\n”
“/del - Mesaji sil\n”
)
await update.message.reply_text(text)

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
member = await get_member_status(update, update.effective_user.id)
if not member or not is_admin(member):
await update.message.reply_text(“Bu komut sadece adminlere acik.”)
return
if update.message.reply_to_message:
target_id = update.message.reply_to_message.from_user.id
elif context.args:
try:
target_id = int(context.args[0])
except ValueError:
await update.message.reply_text(“Gecerli bir kullanici ID gir.”)
return
else:
await update.message.reply_text(“Bir kullaniciya yanit ver veya ID belirt.”)
return
try:
await context.bot.ban_chat_member(update.effective_chat.id, target_id)
await update.message.reply_text(“Kullanici banlandi.”)
except TelegramError as e:
await update.message.reply_text(“Hata: “ + str(e))

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
member = await get_member_status(update, update.effective_user.id)
if not member or not is_admin(member):
await update.message.reply_text(“Bu komut sadece adminlere acik.”)
return
if not context.args:
await update.message.reply_text(“Kullanim: /unban <user_id>”)
return
try:
target_id = int(context.args[0])
await context.bot.unban_chat_member(update.effective_chat.id, target_id)
await update.message.reply_text(“Kullanicinin bani kaldirildi.”)
except (ValueError, TelegramError) as e:
await update.message.reply_text(“Hata: “ + str(e))

async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
member = await get_member_status(update, update.effective_user.id)
if not member or not is_admin(member):
await update.message.reply_text(“Bu komut sadece adminlere acik.”)
return
if update.message.reply_to_message:
target = update.message.reply_to_message.from_user
else:
await update.message.reply_text(“Susturmak istedigin mesaji yanitla.”)
return
await mute_user(update, context, target.id, 300, “Admin karari”)

async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
member = await get_member_status(update, update.effective_user.id)
if not member or not is_admin(member):
await update.message.reply_text(“Bu komut sadece adminlere acik.”)
return
if not update.message.reply_to_message:
await update.message.reply_text(“Susturmasi kaldirilacak mesaji yanitla.”)
return
target_id = update.message.reply_to_message.from_user.id
all_perms = ChatPermissions(
can_send_messages=True,
can_send_media_messages=True,
can_send_polls=True,
can_send_other_messages=True,
can_add_web_page_previews=True,
)
try:
await context.bot.restrict_chat_member(update.effective_chat.id, target_id, all_perms)
await update.message.reply_text(“Susturma kaldirildi.”)
except TelegramError as e:
await update.message.reply_text(“Hata: “ + str(e))

async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
member = await get_member_status(update, update.effective_user.id)
if not member or not is_admin(member):
await update.message.reply_text(“Bu komut sadece adminlere acik.”)
return
if not update.message.reply_to_message:
await update.message.reply_text(“Uyarilacak mesaji yanitla.”)
return
target_id = update.message.reply_to_message.from_user.id
reason = “ “.join(context.args) if context.args else “Admin karari”
await warn_user(update, context, target_id, reason)

async def cmd_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
chat_id = update.effective_chat.id
if update.message.reply_to_message:
target = update.message.reply_to_message.from_user
else:
target = update.effective_user
count = user_warnings[chat_id][target.id]
await update.message.reply_text(target.first_name + “ – “ + str(count) + “/” + str(MAX_WARNINGS) + “ uyari”)

async def cmd_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
member = await get_member_status(update, update.effective_user.id)
if not member or not is_admin(member):
await update.message.reply_text(“Bu komut sadece adminlere acik.”)
return
if not update.message.reply_to_message:
await update.message.reply_text(“Silinecek mesaji yanitla.”)
return
try:
await update.message.reply_to_message.delete()
await update.message.delete()
except TelegramError as e:
await update.message.reply_text(“Silinemedi: “ + str(e))

async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
await update.message.reply_text(
“Grup Kurallari\n\n”
“1. Saygi goster, hakaret etme.\n”
“2. Spam ve flood yapma.\n”
“3. Reklam ve tanitim yasak.\n”
“4. Konu disi icerik paylasmia.\n”
“5. Kisisel bilgileri paylasmia.\n\n”
“Ihlaller: Uyari - Susturma - Ban”
)

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
try:
await update.message.delete()
except TelegramError:
pass
await mute_user(update, context, user.id, MUTE_DURATION_SEC, “Flood”)
await warn_user(update, context, user.id, “Flood”)
return
bad_word = contains_banned_word(text)
if bad_word:
try:
await update.message.delete()
except TelegramError:
pass
await warn_user(update, context, user.id, “Yasakli kelime: “ + bad_word)
return
if update.effective_chat.type in (“group”, “supergroup”):
if “t.me/” in text or “telegram.me/” in text:
try:
await update.message.delete()
except TelegramError:
pass
await warn_user(update, context, user.id, “Izinsiz grup/kanal linki”)
return

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
query = update.callback_query
await query.answer()
if query.data == “help”:
await query.message.reply_text(“Yardim icin /help komutunu kullan.”)
elif query.data == “status”:
await query.message.reply_text(
“Guvenlik Durumu: AKTIF\n\n”
“Flood esigi: “ + str(FLOOD_MAX_MESSAGES) + “ mesaj / “ + str(FLOOD_TIME_WINDOW) + “s\n”
“Susturma suresi: “ + str(MUTE_DURATION_SEC) + “s\n”
“Max uyari (ban): “ + str(MAX_WARNINGS) + “\n”
“Yasakli kelime sayisi: “ + str(len(BANNED_WORDS))
)

def main():
if not TOKEN:
raise ValueError(“TOKEN ortam degiskeni tanimlanmamis!”)
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler(“start”, cmd_start))
app.add_handler(CommandHandler(“help”, cmd_help))
app.add_handler(CommandHandler(“ban”, cmd_ban))
app.add_handler(CommandHandler(“unban”, cmd_unban))
app.add_handler(CommandHandler(“mute”, cmd_mute))
app.add_handler(CommandHandler(“unmute”, cmd_unmute))
app.add_handler(CommandHandler(“warn”, cmd_warn))
app.add_handler(CommandHandler(“warnings”, cmd_warnings))
app.add_handler(CommandHandler(“del”, cmd_del))
app.add_handler(CommandHandler(“rules”, cmd_rules))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CallbackQueryHandler(button_callback))
logger.info(“Bot baslatiliyor…”)
app.run_polling()

if **name** == “**main**”:
main()
