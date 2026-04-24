import os
import re
import time
import logging
import yt_dlp

from collections import defaultdict
from datetime import datetime, timedelta

from telegram import (
    Update, ChatPermissions,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, ContextTypes,
    CallbackQueryHandler, filters
)

# ================= CONFIG =================

TOKEN = os.getenv("TOKEN")

MAX_WARN = 3
MUTE_TIME = 300
FLOOD_LIMIT = 5
FLOOD_TIME = 10

logging.basicConfig(level=logging.INFO)

warns = defaultdict(lambda: defaultdict(int))
flood = defaultdict(lambda: defaultdict(list))

# ================= HELPERS =================

async def is_admin(update, user_id):
    member = await update.effective_chat.get_member(user_id)
    return member.status in ("administrator", "creator")


async def get_target(update, context):
    message = update.message

    # Reply varsa
    if message.reply_to_message:
        return message.reply_to_message.from_user.id

    # Arg varsa
    if context.args:
        arg = context.args[0]

        if arg.isdigit():
            return int(arg)

        if arg.startswith("@"):
            try:
                member = await update.effective_chat.get_member(arg)
                return member.user.id
            except:
                return None

    return None


def has_link(message):
    if message.entities:
        for e in message.entities:
            if e.type in ["url", "text_link"]:
                return True

    if message.text:
        if re.search(r"(https?://|t\.me|www\.)", message.text.lower()):
            return True

    return False


def is_flood(chat_id, user_id):
    now = time.time()
    flood[chat_id][user_id] = [
        t for t in flood[chat_id][user_id] if now - t < FLOOD_TIME
    ]
    flood[chat_id][user_id].append(now)
    return len(flood[chat_id][user_id]) > FLOOD_LIMIT


def action_buttons(user_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚠️ Warn", callback_data=f"warn:{user_id}"),
            InlineKeyboardButton("🔇 Mute", callback_data=f"mute:{user_id}"),
            InlineKeyboardButton("⛔ Ban", callback_data=f"ban:{user_id}")
        ],
        [
            InlineKeyboardButton("👮 Panel", callback_data=f"panel:{user_id}")
        ]
    ])


def admin_panel(user_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚠️ Warn", callback_data=f"warn:{user_id}"),
            InlineKeyboardButton("➖ Unwarn", callback_data=f"unwarn:{user_id}")
        ],
        [
            InlineKeyboardButton("🔇 Mute", callback_data=f"mute:{user_id}"),
            InlineKeyboardButton("🔊 Unmute", callback_data=f"unmute:{user_id}")
        ],
        [
            InlineKeyboardButton("⛔ Ban", callback_data=f"ban:{user_id}"),
            InlineKeyboardButton("✅ Unban", callback_data=f"unban:{user_id}")
        ],
        [
            InlineKeyboardButton("♻️ Reset", callback_data=f"reset:{user_id}")
        ]
    ])

# ================= CORE =================

async def warn_user(update, context, user_id):
    if await is_admin(update, user_id):
        return "❌ Adminlere warn atamazsın"

    chat = update.effective_chat.id
    warns[chat][user_id] += 1
    count = warns[chat][user_id]

    if count >= MAX_WARN:
        warns[chat][user_id] = 0
        await mute_user(update, context, user_id)
        return "🔇 3 warn → mute"

    return f"⚠️ Warn {count}/{MAX_WARN}"


async def mute_user(update, context, user_id):
    if await is_admin(update, user_id):
        return "❌ Admin susturulamaz"

    until = datetime.now() + timedelta(seconds=MUTE_TIME)

    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        user_id,
        ChatPermissions(can_send_messages=False),
        until_date=until
    )
    return "🔇 Mute atıldı"


async def unmute_user(update, context, user_id):
    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        user_id,
        ChatPermissions(can_send_messages=True)
    )
    return "🔊 Unmute"


async def ban_user(update, context, user_id):
    if await is_admin(update, user_id):
        return "❌ Adminleri banlayamazsın"

    await context.bot.ban_chat_member(update.effective_chat.id, user_id)
    return "⛔ Banlandı"


async def unban_user(update, context, user_id):
    await context.bot.unban_chat_member(update.effective_chat.id, user_id)
    return "✅ Ban kaldırıldı"


async def unwarn(update, context, user_id):
    chat = update.effective_chat.id
    warns[chat][user_id] = max(0, warns[chat][user_id] - 1)
    return "➖ Warn azaltıldı"


