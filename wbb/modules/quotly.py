import io
import re
import logging

from PIL import Image, ImageDraw, ImageFont, ImageOps
from pyrogram import filters
from pyrogram.types import Message

from wbb import USERBOT_PREFIX, app, app2

LOGGER = logging.getLogger(__name__)

WIDTH = 800
HEIGHT = 450

BACKGROUND = (28, 30, 38)
TEXT_COLOR = (245, 245, 245)
ACCENT_COLOR = (255, 105, 180)


def get_font(size: int):
    """Load a font with a safe fallback."""
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except (OSError, IOError):
        return ImageFont.load_default()


def get_message_text(message: Message) -> str:
    """Extract text from the replied message or command arguments."""
    replied = message.reply_to_message

    if replied:
        return (
            replied.text
            or replied.caption
            or "[Media message]"
        )

    text = message.text or message.caption or ""
    parts = text.split(maxsplit=1)

    if len(parts) > 1:
        return parts[1].strip()

    return "Please reply to a message or provide text."


def get_display_name(message: Message) -> str:
    """Get the sender's display name."""
    user = message.from_user

    if not user:
        return "Anonymous"

    name = user.first_name or user.username or "Anonymous"

    if user.last_name:
        name = f"{name} {user.last_name}"

    return name


def wrap_text(draw, text: str, font, max_width: int):
    """Wrap text to fit within the quote card."""
    lines = []

    for paragraph in text.splitlines() or [""]:
        words = paragraph.split()
        current_line = ""

        if not words:
            lines.append("")
            continue

        for word in words:
            # Split extremely long words to avoid overflow.
            remaining = word

            while remaining:
                test_line = (
                    f"{current_line} {remaining}".strip()
                )

                box = draw.textbbox(
                    (0, 0),
                    test_line,
                    font=font,
                )

                if box[2] - box[0] <= max_width:
                    current_line = test_line
                    remaining = ""
                else:
                    if current_line:
                        lines.append(current_line)
                        current_line = ""

                    # If the word itself is too wide, split it.
                    if not remaining:
                        break

                    chunk = ""

                    for char in remaining:
                        candidate = chunk + char
                        box = draw.textbbox(
                            (0, 0),
                            candidate,
                            font=font,
                        )

                        if box[2] - box[0] <= max_width:
                            chunk = candidate
                        else:
                            break

                    if not chunk:
                        chunk = remaining[0]

                    lines.append(chunk)
                    remaining = remaining[len(chunk):]

        if current_line:
            lines.append(current_line)

    return lines


def create_quote_image(text: str, name: str) -> io.BytesIO:
    """Create a quote card locally using Pillow."""
    image = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        BACKGROUND,
    )
    draw = ImageDraw.Draw(image)

    title_font = get_font(23)
    quote_font = get_font(29)
    footer_font = get_font(18)

    draw.rounded_rectangle(
        (35, 35, WIDTH - 35, HEIGHT - 35),
        radius=24,
        outline=ACCENT_COLOR,
        width=3,
    )

    draw.text(
        (60, 45),
        "❝",
        font=get_font(64),
        fill=ACCENT_COLOR,
    )

    draw.text(
        (60, 120),
        name[:45],
        font=title_font,
        fill=ACCENT_COLOR,
    )

    text = (text or "[Empty message]").strip()
    lines = wrap_text(
        draw,
        text[:1500],
        quote_font,
        WIDTH - 140,
    )

    line_height = 36
    available_height = 190
    max_lines = max(
        1,
        available_height // line_height,
    )

    if len(lines) > max_lines:
        lines = lines[:max_lines]

        # Mark the final visible line as truncated.
        if lines:
            last = lines[-1]

            while last:
                box = draw.textbbox(
                    (0, 0),
                    last + "...",
                    font=quote_font,
                )

                if box[2] - box[0] <= WIDTH - 140:
                    break

                last = last[:-1]

            lines[-1] = last + "..."

    y = 170

    for line in lines:
        draw.text(
            (65, y),
            line,
            font=quote_font,
            fill=TEXT_COLOR,
        )
        y += line_height

    draw.text(
        (60, HEIGHT - 70),
        "Foxy Quote",
        font=footer_font,
        fill=(170, 170, 180),
    )

    output = io.BytesIO()
    image.save(output, format="PNG")
    output.name = "quote.png"
    output.seek(0)

    return output


