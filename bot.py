import os
import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from telegram import (
Update,
ChatPermissions,
InlineKeyboardButton,
InlineKeyboardMarkup,
)
from telegram.ext import (
ApplicationBuilder,
CommandHandler,
MessageHandler,
CallbackQueryHandler,
filters,
ContextTypes,
)
from telegram.error import TelegramError
from telegram.constants import ParseMode

# ─────────────────────────────────────────

# YAPILANDIRMA

# ─────────────────────────────────────────

TOKEN = os.getenv(“TOKEN”)   # Telegram bot token

# Flood / spam limitleri

FLOOD_MAX_MESSAGES = 5        # Bu kadar mesaj
FLOOD_TIME_WINDOW  = 10       # … bu kadar saniye içinde -> uyarı
MUTE_DURATION_SEC  = 60       # Susturma süresi (saniye)
MAX_WARNINGS       = 3        # Kaç uyarıda ban?

# Yasaklı kelimeler (küçük harfe çevrilip kontrol edilir)

BANNED_WORDS = [
“spam”, “reklam”, “kazan”, “kripto”, “forex”,
“casino”, “bahis”, “hack”, “şifre”, “kırmak”,
]

# Loglama

logging.basicConfig(
format=”%(asctime)s | %(levelname)s | %(message)s”,
level=logging.INFO,
)
logger = logging.getLogger(**name**)

# ─────────────────────────────────────────

# DURUM TABLOLARI (bellekte)

# ─────────────────────────────────────────

flood_tracker: dict[int, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))

# flood_tracker[chat_id][user_id] = [timestamp, …]

user_warnings: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))

# user_warnings[chat_id][user_id] = uyarı_sayısı

# ─────────────────────────────────────────

# YARDIMCI FONKSİYONLAR

# ─────────────────────────────────────────

def is_admin(member) -> bool:
“”“Kullanıcının admin/owner olup olmadığını döner.”””
return member.status in (“administrator”, “creator”)

async def get_member_status(update: Update, user_id: int):
try:
return await update.effective_chat.get_member(user_id)
except TelegramError:
return None

def contains_banned_word(text: str) -> str | None:
“”“Metinde yasaklı kelime varsa döner, yoksa None.”””
lower = text.lower()
for word in BANNED_WORDS:
if word in lower:
return word
return None

async def warn_user(
update: Update,
context: ContextTypes.DEFAULT_TYPE,
user_id: int,
reason: str,
) -> None:
“”“Kullanıcıya uyarı ver; limite ulaşırsa banla.”””
chat_id = update.effective_chat.id
user_warnings[chat_id][user_id] += 1
count = user_warnings[chat_id][user_id]

```
user = await get_member_status(update, user_id)
name = user.user.first_name if user else str(user_id)

if count >= MAX_WARNINGS:
    try:
        await context.bot.ban_chat_member(chat_id, user_id)
        await update.effective_chat.send_message(
            f"🚫 <b>{name}</b> {MAX_WARNINGS} uyarı aldığı için gruptan banlandı.\n"
            f"Son ihlal: {reason}",
            parse_mode=ParseMode.HTML,
        )
        user_warnings[chat_id][user_id] = 0
    except TelegramError as e:
        logger.warning("Ban hatası: %s", e)
else:
    remaining = MAX_WARNINGS - count
    await update.effective_chat.send_message(
        f"⚠️ <b>{name}</b> uyarıldı ({count}/{MAX_WARNINGS})\n"
        f"Sebep: {reason}\n"
        f"Daha {remaining} uyarı -> ban.",
        parse_mode=ParseMode.HTML,
    )
```

async def mute_user(
update: Update,
context: ContextTypes.DEFAULT_TYPE,
user_id: int,
duration_sec: int,
reason: str,
) -> None:
“”“Kullanıcıyı geçici sustur.”””
chat_id = update.effective_chat.id
until = datetime.now() + timedelta(seconds=duration_sec)
no_perms = ChatPermissions(can_send_messages=False)
try:
await context.bot.restrict_chat_member(
chat_id, user_id, no_perms, until_date=until
)
user = await get_member_status(update, user_id)
name = user.user.first_name if user else str(user_id)
await update.effective_chat.send_message(
f”🔇 <b>{name}</b> {duration_sec} saniyeliğine susturuldu.\n”
f”Sebep: {reason}”,
parse_mode=ParseMode.HTML,
)
except TelegramError as e:
logger.warning(“Mute hatası: %s”, e)

# ─────────────────────────────────────────

# FLOOD KORUMASI

# ─────────────────────────────────────────

def check_flood(chat_id: int, user_id: int) -> bool:
“”“True -> flood tespit edildi.”””
now = time.time()
timestamps = flood_tracker[chat_id][user_id]

