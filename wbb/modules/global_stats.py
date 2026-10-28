import asyncio

from pyrogram import filters
from pyrogram.errors import FloodWait

from wbb import BOT_ID, BOT_NAME, SUDOERS, app
from wbb.core.decorators.errors import capture_err
from wbb.utils.dbfunctions import (
    get_blacklist_filters_count,
    get_filters_count,
    get_gbans_count,
    get_karmas_count,
    get_notes_count,
    get_rss_feeds_count,
    get_served_chats,
    get_served_users,
    get_warns_count,
    remove_served_chat,
)
from wbb.modules import ALL_MODULES
from wbb.utils.inlinefuncs import keywords_list


@app.on_message(filters.command("clean_db") & SUDOERS)
@capture_err
async def clean_db(_, message):
    served_chats = [
        int(i["chat_id"]) for i in await get_served_chats()
    ]

    m = await message.reply(
        f"__**Cleaning database, Might take around "
        f"{len(served_chats) * 2} seconds.**__"
    )

    for served_chat in served_chats.copy():
        try:
            await app.get_chat_members(served_chat, BOT_ID)
            await asyncio.sleep(2)
        except FloodWait as e:
            await asyncio.sleep(int(e.value))
        except Exception:
            await remove_served_chat(served_chat)
            served_chats.remove(served_chat)

    await m.edit("**Database Cleaned.**")


async def get_total_users_count():
    schats = await get_served_chats()
    chats = [int(chat["chat_id"]) for chat in schats]
    total_count = 0

    for chat_id in chats:
        try:
            count = await app.get_chat_members_count(chat_id)
            total_count += count
        except Exception as e:
            print(
                f"Error fetching members count for chat "
                f"{chat_id}: {e}"
            )

    return total_count


@app.on_message(filters.command(["stats", "gstats"]) & SUDOERS)
@capture_err
async def global_stats(_, message):
    m = await app.send_message(
        message.chat.id,
        text="__**Analysing Stats...**__",
        disable_web_page_preview=True,
    )

    # Bot served chats and users
    served_chats = len(await get_served_chats())
    served_users = len(await get_served_users())
    total_users = await get_total_users_count()

    # Global bans
    gbans = await get_gbans_count()

    # Notes
    notes = await get_notes_count()
    notes_count = notes["notes_count"]
    notes_chats_count = notes["chats_count"]

    # Filters
    filters_data = await get_filters_count()
    filters_count = filters_data["filters_count"]
    filters_chats_count = filters_data["chats_count"]

    # Blacklisted filters
    blacklist_data = await get_blacklist_filters_count()
    blacklist_filters_count = blacklist_data["filters_count"]
    blacklist_filters_chats_count = blacklist_data["chats_count"]

    # Warns
    warns = await get_warns_count()
    warns_count = warns["warns_count"]
    warns_chats_count = warns["chats_count"]

    # Karma
    karmas = await get_karmas_count()
    karmas_count = karmas["karmas_count"]
    karmas_chats_count = karmas["chats_count"]

    # RSS feeds
    rss_count = await get_rss_feeds_count()

    # Modules
    modules_count = len(ALL_MODULES)
    inline_modules_count = len(keywords_list)

    msg = f"""
**Global Stats of {BOT_NAME}**:
    **{modules_count}** Modules Loaded.
    **{inline_modules_count}** Inline Modules Loaded.
    **{rss_count}** Active RSS Feeds.
    **{gbans}** Globally banned users.
    **{filters_count}** Filters, Across **{filters_chats_count}** chats.
    **{blacklist_filters_count}** Blacklist Filters, Across **{blacklist_filters_chats_count}** chats.
    **{notes_count}** Notes, Across **{notes_chats_count}** chats.
    **{warns_count}** Warns, Across **{warns_chats_count}** chats.
    **{karmas_count}** Karma, Across **{karmas_chats_count}** chats.
    **{served_users}** Users, Across **{served_chats}** chats.
    **{total_users}** Total users in chats.
"""

    await m.edit(
        msg,
        disable_web_page_preview=True,
    )

