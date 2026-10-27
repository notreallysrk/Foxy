# wbb/modules/sangmata.py
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatMemberStatus

# WBB ka main app aur DB functions import karein
from wbb import app
from wbb.utils.sangmata_db import (
    is_sangmata_on,
    sangmata_on,
    sangmata_off,
    cek_userdata,
    add_userdata,
    get_userdata
)

__MODULE__ = "Imposter"
__HELP__ = """
/imposter on - Enable Sangmata (Name/Username tracking) in the group.
/imposter off - Disable Sangmata in the group.
/imposter - Show current status and inline buttons to toggle.
"""

# Admin check function
async def is_admin(chat_id: int, user_id: int):
    try:
        member = await app.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        return False

# 1. Background Tracker (Detects Name/Username Changes)
@app.on_message(filters.group & ~filters.bot & ~filters.via_bot, group=5)
async def cek_mataa(_, message: Message):
    if message.sender_chat or not await is_sangmata_on(message.chat.id):
        return

    user = message.from_user
    if not user:
        return

    if not await cek_userdata(user.id):
        return await add_userdata(user.id, user.username, user.first_name, user.last_name)

    uname_old, fname_old, lname_old = await get_userdata(user.id)
    msg = ""
    has_change = False

    if uname_old != user.username:
        has_change = True
        uname_old_fmt = f"@{uname_old}" if uname_old else "None"
        uname_new_fmt = f"@{user.username}" if user.username else "None"
        msg += f"👤 <b>Username changed:</b>\n<b>Before:</b> <code>{uname_old_fmt}</code>\n<b>After:</b> <code>{uname_new_fmt}</code>\n\n"

    if fname_old != user.first_name:
        has_change = True
        msg += f"📝 <b>First Name changed:</b>\n<b>Before:</b> <code>{fname_old}</code>\n<b>After:</b> <code>{user.first_name}</code>\n\n"

    lname_old_fmt = lname_old or "None"
    lname_new_fmt = user.last_name or "None"
    if lname_old != user.last_name:
        has_change = True
        msg += f"📝 <b>Last Name changed:</b>\n<b>Before:</b> <code>{lname_old_fmt}</code>\n<b>After:</b> <code>{lname_new_fmt}</code>\n\n"

    if has_change:
        header = f"🚨 <b>Imposter Alert!</b>\n👤 User: {user.mention} [<code>{user.id}</code>]\n\n"
        await message.reply_text(header + msg, quote=True)
        await add_userdata(user.id, user.username, user.first_name, user.last_name)

# 2. Command to Enable/Disable Sangmata (/imposter)
@app.on_message(filters.group & filters.command("imposter"))
async def set_mataa(_, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("❌ Aapko yeh command use karne ke liye admin hona zaroori hai.")

    if len(message.command) == 1:
        is_enabled = await is_sangmata_on(message.chat.id)
        status = "✅ ON" if is_enabled else "❌ OFF"
        return await message.reply_text(
            f"👁‍🗨 <b>Sangmata Detection Status:</b> <code>{status}</code>\n\nIse ON ya OFF karne ke liye niche diye gaye buttons ka use karein.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Enable", callback_data=f"sangmata:on:{message.chat.id}"),
                InlineKeyboardButton("❌ Disable", callback_data=f"sangmata:off:{message.chat.id}")
            ]])
        )

    choice = message.command[1].lower()
    if choice == "on":
        if await is_sangmata_on(message.chat.id):
            await message.reply_text("⚠️ Sangmata is group mein pehle se ON hai.")
        else:
            await sangmata_on(message.chat.id)
            await message.reply_text("✅ Sangmata Tracking ON kar di gayi hai.")
    elif choice == "off":
        if not await is_sangmata_on(message.chat.id):
            await message.reply_text("⚠️ Sangmata is group mein pehle se OFF hai.")
        else:
            await sangmata_off(message.chat.id)
            await message.reply_text("❌ Sangmata Tracking OFF kar di gayi hai.")

# 3. Callback handler for inline buttons
@app.on_callback_query(filters.regex(r"^sangmata:(on|off):"))
async def handle_sangmata_toggle(_, query: CallbackQuery):
    action, _, chat_id = query.data.split(":")
    chat_id = int(chat_id)

    if not await is_admin(chat_id, query.from_user.id):
        return await query.answer("❌ Aap admin nahi hain!", show_alert=True)

    if action == "on":
        if await is_sangmata_on(chat_id):
            await query.answer("Pehle se ON hai!", show_alert=True)
        else:
            await sangmata_on(chat_id)
            await query.message.edit_text("✅ Sangmata Tracking ON kar di gayi hai.")
            await query.answer("Enabled!")
    elif action == "off":
        if not await is_sangmata_on(chat_id):
            await query.answer("Pehle se OFF hai!", show_alert=True)
        else:
            await sangmata_off(chat_id)
            await query.message.edit_text("❌ Sangmata Tracking OFF kar di gayi hai.")
            await query.answer("Disabled!")
