from __future__ import annotations

import asyncio
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
from telegram.error import Conflict, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("ZEE_BOTS")


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "ZEE BOTS Image Link Bot is running!", 200


@app.route("/health")
def health():
    return "OK", 200


def run_server():
    port = int(os.getenv("PORT", "10000"))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
    )


def start_server():
    thread = Thread(
        target=run_server,
        daemon=True,
    )
    thread.start()


# =========================================================
# ENVIRONMENT
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY", "").strip()


if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN environment variable is missing."
    )

if not IMGBB_API_KEY:
    raise RuntimeError(
        "IMGBB_API_KEY environment variable is missing."
    )


# =========================================================
# PREMIUM TEXT
# =========================================================

WELCOME_TEXT = """
╭━━━「 🖼️ <b>ZEE BOTS</b> 」━━━╮
┃
┃  <b>IMAGE → DIRECT LINK</b>
┃
┃  Convert your image into a
┃  clean &amp; direct HTTPS URL.
┃
┃  ⚡ <b>Fast Processing</b>
┃  🔗 <b>Direct Image URL</b>
┃  ☁️ <b>Reliable Hosting</b>
┃  🔒 <b>HTTPS Link</b>
┃
┃  <i>Send an image to get started.</i>
┃
╰━━━━━━━━━━━━━━━━━━━━╯
"""


HELP_TEXT = """
╭━━━「 ℹ️ <b>HELP CENTER</b> 」━━━╮
┃
┃  <b>How to use ZEE BOTS</b>
┃
┃ ① Send an image to this chat.
┃
┃ ② The bot processes your image.
┃
┃ ③ A direct HTTPS image URL
┃    will be generated.
┃
┃ ④ Tap <b>Open Image</b> to open it.
┃
┃ ⑤ Previous links remain in this
┃    Telegram chat as your history.
┃
┃ <b>Supported:</b>
┃ JPG • JPEG • PNG • WEBP
┃
┃  No Firebase or database is used.
┃
╰━━━━━━━━━━━━━━━━━━━━╯
"""


READY_TEXT = """
╭━━━「 🖼️ <b>READY</b> 」━━━╮
┃
┃  Send your image now.
┃
┃  ⚡ Your direct image link
┃  will be generated automatically.
┃
╰━━━━━━━━━━━━━━━━━━━━╯
"""


PROCESSING_TEXT = """
╭━━━「 ⚡ <b>PROCESSING</b> 」━━━╮
┃
┃  Your image is being processed.
┃
┃  ⏳ <i>Please wait a moment...</i>
┃
╰━━━━━━━━━━━━━━━━━━━━╯
"""


DOWNLOAD_FAILED_TEXT = """
╭━━━「 ❌ <b>DOWNLOAD FAILED</b> 」━━━╮
┃
┃  We couldn't download your image.
┃
┃  Please send it again.
┃
╰━━━━━━━━━━━━━━━━━━━━━━━━╯
"""


UPLOAD_FAILED_TEXT = """
╭━━━「 ❌ <b>UPLOAD FAILED</b> 」━━━╮
┃
┃  We couldn't create your image link.
┃
┃  Please try again later.
┃
╰━━━━━━━━━━━━━━━━━━━━━━━━╯
"""


IMAGE_REQUIRED_TEXT = """
╭━━━「 ⚠️ <b>IMAGE REQUIRED</b> 」━━━╮
┃
┃  Please send an image to continue.
┃
┃  Supported:
┃  JPG • JPEG • PNG • WEBP
┃
╰━━━━━━━━━━━━━━━━━━━━━━━━╯
"""


# =========================================================
# KEYBOARDS
# =========================================================

def main_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "ℹ️ Help",
                    callback_data="help",
                )
            ]
        ]
    )


def help_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "⬅️ Back",
                    callback_data="back",
                ),
                InlineKeyboardButton(
                    "🖼️ Upload",
                    callback_data="upload",
                ),
            ]
        ]
    )


def result_keyboard(url: str):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🌐 Open Image",
                    url=url,
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
    )


# =========================================================
# /START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    await update.message.reply_text(
        WELCOME_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(),
    )


# =========================================================
# /HELP
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    await update.message.reply_text(
        HELP_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=help_keyboard(),
    )


