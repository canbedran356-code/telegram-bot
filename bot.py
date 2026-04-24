import os
import re
import json
import asyncio
import logging
import yt_dlp

from datetime import datetime, timedelta
from collections import defaultdict

from pyrogram import Client, filters as pyro_filters
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ================= CONFIG =================

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
TOKEN = os.getenv("TOKEN")

logging.basicConfig(level=logging.INFO)

# ================= USERBOT =================

userbot = Client("music", api_id=API_ID, api_hash=API_HASH)
calls = PyTgCalls(userbot)

queues = defaultdict(list)

# ================= DOWNLOAD =================

def get_audio(query):
    ydl_opts = {"format": "bestaudio", "quiet": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch:{query}", download=False)["entries"][0]
        return info["url"], info["title"]

# ================= MUSIC =================

async def play_music(chat_id):
    if not queues[chat_id]:
        return

    url, title = queues[chat_id][0]

    await calls.join_group_call(
        chat_id,
        AudioPiped(url)
    )

# ================= BOT =================

warns = defaultdict(lambda: defaultdict(int))

async def is_admin(update, user_id):
    member = await update.effective_chat.get_member(user_id)
    return member.status in ("administrator", "creator")

# ================= COMMANDS =================

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("🎧 /play şarkı")

    query = " ".join(context.args)
    msg = await update.message.reply_text("🔍 aranıyor...")

    try:
        url, title = get_audio(query)
        chat_id = update.effective_chat.id

        queues[chat_id].append((url, title))

        if len(queues[chat_id]) == 1:
            await play_music(chat_id)
            await msg.edit_text(f"🎶 Çalıyor:\n{title}")
        else:
            await msg.edit_text(f"➕ Kuyruğa eklendi:\n{title}")

    except Exception as e:
        await msg.edit_text(f"❌ Hata: {e}")

async def skip(update, context):
    chat_id = update.effective_chat.id

    if queues[chat_id]:
        queues[chat_id].pop(0)

    if queues[chat_id]:
        await play_music(chat_id)
        await update.message.reply_text("⏭ Sonraki şarkı")
    else:
        await calls.leave_group_call(chat_id)
        await update.message.reply_text("⏹ Kuyruk bitti")

async def stop(update, context):
    chat_id = update.effective_chat.id
    queues[chat_id].clear()
    await calls.leave_group_call(chat_id)
    await update.message.reply_text("⛔ Durduruldu")

async def pause(update, context):
    await calls.pause_stream(update.effective_chat.id)
    await update.message.reply_text("⏸ Duraklatıldı")

async def resume(update, context):
    await calls.resume_stream(update.effective_chat.id)
    await update.message.reply_text("▶️ Devam")

# ================= MODERATION =================

async def warn(update, context):
    if not update.message.reply_to_message:
        return await update.message.reply_text("❌ Reply yap")

    user_id = update.message.reply_to_message.from_user.id

    if await is_admin(update, user_id):
        return await update.message.reply_text("❌ Admin")

    chat = update.effective_chat.id
    warns[chat][user_id] += 1

    if warns[chat][user_id] >= 3:
        warns[chat][user_id] = 0
        await context.bot.restrict_chat_member(
            chat,
            user_id,
            ChatPermissions(can_send_messages=False),
            until_date=datetime.now() + timedelta(minutes=5)
        )
        return await update.message.reply_text("🔇 Mute (3 warn)")

    await update.message.reply_text(f"⚠️ Warn {warns[chat][user_id]}/3")

# ================= PANEL =================

def panel(uid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Warn", callback_data=f"warn:{uid}")],
        [InlineKeyboardButton("Mute", callback_data=f"mute:{uid}")]
    ])

async def panel_cmd(update, context):
    if not update.message.reply_to_message:
        return
    uid = update.message.reply_to_message.from_user.id
    await update.message.reply_text("Panel", reply_markup=panel(uid))

async def button(update, context):
    q = update.callback_query
    await q.answer()

    action, uid = q.data.split(":")
    uid = int(uid)

    if not await is_admin(update, q.from_user.id):
        return await q.edit_message_text("❌ Yetki yok")

    if action == "warn":
        warns[update.effective_chat.id][uid] += 1
        await q.edit_message_text("⚠️ Warn verildi")

    elif action == "mute":
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            uid,
            ChatPermissions(can_send_messages=False)
        )
        await q.edit_message_text("🔇 Mute")

# ================= MAIN =================

async def main():
    await userbot.start()
    await calls.start()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("play", play))
    app.add_handler(CommandHandler("skip", skip))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("pause", pause))
    app.add_handler(CommandHandler("resume", resume))

    app.add_handler(CommandHandler("warn", warn))
    app.add_handler(CommandHandler("panel", panel_cmd))

    app.add_handler(CallbackQueryHandler(button))

    print("👑 GOD MODE MUSIC BOT AKTİF")
    await app.run_polling()

asyncio.run(main())
