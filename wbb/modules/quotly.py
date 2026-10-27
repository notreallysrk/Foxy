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
from io import BytesIO

from pyrogram import filters
from pyrogram.types import Message

from wbb import SUDOERS, USERBOT_PREFIX, app, app2, arq
from wbb.core.decorators.errors import capture_err

__MODULE__ = "Quotly"

LOGGER = logging.getLogger(__name__)

__HELP__ = """
/q - To quote a message.
/q [INTEGER] - To quote more than 1 messages.
/q r - To quote a message with its reply.

Use .q to quote using userbot.
"""


async def quotify(messages: list):
    """Convert messages into a Quotly sticker."""
    response = await arq.quotly(messages)

    if not response.ok:
        LOGGER.error("Quotly API returned an error: %s", response.result)
        return [
            False,
            response.result or "Quotly service could not create the quote.",
        ]

    sticker = response.result

    if not isinstance(sticker, (bytes, bytearray)) or not sticker:
        LOGGER.error(
            "Quotly API returned an invalid sticker payload: %s",
            type(sticker).__name__,
        )
        return [
            False,
            "Quotly service returned an invalid sticker. Please try again later.",
        ]

    sticker_file = BytesIO(sticker)
    sticker_file.name = "sticker.webp"

    return [True, sticker_file]


def getArg(message: Message) -> str:
    """Get the command argument safely."""
    parts = (message.text or "").strip().split(None, 1)

    if len(parts) < 2:
        return ""

    return parts[1].strip()


def isArgInt(message: Message) -> list:
    """Check whether the command argument is an integer."""
    try:
        return [True, int(getArg(message))]
    except (ValueError, TypeError):
        return [False, 0]


@app2.on_message(
    filters.command("q", prefixes=USERBOT_PREFIX)
    & ~filters.forwarded
    & ~filters.via_bot
    & SUDOERS
)
@app.on_message(filters.command("q") & ~filters.private)
@capture_err
async def quotly_func(client, message: Message):
    """Create a quote sticker from a replied-to message."""

    target = message.reply_to_message

    if not target:
        return await message.reply_text(
            "Reply to a message to quote it."
        )

    target_text = target.text or target.caption

    if not target_text:
        return await message.reply_text(
            "Replied message has no text or caption, so it can't be quoted."
        )

    status_message = await message.reply_text("Quoting Messages")

    try:
        if len(message.command) < 2:
            messages = [target]

        elif len(message.command) == 2:
            argument = isArgInt(message)

            if argument[0]:
                count = argument[1]

                if count < 2 or count > 10:
                    return await status_message.edit(
                        "Argument must be between 2-10."
                    )

                # Fetch extra messages so media messages can be skipped.
                fetched_messages = await client.get_messages(
                    message.chat.id,
                    range(target.id, target.id + count + 5),
                    replies=0,
                )

                messages = [
                    item
                    for item in fetched_messages
                    if not item.empty
                    and (item.text or item.caption)
                ][:count]

                if not messages:
                    return await status_message.edit(
                        "No suitable text messages were found to quote."
                    )

            else:
                if getArg(message).lower() != "r":
                    return await status_message.edit(
                        "Incorrect argument. Use **/q**, **/q 2**, "
                        "or **/q r** while replying to a message."
                    )

                reply_message = await client.get_messages(
                    message.chat.id,
                    target.id,
                    replies=1,
                )

                if not reply_message or reply_message.empty:
                    return await status_message.edit(
                        "Couldn't find the replied message to quote."
                    )

                if not (reply_message.text or reply_message.caption):
                    return await status_message.edit(
                        "The replied message has no text or caption."
                    )

                messages = [reply_message]

        else:
            return await status_message.edit(
                "Incorrect argument. Check the Quotly command in help."
            )

        sticker_result = await quotify(messages)

        if not sticker_result[0]:
            return await status_message.edit(
                f"Couldn't create quote: {sticker_result[1]}"
            )

        sticker_file = sticker_result[1]

        try:
            await message.reply_sticker(sticker_file)
        finally:
            sticker_file.close()

        await status_message.delete()

    except Exception:
        LOGGER.exception(
            "Quotly failed (chat_id=%s, command=%r, target_message_id=%s)",
            message.chat.id,
            message.text or message.caption,
            target.id if target else None,
        )

        try:
            await status_message.edit(
                "Quote nahi ban paaya. Please dobara try karo. "
                "Agar issue repeat ho, owner logs check kare."
            )
        except Exception:
            LOGGER.exception(
                "Failed to edit the Quotly status message."
            )
