from __future__ import annotations

import asyncio
import base64
import html
import logging
import os
from io import BytesIO
from threading import Thread

import requests
from flask import Flask

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


# =========================================================
# CONFIGURATION
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY", "").strip()

PORT = int(os.getenv("PORT", "10000"))


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# STARTUP CHECK
# =========================================================

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing.")

if not IMGBB_API_KEY:
    raise RuntimeError("IMGBB_API_KEY environment variable is missing.")


logger.info("====================================")
logger.info("ZEE BOTS - IMAGE LINK BOT")
logger.info("====================================")
logger.info("Storage: ImgBB")
logger.info("Firebase: DISABLED")
logger.info("Database History: DISABLED")
logger.info("Telegram Chat History: ENABLED")
logger.info("====================================")


# =========================================================
# FLASK SERVER FOR RENDER
# =========================================================

flask_app = Flask(__name__)


@flask_app.route("/")
def home():
    return "ZEE BOTS Image Link Bot is running!", 200


@flask_app.route("/health")
def health():
    return "OK", 200


def run_flask():
    flask_app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        use_reloader=False,
    )


# =========================================================
# TELEGRAM KEYBOARDS
# =========================================================

def main_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(
                "🖼️ Upload Image",
                callback_data="upload",
            )
        ],
        [
            InlineKeyboardButton(
                "ℹ️ Help",
                callback_data="help",
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def result_keyboard(image_url: str):
    keyboard = [
        [
            InlineKeyboardButton(
                "🌐 Open Image",
                url=image_url,
            )
        ],
        [
            InlineKeyboardButton(
                "🖼️ Upload Another",
                callback_data="upload",
            )
        ],
        [
            InlineKeyboardButton(
                "ℹ️ Help",
                callback_data="help",
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def help_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data="back",
            )
        ],
        [
            InlineKeyboardButton(
                "🖼️ Upload Image",
                callback_data="upload",
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# START MESSAGE
# =========================================================

START_TEXT = """
<b>╭───「 ZEE BOTS 」───╮</b>

<b>🖼️ IMAGE → DIRECT LINK</b>

Turn your image into a
clean direct image URL instantly.

<b>✨ Features</b>
• Fast image upload
• Direct HTTPS image link
• Open image button
• Easy copy & share
• No account required
• No database history

<b>📌 How to use</b>
Simply send an image here.

<b>⚡ Powered by ZEE BOTS</b>
<b>╰────────────────────╯</b>
"""


# =========================================================
# HELP MESSAGE
# =========================================================

HELP_TEXT = """
<b>╭───「 ℹ️ HELP 」───╮</b>

<b>How to convert an image?</b>

1️⃣ Send any image to this bot.
2️⃣ Wait while it processes.
3️⃣ You will receive a direct HTTPS image link.
4️⃣ Use <b>Open Image</b> or copy the link.

<b>📂 Supported</b>
• Telegram photos
• Image documents
• JPG / JPEG
• PNG
• WEBP
• GIF
• Other image formats supported by Telegram

<b>🔐 Privacy</b>
This bot does not use Firebase
or a separate database for history.

Your generated links remain
available in your Telegram chat history.

<b>👨‍💻 Created by @zee_bot_creator_bot</b>

<b>╰────────────────────╯</b>
"""


# =========================================================
# IMGBB UPLOAD
# =========================================================

def upload_to_imgbb(image_data: bytes) -> str | None:
    """
    Upload image bytes to ImgBB.

    ImgBB accepts the image as Base64 through
    the 'image' POST field.
    """

    url = "https://api.imgbb.com/1/upload"

    try:

        # Convert image bytes to Base64
        encoded_image = base64.b64encode(
            image_data
        ).decode("utf-8")

        response = requests.post(
            url,
            data={
                "key": IMGBB_API_KEY,
                "image": encoded_image,
            },
            timeout=60,
        )

        # Log ImgBB response for debugging
        logger.info(
            "ImgBB response | status=%s | body=%s",
            response.status_code,
            response.text[:1000],
        )

        response.raise_for_status()

        data = response.json()

        if not data.get("success"):
            logger.error(
                "ImgBB upload unsuccessful | response=%s",
                data,
            )
            return None

        image_info = data.get("data", {})

        # Try direct URL
        direct_url = image_info.get("url")

        if not direct_url:
            direct_url = image_info.get("display_url")

        if not direct_url:
            image_object = image_info.get("image", {})

            if isinstance(image_object, dict):
                direct_url = image_object.get("url")

        if not direct_url:
            logger.error(
                "ImgBB upload succeeded but no URL found."
            )
            return None

        logger.info(
            "ImgBB upload successful | url=%s",
            direct_url,
        )

        return direct_url

    except requests.RequestException as error:
        logger.exception(
            "ImgBB request failed: %s",
            error,
        )
        return None

    except Exception as error:
        logger.exception(
            "Unexpected ImgBB error: %s",
            error,
        )
        return None


# =========================================================
# /START
# =========================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    await update.message.reply_text(
        START_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(),
        disable_web_page_preview=True,
    )


# =========================================================
# CALLBACK BUTTONS
# =========================================================

async def callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    if not query:
        return

    await query.answer()

    try:

        # ---------------------------------------------
        # UPLOAD
        # ---------------------------------------------

        if query.data == "upload":

            upload_text = """
<b>🖼️ SEND YOUR IMAGE</b>

Please send an image here.

I will convert it into a
<b>direct HTTPS image link</b>.

⚡ Fast • Simple • Direct
"""

            await query.edit_message_text(
                upload_text,
                parse_mode=ParseMode.HTML,
                reply_markup=help_keyboard(),
            )

        # ---------------------------------------------
        # HELP
        # ---------------------------------------------

        elif query.data == "help":

            await query.edit_message_text(
                HELP_TEXT,
                parse_mode=ParseMode.HTML,
                reply_markup=help_keyboard(),
                disable_web_page_preview=True,
            )

        # ---------------------------------------------
        # BACK
        # ---------------------------------------------

        elif query.data == "back":

            await query.edit_message_text(
                START_TEXT,
                parse_mode=ParseMode.HTML,
                reply_markup=main_keyboard(),
                disable_web_page_preview=True,
            )

    except TelegramError as error:

        logger.exception(
            "Telegram callback error: %s",
            error,
        )


# =========================================================
# IMAGE PROCESSING
# =========================================================

async def process_image(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    telegram_file_id: str,
):

    if not update.message:
        return

    message = update.message

    user_id = (
        message.from_user.id
        if message.from_user
        else "unknown"
    )

    processing_message = await message.reply_text(
        """
<b>⏳ PROCESSING IMAGE...</b>

Downloading your image and
creating a direct link.

Please wait...
""",
        parse_mode=ParseMode.HTML,
    )

    try:

        # ---------------------------------------------
        # DOWNLOAD FROM TELEGRAM
        # ---------------------------------------------

        telegram_file = await context.bot.get_file(
            telegram_file_id
        )

        buffer = BytesIO()

        await telegram_file.download_to_memory(
            buffer
        )

        image_bytes = buffer.getvalue()

        logger.info(
            "Image downloaded | user=%s | size=%s",
            user_id,
            len(image_bytes),
        )

        if not image_bytes:

            await processing_message.edit_text(
                """
<b>❌ UPLOAD FAILED</b>

The image could not be downloaded.

Please try sending the image again.
""",
                parse_mode=ParseMode.HTML,
            )

            return

        # ---------------------------------------------
        # UPLOAD TO IMGBB
        # ---------------------------------------------

        direct_url = await asyncio.to_thread(
            upload_to_imgbb,
            image_bytes,
        )

        # ---------------------------------------------
        # FAILED
        # ---------------------------------------------

        if not direct_url:

            await processing_message.edit_text(
                """
<b>╭───「 ❌ UPLOAD FAILED 」───╮</b>

Something went wrong while
processing your image.

Please try again later.

<b>╰────────────────────────╯</b>
""",
                parse_mode=ParseMode.HTML,
                reply_markup=main_keyboard(),
            )

            return

        # ---------------------------------------------
        # SUCCESS
        # ---------------------------------------------

        safe_url = html.escape(
            direct_url,
            quote=False,
        )

        result_text = f"""
<b>╭───「 ✅ UPLOAD COMPLETE 」───╮</b>

<b>🖼️ Image uploaded successfully!</b>

<b>🔗 Direct Image Link:</b>

<code>{safe_url}</code>

<b>💡 Tap the button below to open it.</b>

<b>⚡ Powered by ZEE BOTS</b>

<b>╰────────────────────────────╯</b>
"""

        await processing_message.edit_text(
            result_text,
            parse_mode=ParseMode.HTML,
            reply_markup=result_keyboard(
                direct_url
            ),
            disable_web_page_preview=True,
        )

        logger.info(
            "Image processed successfully | user=%s",
            user_id,
        )

    except TelegramError as error:

        logger.exception(
            "Telegram file error | user=%s | error=%s",
            user_id,
            error,
        )

        try:

            await processing_message.edit_text(
                """
<b>❌ TELEGRAM ERROR</b>

Could not download the image
from Telegram.

Please try again.
""",
                parse_mode=ParseMode.HTML,
                reply_markup=main_keyboard(),
            )

        except Exception:
            pass

    except Exception as error:

        logger.exception(
            "Image processing error | user=%s | error=%s",
            user_id,
            error,
        )

        try:

            await processing_message.edit_text(
                """
<b>❌ SOMETHING WENT WRONG</b>

The image could not be processed.

Please try again.
""",
                parse_mode=ParseMode.HTML,
                reply_markup=main_keyboard(),
            )

        except Exception:
            pass


# =========================================================
# PHOTO HANDLER
# =========================================================

async def photo_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    if not update.message.photo:
        return

    # Get highest-resolution Telegram photo
    photo = update.message.photo[-1]

    await process_image(
        update,
        context,
        photo.file_id,
    )


# =========================================================
# IMAGE DOCUMENT HANDLER
# =========================================================

async def document_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    document = update.message.document

    if not document:
        return

    # Make sure it is an image
    mime_type = document.mime_type or ""

    if not mime_type.startswith("image/"):

        await update.message.reply_text(
            """
<b>⚠️ IMAGE ONLY</b>

Please send an image file.

Supported examples:
JPG • JPEG • PNG • WEBP • GIF
""",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard(),
        )

        return

    await process_image(
        update,
        context,
        document.file_id,
    )


# =========================================================
# TEXT HANDLER
# =========================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    await update.message.reply_text(
        """
<b>🖼️ IMAGE LINK BOT</b>

Please send an image to convert it
into a direct image URL.

<b>Example:</b>

Send → 🖼️ Image
Receive → 🔗 Direct HTTPS Link
""",
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(),
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):

    logger.exception(
        "Unhandled Telegram error:",
        exc_info=context.error,
    )


# =========================================================
# MAIN
# =========================================================

def main():

    # Start Render health server
    flask_thread = Thread(
        target=run_flask,
        daemon=True,
    )

    flask_thread.start()

    # Create Telegram application
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # ---------------------------------------------
    # COMMANDS
    # ---------------------------------------------

    application.add_handler(
        CommandHandler(
            "start",
            start_command,
        )
    )

    # ---------------------------------------------
    # CALLBACK BUTTONS
    # ---------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            callback_handler
        )
    )

    # ---------------------------------------------
    # TELEGRAM PHOTO
    # ---------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.PHOTO,
            photo_handler,
        )
    )

    # ---------------------------------------------
    # IMAGE DOCUMENT
    # ---------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.Document.IMAGE,
            document_handler,
        )
    )

    # ---------------------------------------------
    # TEXT
    # ---------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler,
        )
    )

    # ---------------------------------------------
    # ERRORS
    # ---------------------------------------------

    application.add_error_handler(
        error_handler
    )

    logger.info("Starting Telegram bot...")

    # Poll Telegram
    application.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()