# =========================================================
# BUTTON HANDLER
# =========================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    action = query.data

    # -----------------------------------------
    # HELP
    # -----------------------------------------

    if action == "help":

        await query.edit_message_text(
            HELP_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=help_keyboard(),
        )

        return

    # -----------------------------------------
    # BACK
    # -----------------------------------------

    if action == "back":

        await query.edit_message_text(
            WELCOME_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard(),
        )

        return

    # -----------------------------------------
    # UPLOAD
    # -----------------------------------------

    if action == "upload":

        await query.edit_message_text(
            READY_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=help_keyboard(),
        )

        return


# =========================================================
# IMGBB UPLOAD
# =========================================================

def upload_to_imgbb(
    image_data: bytes,
) -> str | None:

    url = "https://api.imgbb.com/1/upload"

    try:

        response = requests.post(
            url,
            params={
                "key": IMGBB_API_KEY,
            },
            files={
                "image": (
                    "image.jpg",
                    image_data,
                    "image/jpeg",
                )
            },
            timeout=60,
        )

        response.raise_for_status()

        data = response.json()

        if not data.get("success"):
            logger.error(
                "ImgBB response unsuccessful: %s",
                data,
            )
            return None

        image_data_result = data.get(
            "data",
            {}
        )

        # Prefer direct display URL
        direct_url = image_data_result.get(
            "display_url"
        )

        if not direct_url:
            direct_url = image_data_result.get(
                "url"
            )

        if not direct_url:
            direct_url = image_data_result.get(
                "image",
                {}
            ).get("url")

        if not direct_url:
            logger.error(
                "No direct image URL returned."
            )
            return None

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
# IMAGE HANDLER
# =========================================================