```
# Eski kayıtları temizle
flood_tracker[chat_id][user_id] = [
    t for t in timestamps if now - t < FLOOD_TIME_WINDOW
]
flood_tracker[chat_id][user_id].append(now)

return len(flood_tracker[chat_id][user_id]) > FLOOD_MAX_MESSAGES
```

# ─────────────────────────────────────────

# KOMUT İŞLEYİCİLER

# ─────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
keyboard = [
[InlineKeyboardButton(“📋 Yardım”, callback_data=“help”)],
[InlineKeyboardButton(“🛡️ Güvenlik Durumu”, callback_data=“status”)],
]
await update.message.reply_text(
“👋 <b>Güvenlik Botuna Hoş Geldin!</b>\n\n”
“Ben bu grubu koruyorum:\n”
“✅ Spam & flood engelleme\n”
“✅ Yasaklı kelime tespiti\n”
“✅ Otomatik uyarı & ban\n\n”
“Aşağıdaki butonları veya komutları kullanabilirsin.”,
parse_mode=ParseMode.HTML,
reply_markup=InlineKeyboardMarkup(keyboard),
)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
text = (
“📋 <b>Komut Listesi</b>\n\n”
“<b>👤 Kullanıcı Komutları</b>\n”
“/start - Karşılama mesajı\n”
“/help  - Bu yardım menüsü\n\n”
“<b>🔧 Admin Komutları</b>\n”
“/ban @kullanici - Kullanıcıyı banla\n”
“/unban @kullanici - Banı kaldır\n”
“/mute @kullanici - 5 dk sustur\n”
“/unmute @kullanici - Susturmayı kaldır\n”
“/warn @kullanici - Manuel uyarı ver\n”
“/warnings @kullanici - Uyarı sayısını gör\n”
“/del - Yanıtlanan mesajı sil\n”
“/rules - Grup kurallarını göster\n”
)
await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
member = await get_member_status(update, update.effective_user.id)
if not member or not is_admin(member):
await update.message.reply_text(“❌ Bu komut sadece adminlere açık.”)
return

```
if update.message.reply_to_message:
    target_id = update.message.reply_to_message.from_user.id
elif context.args:
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Geçerli bir kullanıcı ID'si gir.")
        return
else:
    await update.message.reply_text("Bir kullanıcıya yanıt ver veya ID belirt.")
    return

try:
    await context.bot.ban_chat_member(update.effective_chat.id, target_id)
    await update.message.reply_text(f"🚫 Kullanıcı {target_id} banlandı.")
except TelegramError as e:
    await update.message.reply_text(f"Hata: {e}")
```

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
member = await get_member_status(update, update.effective_user.id)
if not member or not is_admin(member):
await update.message.reply_text(“❌ Bu komut sadece adminlere açık.”)
return

```
if not context.args:
    await update.message.reply_text("Kullanım: /unban <user_id>")
    return

try:
    target_id = int(context.args[0])
    await context.bot.unban_chat_member(update.effective_chat.id, target_id)
    await update.message.reply_text(f"✅ Kullanıcı {target_id}'nin banı kaldırıldı.")
except (ValueError, TelegramError) as e:
    await update.message.reply_text(f"Hata: {e}")
```

async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
member = await get_member_status(update, update.effective_user.id)
if not member or not is_admin(member):
await update.message.reply_text(“❌ Bu komut sadece adminlere açık.”)
return

```
if update.message.reply_to_message:
    target = update.message.reply_to_message.from_user
else:
    await update.message.reply_text("Susturmak istediğin mesajı yanıtla.")
    return

await mute_user(update, context, target.id, 300, "Admin kararı")
```

async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
member = await get_member_status(update, update.effective_user.id)
if not member or not is_admin(member):
await update.message.reply_text(“❌ Bu komut sadece adminlere açık.”)
return

```
if not update.message.reply_to_message:
    await update.message.reply_text("Susturması kaldırılacak mesajı yanıtla.")
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
    await context.bot.restrict_chat_member(
        update.effective_chat.id, target_id, all_perms
    )
    await update.message.reply_text("✅ Susturma kaldırıldı.")
except TelegramError as e:
    await update.message.reply_text(f"Hata: {e}")
```

async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
member = await get_member_status(update, update.effective_user.id)
if not member or not is_admin(member):
await update.message.reply_text(“❌ Bu komut sadece adminlere açık.”)
return

```
if not update.message.reply_to_message:
    await update.message.reply_text("Uyarılacak mesajı yanıtla.")
    return

target_id = update.message.reply_to_message.from_user.id
reason = " ".join(context.args) if context.args else "Admin kararı"
await warn_user(update, context, target_id, reason)
```

async def cmd_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
chat_id = update.effective_chat.id
if update.message.reply_to_message:
target = update.message.reply_to_message.from_user
else:
target = update.effective_user

