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

import asyncio
import logging
import os
from collections import OrderedDict

from aiohttp import ClientSession, ClientTimeout
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
from wbb.utils.dbfunctions import (
    add_chatbot,
    check_chatbot,
    rm_chatbot,
)
from wbb.utils.filter_groups import chatbot_group


__MODULE__ = "ChatBot"

__HELP__ = """
/chatbot [ENABLE|DISABLE] - Enable or disable Foxy AI in groups.

In private chat, simply send Foxy a message.
"""


LOGGER = logging.getLogger(__name__)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")


PERSONALITY = (
    "You are Foxy, a cute, sweet, playful and caring girl "
    "AI assistant in a Telegram chat. "
    "Speak naturally in the user's language, including "
    "Hindi, Hinglish and English. "
    "Be friendly, witty, helpful and a little playful. "
    "Keep replies conversational and usually concise. "
    "Never claim to be human."
)


# Temporary conversation memory
_HISTORY = OrderedDict()
_HISTORY_LIMIT = 500


def _history_key(message: Message):
    return (
        message.chat.id,
        message.from_user.id if message.from_user else 0,
    )


async def gemini_reply(message: Message):

    if not GEMINI_KEY:
        return (
            "🦊 Foxy AI is not configured yet. "
            "Please ask the owner to set GEMINI_API_KEY."
        )

    query = (message.text or "").strip()

    if not query:
        return None

    key = _history_key(message)

    history = _HISTORY.get(key, [])

    contents = history + [
        {
            "role": "user",
            "parts": [{"text": query}],
        }
    ]

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{GEMINI_MODEL}:generateContent"
    )

    payload = {
        "systemInstruction": {
            "parts": [{"text": PERSONALITY}]
        },
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": 500,
            "temperature": 0.85,
        },
    }

    try:

        async with ClientSession(
            timeout=ClientTimeout(total=45)
        ) as session:

            async with session.post(
                url,
                params={"key": GEMINI_KEY},
                json=payload,
            ) as response:

                data = await response.json(
                    content_type=None
                )

                if response.status != 200:

                    LOGGER.warning(
                        "Gemini API error: HTTP %s",
                        response.status,
                    )

                    if response.status == 429:
                        return (
                            "🦊 I'm getting too many messages "
                            "right now. Please try again "
                            "in a bit! 💕"
                        )

                    return (
                        "🦊 My AI is having trouble right "
                        "now. Please try again later! 💗"
                    )

        candidates = data.get("candidates", [])

        parts = (
            candidates[0]
            .get("content", {})
            .get("parts", [])
            if candidates
            else []
        )

        answer = "".join(
            p.get("text", "")
            for p in parts
            if isinstance(p, dict)
        ).strip()

        if not answer:
            return (
                "🦊 I couldn't think of a reply "
                "this time. Try asking differently! 💕"
            )

        _HISTORY[key] = (
            contents
            + [
                {
                    "role": "model",
                    "parts": [{"text": answer}],
                }
            ]
        )[-12:]

        _HISTORY.move_to_end(key)

        while len(_HISTORY) > _HISTORY_LIMIT:
            _HISTORY.popitem(last=False)

        return answer

    except Exception:

        LOGGER.exception("Gemini request failed")

        return (
            "🦊 Oops! I can't connect to my AI "
            "right now. Try again soon! 💗"
        )


async def chat_bot_toggle(
    message: Message,
    is_userbot: bool,
):

    status = message.text.split(None, 1)[1].lower()

    chat_id = message.chat.id

    db = await check_chatbot()

    enabled = (
        db["userbot"]
        if is_userbot
        else db["bot"]
    )

    if status == "enable":

        if chat_id not in enabled:

            await add_chatbot(
                chat_id,
                is_userbot=is_userbot,
            )

            return await eor(
                message,
                text="Chatbot Enabled!",
            )

        return await eor(
            message,
            text="ChatBot Is Already Enabled.",
        )

    if status == "disable":

        if chat_id in enabled:

            await rm_chatbot(
                chat_id,
                is_userbot=is_userbot,
            )

            return await eor(
                message,
                text="Chatbot Disabled!",
            )

        return await eor(
            message,
            text="ChatBot Is Already Disabled.",
        )

    return await eor(
        message,
        text="**Usage:**\n/chatbot [ENABLE|DISABLE]",
    )


@app.on_message(filters.command("chatbot"))
@capture_err
async def chatbot_status(_, message: Message):

    if len(message.command) != 2:

        return await eor(
            message,
            text="**Usage:**\n/chatbot [ENABLE|DISABLE]",
        )

    await chat_bot_toggle(
        message,
        is_userbot=False,
    )


async def send_gemini(message: Message):

    await message._client.send_chat_action(
        message.chat.id,
        enums.ChatAction.TYPING,
    )

    try:

        answer = await gemini_reply(message)

        if answer:

            for start in range(0, len(answer), 4000):

                await message.reply_text(
                    answer[start:start + 4000],
                    parse_mode=enums.ParseMode.DISABLED,
                )

    finally:

        await message._client.send_chat_action(
            message.chat.id,
            enums.ChatAction.CANCEL,
        )


# Gemini AI in groups
@app.on_message(
    filters.group
    & filters.text
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

    if (
        not message.reply_to_message
        or not message.reply_to_message.from_user
    ):
        return

    if (
        message.reply_to_message.from_user.id
        != BOT_ID
    ):
        return

    await send_gemini(message)


# Gemini AI in private messages
@app.on_message(
    filters.private
    & filters.text
    & ~filters.bot
    & ~filters.command(
        ["start", "help", "chatbot"]
    ),
    group=chatbot_group,
)
@capture_err
async def chatbot_private(_, message: Message):

    if (message.text or "").startswith("/"):
        return

    await send_gemini(message)


# Existing userbot ChatBot (ARQ)
async def type_and_send(message: Message):

    chat_id = message.chat.id

    user_id = (
        message.from_user.id
        if message.from_user
        else 0
    )

    query = message.text.strip()

    await message._client.send_chat_action(
        chat_id,
        enums.ChatAction.TYPING,
    )

    try:

        luna = await arq.luna(
            query,
            user_id,
        )

        response = luna.result

        await message.reply_text(response)

    finally:

        await message._client.send_chat_action(
            chat_id,
            enums.ChatAction.CANCEL,
        )


@app2.on_message(
    filters.command(
        "chatbot",
        prefixes=USERBOT_PREFIX,
    )
    & SUDOERS
    & ~filters.forwarded
    & ~filters.via_bot
)
@capture_err
async def chatbot_status_ubot(_, message: Message):

    if len(message.text.split()) != 2:

        return await eor(
            message,
            text=(
                f"**Usage:**\n"
                f"{USERBOT_PREFIX}chatbot "
                "[ENABLE|DISABLE]"
            ),
        )

    await chat_bot_toggle(
        message,
        is_userbot=True,
    )


@app2.on_message(
    ~filters.me
    & ~filters.private
    & filters.text,
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
            message.reply_to_message.from_user.id
            != USERBOT_ID
            and username not in message.text
        ):
            return

    elif username not in message.text:
        return

    await type_and_send(message)


@app2.on_message(
    filters.text
    & filters.private
    & ~filters.me,
    group=(chatbot_group + 1),
)
@capture_err
async def chatbot_talk_ubot_pm(_, message: Message):

    db = await check_chatbot()

    if message.chat.id not in db["userbot"]:
        return

    await type_and_send(message)