async def handle_image(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message = update.message

    if not message:
        return

    if not message.photo:
        return

    user = message.from_user

    user_id = (
        user.id
        if user
        else "unknown"
    )

    # -----------------------------------------
    # PROCESSING MESSAGE
    # -----------------------------------------

    processing = await message.reply_text(
        PROCESSING_TEXT,
        parse_mode=ParseMode.HTML,
    )

    buffer = BytesIO()

    # -----------------------------------------
    # DOWNLOAD TELEGRAM IMAGE
    # -----------------------------------------

    try:

        # Highest resolution photo
        photo = message.photo[-1]

        telegram_file = await context.bot.get_file(
            photo.file_id
        )

        await telegram_file.download_to_memory(
            buffer
        )

        image_bytes = buffer.getvalue()

        if not image_bytes:
            raise ValueError(
                "Downloaded image is empty."
            )

        logger.info(
            "Image downloaded | user=%s | size=%s",
            user_id,
            len(image_bytes),
        )

    except Exception as error:

        logger.exception(
            "Telegram download failed: %s",
            error,
        )

        await processing.edit_text(
            DOWNLOAD_FAILED_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=help_keyboard(),
        )

        return

    # -----------------------------------------
    # IMGBB UPLOAD
    # -----------------------------------------

    try:

        direct_url = await asyncio.to_thread(
            upload_to_imgbb,
            image_bytes,
        )

    except Exception as error:

        logger.exception(
            "Upload thread failed: %s",
            error,
        )

        direct_url = None

    if not direct_url:

        await processing.edit_text(
            UPLOAD_FAILED_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=help_keyboard(),
        )

        return

    # -----------------------------------------
    # SUCCESS
    # -----------------------------------------

    safe_url = html.escape(
        direct_url
    )

    success_text = f"""
╭━━━「 ✅ <b>IMAGE READY</b> 」━━━╮
┃
┃  <b>Your direct image link is ready.</b>
┃
┃  🔗 <b>DIRECT URL</b>
┃
┃  <code>{safe_url}</code>
┃
┃  ⚡ Fast Processing
┃  ☁️ Image Hosted
┃  🔒 HTTPS Link
┃
┃  <i>This link remains in your
┃  Telegram chat history.</i>
┃
╰━━━━━━━━━━━━━━━━━━━━╯
"""

    try:

        await processing.edit_text(
            success_text,
            parse_mode=ParseMode.HTML,
            reply_markup=result_keyboard(
                direct_url
            ),
            disable_web_page_preview=True,
        )

        logger.info(
            "Image link generated | user=%s | url=%s",
            user_id,
            direct_url,
        )

    except TelegramError as error:

        logger.exception(
            "Failed to send result: %s",
            error,
        )


# =========================================================
# DOCUMENT IMAGE SUPPORT
# =========================================================

async def handle_image_document(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    message = update.message

    if not message or not message.document:
        return

    document = message.document

    mime = (
        document.mime_type or ""
    ).lower()

    allowed_mimes = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    }

    if mime not in allowed_mimes:
        await message.reply_text(
            IMAGE_REQUIRED_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=help_keyboard(),
        )
        return

    processing = await message.reply_text(
        PROCESSING_TEXT,
        parse_mode=ParseMode.HTML,
    )

    buffer = BytesIO()

    try:

        telegram_file = await context.bot.get_file(
            document.file_id
        )

        await telegram_file.download_to_memory(
            buffer
        )

        image_bytes = buffer.getvalue()

        if not image_bytes:
            raise ValueError(
                "Empty image."
            )

    except Exception:

        logger.exception(
            "Document download failed"
        )

        await processing.edit_text(
            DOWNLOAD_FAILED_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=help_keyboard(),
        )

        return

    try:

        direct_url = await asyncio.to_thread(
            upload_to_imgbb,
            image_bytes,
        )

    except Exception:

        logger.exception(
            "Document upload failed"
        )

        direct_url = None

    if not direct_url:

        await processing.edit_text(
            UPLOAD_FAILED_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=help_keyboard(),
        )

        return

    safe_url = html.escape(
        direct_url
    )

    success_text = f"""
╭━━━「 ✅ <b>IMAGE READY</b> 」━━━╮
┃
┃  <b>Your direct image link is ready.</b>
┃
┃  🔗 <b>DIRECT URL</b>
┃
┃  <code>{safe_url}</code>
┃
┃  ⚡ Fast Processing
┃  ☁️ Image Hosted
┃  🔒 HTTPS Link
┃
┃  <i>This link remains in your
┃  Telegram chat history.</i>
┃
╰━━━━━━━━━━━━━━━━━━━━╯
"""

    await processing.edit_text(
        success_text,
        parse_mode=ParseMode.HTML,
        reply_markup=result_keyboard(
            direct_url
        ),
        disable_web_page_preview=True,
    )


# =========================================================
# UNSUPPORTED MESSAGE
# =========================================================

async def unsupported_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    await update.message.reply_text(
        IMAGE_REQUIRED_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=help_keyboard(),
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):

    error = context.error

    if isinstance(error, Conflict):

        logger.error(
            "Telegram 409 Conflict: another "
            "instance is using this bot token."
        )

    else:

        logger.exception(
            "Unhandled bot error",
            exc_info=error,
        )


# =========================================================
# BUILD APPLICATION
# =========================================================

def build_application():

    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # /start
    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    # /help
    application.add_handler(
        CommandHandler(
            "help",
            help_command,
        )
    )

    # Telegram photos
    application.add_handler(
        MessageHandler(
            filters.PHOTO,
            handle_image,
        )
    )

    # Images sent as files/documents
    application.add_handler(
        MessageHandler(
            filters.Document.IMAGE,
            handle_image_document,
        )
    )

    # Buttons
    application.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    # Unsupported messages
    application.add_handler(
        MessageHandler(
            filters.ALL,
            unsupported_message,
        )
    )

    # Error handler
    application.add_error_handler(
        error_handler
    )

    return application


# =========================================================
# MAIN
# =========================================================

def main():

    logger.info(
        "===================================="
    )

    logger.info(
        "ZEE BOTS starting..."
    )

    logger.info(
        "Storage: ImgBB"
    )

    logger.info(
        "Firebase: DISABLED"
    )

    logger.info(
        "Database History: DISABLED"
    )

    logger.info(
        "Telegram Chat History: ENABLED"
    )

    logger.info(
        "===================================="
    )

    # Start Render web server
    start_server()

    # Build Telegram bot
    application = build_application()

    try:

        application.run_polling(
            drop_pending_updates=True
        )

    except Conflict:

        logger.error(
            "409 Conflict detected. "
            "Make sure the bot is running "
            "in only ONE place."
        )

        raise SystemExit(1)

    except KeyboardInterrupt:

        logger.info(
            "Bot stopped."
        )

    except Exception:

        logger.exception(
            "Bot stopped unexpectedly."
        )

        raise SystemExit(1)


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()