```
count = user_warnings[chat_id][target.id]
await update.message.reply_text(
    f"⚠️ <b>{target.first_name}</b> - {count}/{MAX_WARNINGS} uyarı",
    parse_mode=ParseMode.HTML,
)
```

async def cmd_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
member = await get_member_status(update, update.effective_user.id)
if not member or not is_admin(member):
await update.message.reply_text(“❌ Bu komut sadece adminlere açık.”)
return

```
if not update.message.reply_to_message:
    await update.message.reply_text("Silinecek mesajı yanıtla.")
    return

try:
    await update.message.reply_to_message.delete()
    await update.message.delete()
except TelegramError as e:
    await update.message.reply_text(f"Silinemedi: {e}")
```

async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
await update.message.reply_text(
“📜 <b>Grup Kuralları</b>\n\n”
“1️⃣ Saygılı ol, hakaret etme.\n”
“2️⃣ Spam ve flood yapma.\n”
“3️⃣ Reklam ve tanıtım yasak.\n”
“4️⃣ Konu dışı içerik paylaşma.\n”
“5️⃣ Kişisel bilgileri paylaşma.\n\n”
“⚡ İhlaller: Uyarı -> Susturma -> Ban”,
parse_mode=ParseMode.HTML,
)

# ─────────────────────────────────────────

# MESAJ İŞLEYİCİSİ (otomatik moderasyon)

# ─────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not update.message or not update.message.text:
return

```
user    = update.effective_user
chat_id = update.effective_chat.id
text    = update.message.text

# Adminleri atla
member = await get_member_status(update, user.id)
if member and is_admin(member):
    return

# 1) Flood koruması
if check_flood(chat_id, user.id):
    try:
        await update.message.delete()
    except TelegramError:
        pass
    await mute_user(
        update, context, user.id, MUTE_DURATION_SEC,
        f"Flood ({FLOOD_MAX_MESSAGES}+ mesaj / {FLOOD_TIME_WINDOW}s)"
    )
    await warn_user(update, context, user.id, "Flood")
    return

# 2) Yasaklı kelime kontrolü
bad_word = contains_banned_word(text)
if bad_word:
    try:
        await update.message.delete()
    except TelegramError:
        pass
    await warn_user(update, context, user.id, f'Yasaklı kelime: "{bad_word}"')
    return

# 3) Link / davet engeli (grup değilse geç)
if update.effective_chat.type in ("group", "supergroup"):
    if "t.me/" in text or "telegram.me/" in text:
        try:
            await update.message.delete()
        except TelegramError:
            pass
        await warn_user(update, context, user.id, "İzinsiz grup/kanal linki")
        return
```

# ─────────────────────────────────────────

# INLINE BUTON İŞLEYİCİSİ

# ─────────────────────────────────────────

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
query = update.callback_query
await query.answer()

```
if query.data == "help":
    await query.message.reply_text(
        "📋 Yardım için /help komutunu kullan."
    )
elif query.data == "status":
    await query.message.reply_text(
        "🛡️ <b>Güvenlik Durumu: AKTİF</b>\n\n"
        f"• Flood eşiği: {FLOOD_MAX_MESSAGES} mesaj / {FLOOD_TIME_WINDOW}s\n"
        f"• Susturma süresi: {MUTE_DURATION_SEC}s\n"
        f"• Max uyarı (ban): {MAX_WARNINGS}\n"
        f"• Yasaklı kelime sayısı: {len(BANNED_WORDS)}",
        parse_mode=ParseMode.HTML,
    )
```

# ─────────────────────────────────────────

# ANA GİRİŞ NOKTASI

# ─────────────────────────────────────────

def main():
if not TOKEN:
raise ValueError(“TOKEN ortam değişkeni tanımlanmamış!”)

```
app = ApplicationBuilder().token(TOKEN).build()

# Komutlar
app.add_handler(CommandHandler("start",    cmd_start))
app.add_handler(CommandHandler("help",     cmd_help))
app.add_handler(CommandHandler("ban",      cmd_ban))
app.add_handler(CommandHandler("unban",    cmd_unban))
app.add_handler(CommandHandler("mute",     cmd_mute))
app.add_handler(CommandHandler("unmute",   cmd_unmute))
app.add_handler(CommandHandler("warn",     cmd_warn))
app.add_handler(CommandHandler("warnings", cmd_warnings))
app.add_handler(CommandHandler("del",      cmd_del))
app.add_handler(CommandHandler("rules",    cmd_rules))

# Mesaj moderasyonu
app.add_handler(MessageHandler(
    filters.TEXT & ~filters.COMMAND, handle_message
))

# Butonlar
app.add_handler(CallbackQueryHandler(button_callback))

logger.info("Bot başlatılıyor...")
app.run_polling()
```

if **name** == “**main**”:
main()
