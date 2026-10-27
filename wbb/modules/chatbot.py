"""
MIT License

Copyright (c) 2024 TheHamkerCat

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import logging
from asyncio import gather, sleep

from pyrogram import enums, filters
from pyrogram.types import Message

from wbb import (
    BOT_ID,
    SUDOERS,
    USERBOT_ID,
    USERBOT_PREFIX,
    USERBOT_USERNAME,
    app,
    app2,
    arq,
    eor,
)
from wbb.core.decorators.errors import capture_err
from wbb.utils.dbfunctions import add_chatbot, check_chatbot, rm_chatbot
from wbb.utils.filter_groups import chatbot_group

logger = logging.getLogger(__name__)

__MODULE__ = "ChatBot"
__HELP__ = """
/chatbot [ENABLE|DISABLE] To Enable Or Disable ChatBot In Your Chat.

There's one module of this available for userbot also
check userbot module help."""


async def chat_bot_toggle(message: Message, is_userbot: bool):
    status = message.text.split(None, 1)[1].lower()
    chat_id = message.chat.id
    db = await check_chatbot()
    db = db["userbot"] if is_userbot else db["bot"]
    if status == "enable":
        if chat_id not in db:
            await add_chatbot(chat_id, is_userbot=is_userbot)
            text = "Chatbot Enabled!"
            return await eor(message, text=text)
        await eor(message, text="ChatBot Is Already Enabled.")
    elif status == "disable":
        if chat_id in db:
            await rm_chatbot(chat_id, is_userbot=is_userbot)
            return await eor(message, text="Chatbot Disabled!")
        await eor(message, text="ChatBot Is Already Disabled.")
    else:
        await eor(message, text="**Usage:**\n/chatbot [ENABLE|DISABLE]")


@app.on_message(filters.command("chatbot"))
@capture_err
async def chatbot_status(_, message: Message):
    if len(message.command) != 2:
        return await eor(message, text="**Usage:**\n/chatbot [ENABLE|DISABLE]")
    await chat_bot_toggle(message, is_userbot=False)


async def lunaQuery(query: str, user_id: int):
    luna = await arq.luna(query, user_id)
    result = getattr(luna, "result", None)
    if not isinstance(result, str) or not result.strip():
        logger.error("ARQ Luna returned an empty or invalid result: %r", result)
        return None
    if result.strip().lower() == "something went wrong.":
        logger.error("ARQ Luna returned its generic error response for user_id=%s", user_id)
        return None
    return result


async def type_and_send(message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    query = (message.text or "").strip()
    if not query:
        return
    client = message._client
    try:
        await client.send_chat_action(chat_id, enums.ChatAction.TYPING)
        response, _ = await gather(lunaQuery(query, user_id), sleep(3))
        if response is None:
            await message.reply_text("Sorry, the AI service couldn't generate a reply right now. Please try again later.")
        else:
            await message.reply_text(response)
    except Exception:
        logger.exception("Foxy chatbot Luna request failed (chat_id=%s)", chat_id)
        await message.reply_text("Sorry, the AI service is temporarily unavailable. Please try again later.")
    finally:
        try:
            await client.send_chat_action(chat_id, enums.ChatAction.CANCEL)
        except Exception:
            logger.debug("Could not cancel chatbot typing action", exc_info=True)


@app.on_message(
    filters.text
    & filters.reply
    & ~filters.bot
    & ~filters.via_bot
    & ~filters.forwarded,
    group=chatbot_group,
)
@capture_err
async def chatbot_talk(_, message: Message):
    db = await check_chatbot()
    if message.chat.id not in db["bot"]:
        return
    if not message.reply_to_message:
        return
    if not message.reply_to_message.from_user:
        return
    if message.reply_to_message.from_user.id != BOT_ID:
        return
    await type_and_send(message)


@app2.on_message(
    filters.command("chatbot", prefixes=USERBOT_PREFIX)
    & SUDOERS
    & ~filters.forwarded
    & ~filters.via_bot
)
@capture_err
async def chatbot_status_ubot(_, message: Message):
    if len(message.text.split()) != 2:
        return await eor(
            message,
            text=f"**Usage:**\n{USERBOT_PREFIX}chatbot [ENABLE|DISABLE]",
        )
    await chat_bot_toggle(message, is_userbot=True)


@app2.on_message(
    ~filters.me & ~filters.private & filters.text,
    group=chatbot_group,
)
@capture_err
async def chatbot_talk_ubot(_, message: Message):
    db = await check_chatbot()
    if message.chat.id not in db["userbot"]:
        return
    username = "@" + str(USERBOT_USERNAME)
    if message.reply_to_message:
        if not message.reply_to_message.from_user:
            return
        if (
            message.reply_to_message.from_user.id != USERBOT_ID
            and username not in message.text
        ):
            return
    else:
        if username not in message.text:
            return
    await type_and_send(message)


@app2.on_message(
    filters.text & filters.private & ~filters.me,
    group=(chatbot_group + 1),
)
@capture_err
async def chatbot_talk_ubot_pm(_, message: Message):
    db = await check_chatbot()
    if message.chat.id not in db["userbot"]:
        return
    await type_and_send(message)