async def send_quote(message: Message):
    """Generate and send a quote image."""
    text = get_message_text(message)

    if not text or text.startswith(
        "Please reply to a message"
    ):
        await message.reply_text(
            "Reply to a message or provide text to create a quote."
        )
        return

    source = message.reply_to_message or message
    name = get_display_name(source)

    output = create_quote_image(text, name)

    await message.reply_photo(
        photo=output,
        quote=True,
    )


async def process_qpic(message: Message):
    """Create a quote image, grayscale image, or WebP sticker."""
    text = get_message_text(message)

    if not text or text.startswith(
        "Please reply to a message"
    ):
        await message.reply_text(
            "Reply to a message or provide text.\n\n"
            "Options:\n"
            "-b : Black and white\n"
            "-s : WebP sticker"
        )
        return

    source = message.reply_to_message or message
    name = get_display_name(source)

    command_text = message.text or message.caption or ""

    grayscale = bool(
        re.search(r"(?:^|\s)-b(?:\s|$)", command_text)
    )
    sticker = bool(
        re.search(r"(?:^|\s)-s(?:\s|$)", command_text)
    )

    # Remove options from the text when no message is replied to.
    if not message.reply_to_message:
        text = re.sub(
            r"(?:^|\s)-[bs](?=\s|$)",
            " ",
            text,
        ).strip()

    if not text:
        await message.reply_text(
            "Please provide some text for the quote."
        )
        return

    output = create_quote_image(text, name)

    with Image.open(output) as source_image:
        image = source_image.convert("RGB")

    if grayscale:
        image = ImageOps.grayscale(image).convert("RGB")

    result = io.BytesIO()

    if sticker:
        # Telegram stickers should fit within 512x512.
        image.thumbnail((512, 512))
        image.save(
            result,
            format="WEBP",
            quality=90,
        )
        result.name = "quote.webp"
        result.seek(0)

        await message.reply_sticker(
            sticker=result,
        )
    else:
        image.save(
            result,
            format="PNG",
        )
        result.name = "quote.png"
        result.seek(0)

        await message.reply_document(
            document=result,
            caption="Here is your quote.",
        )


@app.on_message(
    filters.command(["q", "quote"])
    & filters.group
)
async def quote_command(_, message: Message):
    """Bot quote command."""
    try:
        await send_quote(message)
    except Exception:
        LOGGER.exception("Bot quote command failed")
        await message.reply_text(
            "Failed to create the quote. Please try again."
        )


@app.on_message(
    filters.command(["qpic"])
)
async def qpic_command(_, message: Message):
    """Bot quote picture command."""
    try:
        await process_qpic(message)
    except Exception:
        LOGGER.exception("Bot qpic command failed")
        await message.reply_text(
            "Failed to create the quote picture. Please try again."
        )


@app2.on_message(
    filters.command(
        ["q", "rq", "fq", "frq", "qbot"],
        prefixes=USERBOT_PREFIX,
    )
    & filters.me
)
async def userbot_quote_command(_, message: Message):
    """Userbot quote commands."""
    try:
        await send_quote(message)
    except Exception:
        LOGGER.exception("Userbot quote command failed")
        await message.reply_text(
            "Failed to create the quote. Please try again."
        )


@app2.on_message(
    filters.command(
        ["qpic"],
        prefixes=USERBOT_PREFIX,
    )
    & filters.me
)
async def userbot_qpic_command(_, message: Message):
    """Userbot quote picture command."""
    try:
        await process_qpic(message)
    except Exception:
        LOGGER.exception("Userbot qpic command failed")
        await message.reply_text(
            "Failed to create the quote picture. Please try again."
        )
