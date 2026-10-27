import io
import re
import logging
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pyrogram import filters
from pyrogram.types import Message

from wbb import USERBOT_PREFIX, app, app2, SUDOERS
from wbb.utils.errors import capture_err

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
    except OSError:
        return ImageFont.load_default()


def get_message_text(message: Message) -> str:
    """Extract text from a message or its replied message."""
    if message.reply_to_message:
        replied = message.reply_to_message
        return replied.text or replied.caption or "[Media message]"

    text = message.text or message.caption or ""
    parts = text.split(maxsplit=1)

    if len(parts) > 1:
        return parts[1]

    return "Please reply to a message or provide text."


def get_display_name(message: Message) -> str:
    """Get the sender's display name."""
    user = message.from_user

    if not user:
        return "Anonymous"

    return user.first_name or user.username or "Anonymous"


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
            test_line = f"{current_line} {word}".strip()
            box = draw.textbbox((0, 0), test_line, font=font)

            if box[2] - box[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

    return lines


def create_quote_image(text: str, name: str) -> io.BytesIO:
    """Create a quote card locally using Pillow."""
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)

    title_font = get_font(23)
    quote_font = get_font(29)
    footer_font = get_font(18)

    # Decorative accent
    draw.rounded_rectangle(
        (35, 35, WIDTH - 35, HEIGHT - 35),
        radius=24,
        outline=ACCENT_COLOR,
        width=3,
    )

    draw.text(
        (60, 55),
        "❝",
        font=get_font(64),
        fill=ACCENT_COLOR,
    )

    draw.text(
        (60, 125),
        name[:45],
        font=title_font,
        fill=ACCENT_COLOR,
    )

    lines = wrap_text(
        draw,
        text[:1500],
        quote_font,
        WIDTH - 140,
    )

    line_height = 42
    available_height = 210
    max_lines = max(1, available_height // line_height)
    lines = lines[:max_lines]

    y = 175

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
    name = get_display_name(
        message.reply_to_message or message
    )

    output = create_quote_image(text, name)

    await message.reply_photo(
        photo=output,
        quote=True,
    )


@app.on_message(
    filters.command(["q", "quote"])
    & filters.group
)
@capture_err
async def quote_command(_, message: Message):
    """Bot quote command."""
    await send_quote(message)


@app.on_message(
    filters.command(["qpic"])
)
@capture_err
async def qpic_command(_, message: Message):
    """Create a quote picture, grayscale image, or WebP sticker."""
    text = get_message_text(message)
    name = get_display_name(
        message.reply_to_message or message
    )

    command_text = message.text or ""
    grayscale = bool(re.search(r"(?:^|\s)-b(?:\s|$)", command_text))
    sticker = bool(re.search(r"(?:^|\s)-s(?:\s|$)", command_text))

    # Remove command flags from text when no message is replied to.
    if not message.reply_to_message:
        text = re.sub(r"(?:^|\s)-[bs](?=\s|$)", " ", text).strip()

    output = create_quote_image(text, name)

    image = Image.open(output).convert("RGB")

    if grayscale:
        image = ImageOps.grayscale(image).convert("RGB")

    result = io.BytesIO()

    if sticker:
        image.save(result, format="WEBP", quality=90)
        result.name = "quote.webp"
        result.seek(0)
        await message.reply_sticker(sticker=result)
    else:
        image.save(result, format="PNG")
        result.name = "quote.png"
        result.seek(0)
        await message.reply_document(
            document=result,
            caption="Here is your quote.",
        )


# Userbot quote commands
@app2.on_message(
    filters.command(
        ["q", "rq", "fq", "frq", "qbot"],
        prefixes=USERBOT_PREFIX,
    )
    & filters.me
)
@capture_err
async def userbot_quote_command(_, message: Message):
    """Userbot quote commands."""
    await send_quote(message)


@app2.on_message(
    filters.command(
        ["qpic"],
        prefixes=USERBOT_PREFIX,
    )
    & filters.me
)
@capture_err
async def userbot_qpic_command(_, message: Message):
    """Userbot quote picture command."""
    await qpic_command(_, message)
