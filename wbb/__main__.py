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
import importlib
import re
from contextlib import closing, suppress

from pyrogram import filters, idle
from pyrogram.enums import ChatType, ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from uvloop import install

from wbb import (
    BOT_NAME,
    BOT_TOKEN,
    BOT_USERNAME,
    LOG_GROUP_ID,
    USERBOT_NAME,
    aiohttpsession,
    app,
    log,
)
from wbb.core.keyboard import ikb
import aiohttp
import logging
from wbb.modules import ALL_MODULES
from wbb.modules.sudoers import bot_sys_stats
from wbb.utils import paginate_modules
from wbb.utils.constants import MARKDOWN
from wbb.utils.dbfunctions import clean_restart_stage, get_rules
from wbb.utils.functions import extract_text_and_keyb

"""Native Telegram Bot API coloured keyboards, sent in a single request."""


def styled_keyboard(markup, mode):
    rows = []
    for row in markup.inline_keyboard:
        output = []
        for button in row:
            item = {"text": button.text}
            for field in ("url", "callback_data", "switch_inline_query", "switch_inline_query_current_chat"):
                value = getattr(button, field, None)
                if value is not None:
                    item[field] = value
                    break
            else:
                return None  # Avoid altering buttons with unsupported actions.
            if mode == "start":
                name = button.text.lower()
                item["style"] = ("success" if "add me" in name else "danger" if "repo" in name else "primary")
            elif mode == "help":
                name = button.text.strip().lower()
                callback = item.get("callback_data", "")
                if "prev(" in callback or name in ("❮", "previous"):
                    item["style"] = "primary"
                elif "next(" in callback or name in ("❯", "next"):
                    item["style"] = "success"
                elif name == "back" or callback == "help_back":
                    item["style"] = "danger"
            output.append(item)
        rows.append(output)
    return {"inline_keyboard": rows}


async def telegram_styled(method, *, markup, mode, **fields):
    """Send/edit styled keyboards in the original Bot API request (no grey flash)."""
    payload = dict(fields)
    payload["reply_markup"] = styled_keyboard(markup, mode)
    if payload["reply_markup"] is None:
        raise ValueError("Unsupported keyboard button action")
    payload.setdefault("parse_mode", "Markdown")
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
            json=payload, timeout=aiohttp.ClientTimeout(total=20),
        ) as response:
            result = await response.json(content_type=None)
    if not result.get("ok"):
        raise RuntimeError(f"Telegram {method}: {result.get('description', 'unknown error')}")
    return result["result"]


async def send_styled_reply(message, text, markup, mode, *, no_preview=False):
    return await telegram_styled(
        "sendMessage", chat_id=message.chat.id, text=text,
        reply_to_message_id=message.id, allow_sending_without_reply=True,
        disable_web_page_preview=no_preview, markup=markup, mode=mode,
    )


async def edit_styled(message, text, markup, mode, *, no_preview=True):
    return await telegram_styled(
        "editMessageText", chat_id=message.chat.id, message_id=message.id,
        text=text, disable_web_page_preview=no_preview,
        markup=markup, mode=mode,
    )


loop = asyncio.get_event_loop()

HELPABLE = {}


async def start_bot():
    global HELPABLE

    for module in ALL_MODULES:
        imported_module = importlib.import_module("wbb.modules." + module)
        if (
            hasattr(imported_module, "__MODULE__")
            and imported_module.__MODULE__
        ):
            imported_module.__MODULE__ = imported_module.__MODULE__
            if (
                hasattr(imported_module, "__HELP__")
                and imported_module.__HELP__
            ):
                HELPABLE[
                    imported_module.__MODULE__.replace(" ", "_").lower()
                ] = imported_module
    bot_modules = ""
    j = 1
    for i in ALL_MODULES:
        if j == 4:
            bot_modules += "|{:<15}|\n".format(i)
            j = 0
        else:
            bot_modules += "|{:<15}".format(i)
        j += 1
    print("+===============================================================+")
    print("|                              WBB                              |")
    print("+===============+===============+===============+===============+")
    print(bot_modules)
    print("+===============+===============+===============+===============+")
    log.info(f"BOT STARTED AS {BOT_NAME}!")
    log.info(f"USERBOT STARTED AS {USERBOT_NAME}!")

    restart_data = await clean_restart_stage()

    try:
        log.info("Sending online status")
        if restart_data:
            await app.edit_message_text(
                restart_data["chat_id"],
                restart_data["message_id"],
                "**Restarted Successfully**",
            )

        else:
            await app.send_message(LOG_GROUP_ID, "Bot started!")
    except Exception:
        pass

    await idle()

    await aiohttpsession.close()
    log.info("Stopping clients")
    await app.stop()
    log.info("Cancelling asyncio tasks")
    for task in asyncio.all_tasks():
        task.cancel()
    log.info("Dead!")


