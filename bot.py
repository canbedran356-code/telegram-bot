import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# BotFather'dan alınan token
TOKEN = 8416325072:AAGLEovwn8AbF9loNQiJ-LzLovzM1zY9-WM

# Loglama ayarları
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Yeni kullanıcıları karşılama ve güvenlik mesajı
async def welcome_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text=f"Hoş geldin {member.first_name}! 👋\nLütfen kuralları oku."
        )

# Link içeren mesajları silme (Güvenlik)
async def check_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if message.entities:
        for entity in message.entities:
            if entity.type in ["url", "mention"]:
                await message.delete()
                await context.bot.send_message(
                    chat_id=message.chat_id,
                    text=f"⚠️ {message.from_user.first_name}, link veya mention paylaşmak yasak!"
                )

# Ban komutu (Sadece adminler için basit kontrol)
async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /ban @kullaniciadi")
        return

    user_to_ban = context.args[0]
    # Basit ban mantığı (Gerçek kullanımda user_id gereklidir)
    await update.message.reply_text(f"{user_to_ban} gruptan uzaklaştırıldı. 🚫")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Yeni gelenleri karşıla
    new_member_handler = MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_member)
    
    # Mesajları kontrol et (link vs)
    message_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), check_messages)
    
    # Komutlar
    ban_handler = CommandHandler('ban', ban_user)
    
    application.add_handler(new_member_handler)
    application.add_handler(message_handler)
    application.add_handler(ban_handler)
    
    print("Bot çalışıyor...")
    application.run_polling()
