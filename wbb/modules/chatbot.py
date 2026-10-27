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
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
"""

import asyncio
import logging
import os
import time
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
/chatbot [ENABLE|DISABLE] - Enable or disable the group ChatBot.

Private chat:
Send Foxy a message to talk with Gemini AI.

The userbot ChatBot continues using ARQ Luna.
"""

LOGGER = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash-lite",
).strip()

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/"
    f"v1beta/models/{GEMINI_MODEL}:generateContent"
)

PERSONALITY = """
You are Foxy, a cute, sweet, caring and playful AI girl
who chats with people on Telegram.

IMPORTANT CONVERSATION RULES:

1. Talk naturally, like a friendly chat partner.
2. Usually reply in ONE short sentence.
3. Use at most TWO short sentences unless details are requested.
4. Keep normal chat replies around 5-25 words.
5. Never write long paragraphs for simple messages.
6. Understand the user's latest message in context.
7. If the user says "Ek baat batao", reply naturally:
   "Haan ji, poocho na 🥰"
8. If the user says "Aap batao mujhe ek baat",
   respond naturally, for example:
   "Haan bolo, kya jaan'na hai? 💗"
9. If the user asks "Kaisi ho?", answer briefly and ask
   how they are only when it feels natural.
10. Speak Hindi or Hinglish when the user does.
11. Speak English when the user speaks English.
12. Be cute, warm, playful and lightly teasing.
13. Do not overact or add unnecessary dramatic reactions.
14. Use emojis sparingly, usually zero or one.
15. Do not repeatedly ask "What's on your mind?"
16. Do not repeat the same greeting or question unnecessarily.
17. Answer direct questions directly.
18. Give detailed answers only when the user requests details.
19. Do not invent personal experiences or claim to be human.
20. Follow the ongoing conversation instead of changing topics.
"""

# Temporary conversation memory.
# Memory is separate for each chat and user.
_HISTORY = OrderedDict()
_HISTORY_LIMIT = 500
_MAX_HISTORY_MESSAGES = 6
_MAX_OUTPUT_TOKENS = 96

# Reuse the HTTP connection between messages to avoid a new TLS handshake
# for every Gemini request.
_GEMINI_SESSION = None


def _history_key(message: Message):
    user_id = message.from_user.id if message.from_user else 0
    return message.chat.id, user_id


async def gemini_reply(message: Message):
    """Generate a short, contextual reply using Gemini."""

    if not GEMINI_API_KEY:
        LOGGER.error("GEMINI_API_KEY is not configured.")
        return (
            "🦊 Oops! My AI isn't configured yet. "
            "Please tell the owner. 💗"
        )

    query = (message.text or "").strip()

    if not query:
        return None

    key = _history_key(message)
    history = _HISTORY.get(key, [])

    # Gemini conversation roles must alternate between user and model.
    contents = history + [
        {
            "role": "user",
            "parts": [{"text": query}],
        }
    ]

    payload = {
        "systemInstruction": {
            "parts": [{"text": PERSONALITY}],
        },
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": _MAX_OUTPUT_TOKENS,
            "temperature": 0.65,
        },
    }

    try:
        global _GEMINI_SESSION
        if _GEMINI_SESSION is None or _GEMINI_SESSION.closed:
            timeout = ClientTimeout(total=45, connect=10, sock_read=35)
            _GEMINI_SESSION = ClientSession(timeout=timeout)

        request_started = time.perf_counter()
        async with _GEMINI_SESSION.post(
            GEMINI_API_URL,
            params={"key": GEMINI_API_KEY},
            json=payload,
        ) as response:
            data = await response.json(content_type=None)
            elapsed = time.perf_counter() - request_started
            LOGGER.info(
                "Gemini API response completed in %.2f seconds (HTTP %s, model=%s).",
                elapsed,
                response.status,
                GEMINI_MODEL,
            )

            if response.status != 200:
                # Do not log the API key or request URL.
                api_error = data.get("error", {})
                error_message = api_error.get(
                    "message",
                    "No error details provided",
                )

                LOGGER.error(
                    "Gemini API returned HTTP %s: %s",
                    response.status,
                    error_message[:300],
                )

                if response.status == 429:
                    return (
                        "Aww, thoda busy hoon abhi! 🥹 "
                        "Ek minute baad try karo. 💗"
                    )

                if response.status == 404:
                    LOGGER.error(
                        "Gemini model/endpoint not found. "
                        "Check GEMINI_MODEL in Heroku Config Vars."
                    )
                    return (
                        "Meri AI setting mein kuch problem hai. "
                        "Owner ko model setting check karni hogi. 🦊"
                    )

                return (
                    "Aww, meri AI abhi reply nahi kar paa rahi. "
                    "Thodi der baad try karo. 💗"
                )

        candidates = data.get("candidates", [])

        if not candidates:
            LOGGER.warning("Gemini returned no candidates.")
            return "Aww, abhi mere paas jawab nahi hai. 🥹"

        candidate = candidates[0]
        content = candidate.get("content") or {}
        parts = content.get("parts") or []

        answer = " ".join(
            part.get("text", "").strip()
            for part in parts
            if isinstance(part, dict) and part.get("text")
        ).strip()

        if not answer:
            LOGGER.warning(
                "Gemini returned no text. Finish reason: %s",
                candidate.get("finishReason", "unknown"),
            )
            return (
                "Aww, samajh nahi aaya kya bolun. "
                "Ek baar phir se poocho na. 🦊"
            )

        # Save the latest user/model messages for contextual replies.
        updated_history = contents + [
            {
                "role": "model",
                "parts": [{"text": answer}],
            }
        ]

        _HISTORY[key] = updated_history[-_MAX_HISTORY_MESSAGES:]
        _HISTORY.move_to_end(key)

        while len(_HISTORY) > _HISTORY_LIMIT:
            _HISTORY.popitem(last=False)

        return answer

    except asyncio.TimeoutError:
        LOGGER.warning(
            "Gemini request timed out after 45 seconds (model=%s).",
            GEMINI_MODEL,
        )
        return (
            "Aww, reply aane mein zyada time lag gaya. "
            "Ek baar phir try karo na. 💗"
        )
    except Exception:
        LOGGER.exception("Gemini request failed (model=%s).", GEMINI_MODEL)
        return (
            "Aww, connection mein problem aa gayi. "
            "Thodi der mein phir baat karte hain. 💗"
        )