home_keyboard_pm = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(
                text="Commands ❓", callback_data="bot_commands"
            ),
            InlineKeyboardButton(
                text="Repo 🛠",
                url="https://github.com/thehamkercat/WilliamButcherBot",
            ),
        ],
        [
            InlineKeyboardButton(
                text="System Stats 🖥",
                callback_data="stats_callback",
            ),
            InlineKeyboardButton(
                text="Support 👨", url="http://t.me/WBBSupport"
            ),
        ],
        [
            InlineKeyboardButton(
                text="Add Me To Your Group 🎉",
                url=f"http://t.me/{BOT_USERNAME}?startgroup=new",
            )
        ],
    ]
)

home_text_pm = (
    f"Hey there! My name is {BOT_NAME}. I can manage your "
    + "group with lots of useful features, feel free to "
    + "add me to your group."
)

keyboard = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(
                text="Help ❓",
                url=f"t.me/{BOT_USERNAME}?start=help",
            ),
            InlineKeyboardButton(
                text="Repo 🛠",
                url="https://github.com/thehamkercat/WilliamButcherBot",
            ),
        ],
        [
            InlineKeyboardButton(
                text="System Stats 💻",
                callback_data="stats_callback",
            ),
            InlineKeyboardButton(text="Support 👨", url="t.me/WBBSupport"),
        ],
    ]
)


FED_MARKUP = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(
                "Fed Owner Commands", callback_data="fed_owner"
            ),
            InlineKeyboardButton(
                "Fed Admin Commands", callback_data="fed_admin"
            ),
        ],
        [
            InlineKeyboardButton("User Commands", callback_data="fed_user"),
        ],
        [
            InlineKeyboardButton("Back", callback_data="help_back"),
        ],
    ]
)


@app.on_message(filters.command("start"))
async def start(_, message):
    if message.chat.type != ChatType.PRIVATE:
        return await message.reply(
            "Pm Me For More Details.", reply_markup=keyboard
        )
    if len(message.text.split()) > 1:
        user = await app.get_users(message.from_user.id)
        name = (message.text.split(None, 1)[1]).lower()
        match = re.match(r"rules_(.*)", name)
        if match:
            chat_id = match.group(1)
            user_id = message.from_user.id
            chat = await app.get_chat(int(chat_id))
            text = f"**The rules for `{chat.title}` are:\n\n**"
            rules = await get_rules(int(chat_id))
            if rules:
                text = text + rules
                if "{chat}" in text:
                    text = text.replace("{chat}", chat.title)
                if "{name}" in text:
                    text = text.replace("{name}", user.mention)
                keyb = None
                if re.findall(r"\[.+\,.+\]", text):
                    text, keyb = extract_text_and_keyb(ikb, text)
                await app.send_message(user_id, text=text, reply_markup=keyb)
            else:
                return await app.send_message(
                    user_id,
                    "The group admins haven't set any rules for this chat yet. "
                    "This probably doesn't mean it's lawless though...!",
                )
        if name == "mkdwn_help":
            await message.reply(
                MARKDOWN,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        elif "_" in name:
            module = name.split("_", 1)[1]
            text = (
                f"Here is the help for **{HELPABLE[module].__MODULE__}**:\n"
                + HELPABLE[module].__HELP__
            )
            if module == "federation":
                return await message.reply(
                    text=text,
                    reply_markup=FED_MARKUP,
                    disable_web_page_preview=True,
                )
            await send_styled_reply(
                message, text,
                InlineKeyboardMarkup([[InlineKeyboardButton("back", callback_data="help_back")]]),
                "help", no_preview=True,
            )
        elif name == "help":
            text, keyb = await help_parser(message.from_user.first_name)
            await send_styled_reply(message, text, keyb, "help")
    else:
        await send_styled_reply(message, home_text_pm, home_keyboard_pm, "start")
    return


@app.on_message(filters.command("help"))
async def help_command(_, message):
    if message.chat.type != ChatType.PRIVATE:
        if len(message.command) >= 2:
            name = (message.text.split(None, 1)[1]).replace(" ", "_").lower()
            if str(name) in HELPABLE:
                key = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text="Click here",
                                url=f"t.me/{BOT_USERNAME}?start=help_{name}",
                            )
                        ],
                    ]
                )
                await message.reply(
                    f"Click on the below button to get help about {name}",
                    reply_markup=key,
                )
            else:
                await message.reply(
                    "PM Me For More Details.", reply_markup=keyboard
                )
        else:
            await message.reply(
                "Pm Me For More Details.", reply_markup=keyboard
            )
    else:
        if len(message.command) >= 2:
            name = (message.text.split(None, 1)[1]).replace(" ", "_").lower()
            if str(name) in HELPABLE:
                text = (
                    f"Here is the help for **{HELPABLE[name].__MODULE__}**:\n"
                    + HELPABLE[name].__HELP__
                )
                await message.reply(text, disable_web_page_preview=True)
            else:
                text, help_keyboard = await help_parser(
                    message.from_user.first_name
                )
                await send_styled_reply(message, text, help_keyboard, "help", no_preview=True)
        else:
            text, help_keyboard = await help_parser(
                message.from_user.first_name
            )
            await send_styled_reply(message, text, help_keyboard, "help", no_preview=True)
    return


