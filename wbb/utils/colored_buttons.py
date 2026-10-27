"""Apply Telegram Bot API native button styles without requiring Kurigram style support."""
import logging
import aiohttp

log = logging.getLogger(__name__)


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


async def colorize_message(message, markup, bot_token, mode):
    if message is None:
        return
    keyboard = styled_keyboard(markup, mode)
    if keyboard is None:
        return
    payload = {"chat_id": message.chat.id, "message_id": message.id, "reply_markup": keyboard}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"https://api.telegram.org/bot{bot_token}/editMessageReplyMarkup", json=payload, timeout=aiohttp.ClientTimeout(total=10)) as response:
                result = await response.json(content_type=None)
                if not result.get("ok"):
                    log.warning("Telegram coloured keyboard not applied: %s", result.get("description", "unknown error"))
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        log.warning("Telegram coloured keyboard request failed: %s", exc)
