import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ContentType

# --- AYARLAR ---
# BotFather'dan aldığınız token
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE" 
logging.basicConfig(level=logging.INFO)

# --- BOT BAŞLATMA ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- KOMUTLAR VE MESAJLAR ---

# /start komutu (Bot özelden yazıldığında veya gruba eklendiğinde)
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Merhaba! Ben Grup Yardım Botuyum.\n\n"
        "Grup yönetimine yardımcı olmak için buradayım.\n"
        "Kuralları öğrenmek için /kurallar komutunu kullanabilirsiniz."
    )

# /kurallar komutu (Grupta)
@dp.message(Command("kurallar"))
async def cmd_kurallar(message: types.Message):
    rules_text = (
        "📜 **Grup Kuralları**\n\n"
        "1. Saygılı olun.\n"
        "2. Spam yapmayın.\n"
        "3. Reklam içerik paylaşmayın.\n"
        "4. Küfür/Hakaret yasaktır."
    )
    await message.answer(rules_text, parse_mode="Markdown")

# /help komutu
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "🛠 **Yardım Menüsü**\n\n"
        "/kurallar - Grup kurallarını gösterir.\n"
        "/ping - Botun çalışıp çalışmadığını kontrol eder."
    )

# Yeni Üye Karşılama
@dp.message(F.content_type == ContentType.NEW_CHAT_MEMBERS)
async def welcome_member(message: types.Message):
    for member in message.new_chat_members:
        await message.answer(
            f"Hoş geldin {member.mention_markdown()}! 🎉\n"
            f"Lütfen önce kuralları oku: /kurallar",
            parse_mode="Markdown"
        )

# --- ANA DÖNGÜ ---
async def main():
    # Botu başlat (uzun yoklama - polling)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