async def help_parser(name, keyboard=None):
    if not keyboard:
        keyboard = InlineKeyboardMarkup(paginate_modules(0, HELPABLE, "help"))
    return (
        """Hello {first_name}, My name is {bot_name}.
I'm a group management bot with some useful features.
You can choose an option below, by clicking a button.
Also you can ask anything in Support Group.
""".format(
            first_name=name,
            bot_name=BOT_NAME,
        ),
        keyboard,
    )


@app.on_callback_query(filters.regex("bot_commands"))
async def commands_callbacc(_, CallbackQuery):
    text, keyboard = await help_parser(CallbackQuery.from_user.mention)
    await app.send_message(
        CallbackQuery.message.chat.id,
        text=text,
        reply_markup=keyboard,
    )

    await CallbackQuery.message.delete()


@app.on_callback_query(filters.regex("stats_callback"))
async def stats_callbacc(_, CallbackQuery):
    text = await bot_sys_stats()
    await app.answer_callback_query(CallbackQuery.id, text, show_alert=True)


@app.on_callback_query(filters.regex(r"help_(.*?)"))
async def help_button(client, query):
    home_match = re.match(r"help_home\((.+?)\)", query.data)
    mod_match = re.match(r"help_module\((.+?)\)", query.data)
    prev_match = re.match(r"help_prev\((.+?)\)", query.data)
    next_match = re.match(r"help_next\((.+?)\)", query.data)
    back_match = re.match(r"help_back", query.data)
    create_match = re.match(r"help_create", query.data)
    top_text = f"""
Hello {query.from_user.first_name}, My name is {BOT_NAME}.
I'm a group management bot with some useful features.
You can choose an option below, by clicking a button.
Also you can ask anything in Support Group.

General command are:
 - /start: Start the bot
 - /help: Give this message
 """
    if mod_match:
        module = (mod_match.group(1)).replace(" ", "_")
        text = (
            "{} **{}**:\n".format(
                "Here is the help for", HELPABLE[module].__MODULE__
            )
            + HELPABLE[module].__HELP__
        )
        if module == "federation":
            return await query.message.edit(
                text=text,
                reply_markup=FED_MARKUP,
                disable_web_page_preview=True,
            )
        await edit_styled(
            query.message, text,
            InlineKeyboardMarkup([[InlineKeyboardButton("back", callback_data="help_back")]]),
            "help",
        )
    elif home_match:
        await telegram_styled("sendMessage", chat_id=query.from_user.id, text=home_text_pm, markup=home_keyboard_pm, mode="start")
        await query.message.delete()
    elif prev_match:
        curr_page = int(prev_match.group(1))
        nav_markup = InlineKeyboardMarkup(paginate_modules(curr_page - 1, HELPABLE, "help"))
        await edit_styled(query.message, top_text, nav_markup, "help")

    elif next_match:
        next_page = int(next_match.group(1))
        nav_markup = InlineKeyboardMarkup(paginate_modules(next_page + 1, HELPABLE, "help"))
        await edit_styled(query.message, top_text, nav_markup, "help")

    elif back_match:
        nav_markup = InlineKeyboardMarkup(paginate_modules(0, HELPABLE, "help"))
        await edit_styled(query.message, top_text, nav_markup, "help")

    elif create_match:
        text, keyboard = await help_parser(query)
        await edit_styled(query.message, text, keyboard, "help")

    return await client.answer_callback_query(query.id)


if __name__ == "__main__":
    install()
    with closing(loop):
        with suppress(asyncio.exceptions.CancelledError):
            loop.run_until_complete(start_bot())
        loop.run_until_complete(asyncio.sleep(3.0))  # task cancel wait