async def chat_bot_toggle(
    message: Message,
    is_userbot: bool,
):
    status = message.text.split(None, 1)[1].lower()
    chat_id = message.chat.id

    db = await check_chatbot()
    enabled_chats = db["userbot"] if is_userbot else db["bot"]

    if status == "enable":
        if chat_id not in enabled_chats:
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
        if chat_id in enabled_chats:
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
    """Show typing status and send Gemini's response."""

    await message._client.send_chat_action(
        message.chat.id,
        enums.ChatAction.TYPING,
    )

    try:
        answer = await gemini_reply(message)

        if not answer:
            return

        # Telegram messages have a maximum length of 4096 characters.
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


# ---------------------------------------------------------
# Gemini ChatBot: enabled groups
# ---------------------------------------------------------

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

    replied_message = message.reply_to_message

    if not replied_message or not replied_message.from_user:
        return

    if replied_message.from_user.id != BOT_ID:
        return

    await send_gemini(message)


# ---------------------------------------------------------
# Gemini ChatBot: private messages
# ---------------------------------------------------------

@app.on_message(
    filters.private
    & filters.text
    & ~filters.bot
    & ~filters.command(["start", "help", "chatbot"]),
    group=chatbot_group,
)
@capture_err
async def chatbot_private(_, message: Message):
    # Do not treat other bot commands as normal conversation.
    if (message.text or "").startswith("/"):
        return

    await send_gemini(message)


# ---------------------------------------------------------
# Existing userbot ChatBot: ARQ Luna
# ---------------------------------------------------------

async def type_and_send(message: Message):
    chat_id = message.chat.id

    user_id = (
        message.from_user.id
        if message.from_user
        else 0
    )

    query = (message.text or "").strip()

    if not query:
        return

    await message._client.send_chat_action(
        chat_id,
        enums.ChatAction.TYPING,
    )

    try:
        luna = await arq.luna(query, user_id)
        response = getattr(luna, "result", None)

        if not response:
            response = (
                "Sorry, the AI service couldn't generate "
                "a reply right now. Please try again later."
            )

        await message.reply_text(str(response))

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
    & ~filters.via_bot,
)
@capture_err
async def chatbot_status_ubot(_, message: Message):
    if len(message.text.split()) != 2:
        return await eor(
            message,
            text=(
                f"**Usage:**\n"
                f"{USERBOT_PREFIX}chatbot [ENABLE|DISABLE]"
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
            message.reply_to_message.from_user.id != USERBOT_ID
            and username.lower() not in message.text.lower()
        ):
            return

    elif username.lower() not in message.text.lower():
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