async def reset_warn(update, context, user_id):
    chat = update.effective_chat.id
    warns[chat][user_id] = 0
    return "♻️ Warn sıfırlandı"

# ================= COMMANDS =================

async def warn_cmd(update, context):
    user_id = await get_target(update, context)
    if not user_id:
        return await update.message.reply_text("❌ Kullanıcı bulunamadı")

    msg = await warn_user(update, context, user_id)
    await update.message.reply_text(msg)


async def mute_cmd(update, context):
    user_id = await get_target(update, context)
    if not user_id:
        return await update.message.reply_text("❌ Kullanıcı bulunamadı")

    msg = await mute_user(update, context, user_id)
    await update.message.reply_text(msg)


async def unmute_cmd(update, context):
    user_id = await get_target(update, context)
    if not user_id:
        return await update.message.reply_text("❌ Kullanıcı bulunamadı")

    msg = await unmute_user(update, context, user_id)
    await update.message.reply_text(msg)


async def ban_cmd(update, context):
    user_id = await get_target(update, context)
    if not user_id:
        return await update.message.reply_text("❌ Kullanıcı bulunamadı")

    msg = await ban_user(update, context, user_id)
    await update.message.reply_text(msg)


async def unban_cmd(update, context):
    user_id = await get_target(update, context)
    if not user_id:
        return await update.message.reply_text("❌ Kullanıcı bulunamadı")

    msg = await unban_user(update, context, user_id)
    await update.message.reply_text(msg)


async def panel_cmd(update, context):
    if not await is_admin(update, update.effective_user.id):
        return await update.message.reply_text("❌ Yetkin yok")

    user_id = await get_target(update, context)
    if not user_id:
        return await update.message.reply_text("❌ Kullanıcı bulunamadı")

    await update.message.reply_text(
        "👮 Admin Panel",
        reply_markup=admin_panel(user_id)
    )

# ================= BUTTON =================

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()

    action, user_id = query.data.split(":")
    user_id = int(user_id)

    member = await query.message.chat.get_member(query.from_user.id)
    if member.status not in ("administrator", "creator"):
        return await query.answer("❌ Bu işlem sana göre değil", show_alert=True)

    fake_update = Update(update.update_id, message=query.message)

    if action == "panel":
        return await query.edit_message_text("👮 Panel", reply_markup=admin_panel(user_id))

    if action == "warn":
        msg = await warn_user(fake_update, context, user_id)
    elif action == "mute":
        msg = await mute_user(fake_update, context, user_id)
    elif action == "unmute":
        msg = await unmute_user(fake_update, context, user_id)
    elif action == "ban":
        msg = await ban_user(fake_update, context, user_id)
    elif action == "unban":
        msg = await unban_user(fake_update, context, user_id)
    elif action == "unwarn":
        msg = await unwarn(fake_update, context, user_id)
    elif action == "reset":
        msg = await reset_warn(fake_update, context, user_id)

    await query.edit_message_text(msg)

# ================= AUTO =================

async def message_handler(update, context):
    if not update.message:
        return

    user = update.effective_user
    chat = update.effective_chat.id

    if await is_admin(update, user.id):
        return

    if is_flood(chat, user.id):
        await mute_user(update, context, user.id)
        return

    if has_link(update.message):
        try:
            await update.message.delete()
        except:
            pass

        await update.message.reply_text(
            f"🚫 {user.first_name} kural ihlali!",
            reply_markup=action_buttons(user.id)
        )

# ================= MUSIC =================

async def play(update, context):
    if not context.args:
        return await update.message.reply_text("🎧 /play şarkı")

    query = " ".join(context.args)
    msg = await update.message.reply_text("🎧 indiriliyor...")

    try:
        with yt_dlp.YoutubeDL({"format": "bestaudio", "quiet": True}) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=True)
            video = info["entries"][0]
            file = ydl.prepare_filename(video)

        await update.message.reply_audio(audio=open(file, "rb"))
        os.remove(file)
        await msg.delete()

    except:
        await msg.edit_text("❌ indirilemedi")

# ================= MAIN =================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("warn", warn_cmd))
    app.add_handler(CommandHandler("mute", mute_cmd))
    app.add_handler(CommandHandler("unmute", unmute_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("panel", panel_cmd))
    app.add_handler(CommandHandler("play", play))

    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL, message_handler))

    print("Bot aktif 🚀")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
