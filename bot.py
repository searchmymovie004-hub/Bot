"""
ZEE BOTS
Premium Image → Direct Link Telegram Bot

Features:
- Premium UI / messaging
- Image → Cloudinary
- Direct HTTPS image link
- Open Image button
- Upload Another button
- Help + Back navigation
- No Firebase
- No database
- Telegram chat itself keeps the user's previous links
- Render Web Service compatible
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
from io import BytesIO
from threading import Thread
from typing import Any

import cloudinary
import cloudinary.uploader

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
    format=(
        "%(asctime)s | "
        "%(name)s | "
        "%(levelname)s | "
        "%(message)s"
    ),
    level=logging.INFO,
)

LOGGER = logging.getLogger("ZEE_BOTS")


# =========================================================
# RENDER WEB SERVER
# =========================================================

web_app = Flask(__name__)


@web_app.route("/")
def home():
    return "ZEE BOTS Image Link Bot is running!", 200


@web_app.route("/health")
def health():
    return "OK", 200


def run_http_server() -> None:
    port = int(os.getenv("PORT", "10000"))

    LOGGER.info(
        "Starting HTTP server on port %s",
        port,
    )

    web_app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
    )


def start_http_server() -> None:
    thread = Thread(
        target=run_http_server,
        daemon=True,
        name="render-http-server",
    )

    thread.start()

    LOGGER.info(
        "Render HTTP server started"
    )


# =========================================================
# ENVIRONMENT
# =========================================================

def get_environment() -> dict[str, str]:

    required = [
        "BOT_TOKEN",
        "CLOUDINARY_CLOUD_NAME",
        "CLOUDINARY_API_KEY",
        "CLOUDINARY_API_SECRET",
    ]

    values = {
        key: os.getenv(key, "").strip()
        for key in required
    }

    missing = [
        key
        for key, value in values.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Missing environment variable(s): "
            + ", ".join(missing)
        )

    return values


# =========================================================
# CLOUDINARY
# =========================================================

def configure_cloudinary(
    settings: dict[str, str],
) -> None:

    cloudinary.config(
        cloud_name=settings[
            "CLOUDINARY_CLOUD_NAME"
        ],
        api_key=settings[
            "CLOUDINARY_API_KEY"
        ],
        api_secret=settings[
            "CLOUDINARY_API_SECRET"
        ],
        secure=True,
    )

    LOGGER.info(
        "Cloudinary configured successfully"
    )


def upload_to_cloudinary(
    buffer: BytesIO,
) -> dict[str, Any]:

    options: dict[str, Any] = {
        "resource_type": "image",
        "folder": "zee_bots",
    }

    # Optional upload preset.
    preset = os.getenv(
        "CLOUDINARY_UPLOAD_PRESET",
        "",
    ).strip()

    if preset:
        options["upload_preset"] = preset

    return cloudinary.uploader.upload(
        buffer,
        **options,
    )


# =========================================================
# PREMIUM MESSAGES
# =========================================================

WELCOME_TEXT = (
    "╭━━━「 🖼️ <b>ZEE BOTS</b> 」━━━╮\n"
    "┃\n"
    "┃  <b>IMAGE → DIRECT LINK</b>\n"
    "┃\n"
    "┃  Turn your image into a\n"
    "┃  clean &amp; direct HTTPS URL.\n"
    "┃\n"
    "┃  ⚡ <b>Fast Processing</b>\n"
    "┃  🔗 <b>Direct Image URL</b>\n"
    "┃  ☁️ <b>Cloud Hosted</b>\n"
    "┃  🔒 <b>Secure HTTPS</b>\n"
    "┃\n"
    "┃  <i>Send an image to get started.</i>\n"
    "┃\n"
    "╰━━━━━━━━━━━━━━━━━━━━╯"
)


HELP_TEXT = (
    "╭━━━「 ℹ️ <b>HELP CENTER</b> 」━━━╮\n"
    "┃\n"
    "┃  <b>How to use ZEE BOTS</b>\n"
    "┃\n"
    "┃ ① Send an image to this chat.\n"
    "┃\n"
    "┃ ② The image will be processed\n"
    "┃    automatically.\n"
    "┃\n"
    "┃ ③ Your direct HTTPS image URL\n"
    "┃    will be generated.\n"
    "┃\n"
    "┃ ④ Tap <b>Open Image</b> to open it.\n"
    "┃\n"
    "┃ ⑤ Your previous links remain in\n"
    "┃    this Telegram chat history.\n"
    "┃\n"
    "┃ <b>Supported:</b>\n"
    "┃ JPG • JPEG • PNG • WEBP\n"
    "┃\n"
    "┃  No separate account history or\n"
    "┃  database is required.\n"
    "┃\n"
    "╰━━━━━━━━━━━━━━━━━━━━╯"
)


PROCESSING_TEXT = (
    "╭━━━「 ⚡ <b>PROCESSING</b> 」━━━╮\n"
    "┃\n"
    "┃  Your image is being processed.\n"
    "┃\n"
    "┃  ⏳ <i>Please wait...</i>\n"
    "┃\n"
    "╰━━━━━━━━━━━━━━━━━━━━╯"
)


DOWNLOAD_FAILED_TEXT = (
    "╭━━━「 ❌ <b>DOWNLOAD FAILED</b> 」━━━╮\n"
    "┃\n"
    "┃  We couldn't download your image.\n"
    "┃\n"
    "┃  Please send the image again.\n"
    "┃\n"
    "╰━━━━━━━━━━━━━━━━━━━━━━━━╯"
)


UPLOAD_FAILED_TEXT = (
    "╭━━━「 ❌ <b>UPLOAD FAILED</b> 」━━━╮\n"
    "┃\n"
    "┃  We couldn't process your image.\n"
    "┃\n"
    "┃  Please try again.\n"
    "┃\n"
    "╰━━━━━━━━━━━━━━━━━━━━━━━━╯"
)


IMAGE_ONLY_TEXT = (
    "╭━━━「 ⚠️ <b>IMAGE REQUIRED</b> 」━━━╮\n"
    "┃\n"
    "┃  Please send an image to continue.\n"
    "┃\n"
    "┃  Supported formats:\n"
    "┃  JPG • JPEG • PNG • WEBP\n"
    "┃\n"
    "╰━━━━━━━━━━━━━━━━━━━━━━━━╯"
)


READY_TEXT = (
    "╭━━━「 🖼️ <b>READY</b> 」━━━╮\n"
    "┃\n"
    "┃  Send your image now.\n"
    "┃\n"
    "┃  ⚡ <i>Your direct link will be\n"
    "┃  generated automatically.</i>\n"
    "┃\n"
    "╰━━━━━━━━━━━━━━━━━━━━╯"
)


# =========================================================
# KEYBOARDS
# =========================================================

def main_keyboard() -> InlineKeyboardMarkup:

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


def help_keyboard() -> InlineKeyboardMarkup:

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


def result_keyboard(
    image_url: str,
) -> InlineKeyboardMarkup:

    return InlineKeyboardMarkup(
        [
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
    )


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    if not update.message:
        return

    await update.message.reply_text(
        WELCOME_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(),
    )


# =========================================================
# HELP COMMAND
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    if not update.message:
        return

    await update.message.reply_text(
        HELP_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=help_keyboard(),
    )


# =========================================================
# CALLBACK BUTTONS
# =========================================================

async def button_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    query = update.callback_query

    if not query:
        return

    await query.answer()

    action = query.data

    # ---------------------------------------------
    # BACK
    # ---------------------------------------------

    if action == "back":

        await query.edit_message_text(
            WELCOME_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard(),
        )

        return

    # ---------------------------------------------
    # HELP
    # ---------------------------------------------

    if action == "help":

        await query.edit_message_text(
            HELP_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=help_keyboard(),
        )

        return

    # ---------------------------------------------
    # UPLOAD
    # ---------------------------------------------

    if action == "upload":

        await query.edit_message_text(
            READY_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=help_keyboard(),
        )

        return


# =========================================================
# IMAGE HANDLER
# =========================================================

async def handle_image(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    message = update.message

    if not message:
        return

    if not message.photo:
        return

    user = message.from_user

    if not user:
        return

    # ---------------------------------------------
    # PROCESSING MESSAGE
    # ---------------------------------------------

    processing = await message.reply_text(
        PROCESSING_TEXT,
        parse_mode=ParseMode.HTML,
    )

    buffer = BytesIO()

    # ---------------------------------------------
    # DOWNLOAD FROM TELEGRAM
    # ---------------------------------------------

    try:

        # Telegram photo list:
        # smallest -> largest
        photo = message.photo[-1]

        telegram_file = await context.bot.get_file(
            photo.file_id
        )

        await telegram_file.download_to_memory(
            buffer
        )

        buffer.seek(0)

        LOGGER.info(
            "Image downloaded | user=%s",
            user.id,
        )

    except TelegramError:

        LOGGER.exception(
            "Telegram image download failed"
        )

        await processing.edit_text(
            DOWNLOAD_FAILED_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=help_keyboard(),
        )

        return

    except Exception:

        LOGGER.exception(
            "Unexpected image download error"
        )

        await processing.edit_text(
            DOWNLOAD_FAILED_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=help_keyboard(),
        )

        return

    # ---------------------------------------------
    # CLOUDINARY UPLOAD
    # ---------------------------------------------

    try:

        LOGGER.info(
            "Uploading image | user=%s",
            user.id,
        )

        result = await asyncio.to_thread(
            upload_to_cloudinary,
            buffer,
        )

        image_url = result.get(
            "secure_url"
        )

        if (
            not isinstance(image_url, str)
            or not image_url.startswith(
                "https://"
            )
        ):
            raise ValueError(
                "Cloudinary did not return "
                "a valid HTTPS URL."
            )

        LOGGER.info(
            "Cloudinary upload successful | user=%s",
            user.id,
        )

    except Exception:

        LOGGER.exception(
            "Cloudinary upload failed"
        )

        await processing.edit_text(
            UPLOAD_FAILED_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=help_keyboard(),
        )

        return

    # ---------------------------------------------
    # SUCCESS MESSAGE
    # ---------------------------------------------

    safe_url = html.escape(
        image_url
    )

    success_text = (
        "╭━━━「 ✅ <b>IMAGE READY</b> 」━━━╮\n"
        "┃\n"
        "┃  <b>Your direct image link is ready.</b>\n"
        "┃\n"
        "┃  🔗 <b>DIRECT URL</b>\n"
        "┃\n"
        "┃  <code>"
        + safe_url
        + "</code>\n"
        "┃\n"
        "┃  ⚡ Fast Processing\n"
        "┃  ☁️ Cloud Hosted\n"
        "┃  🔒 Secure HTTPS\n"
        "┃\n"
        "┃  <i>This link is kept in your\n"
        "┃  Telegram chat history.</i>\n"
        "┃\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯"
    )

    try:

        await processing.edit_text(
            success_text,
            parse_mode=ParseMode.HTML,
            reply_markup=result_keyboard(
                image_url
            ),
        )

        LOGGER.info(
            "Result sent successfully | user=%s",
            user.id,
        )

    except TelegramError:

        LOGGER.exception(
            "Failed to edit result message"
        )


# =========================================================
# NON-IMAGE MESSAGES
# =========================================================

async def unsupported_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    if not update.message:
        return

    await update.message.reply_text(
        IMAGE_ONLY_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=help_keyboard(),
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    error = context.error

    if isinstance(error, Conflict):

        LOGGER.error(
            "Another bot instance is already "
            "polling this token."
        )

    else:

        LOGGER.exception(
            "Unhandled Telegram error",
            exc_info=error,
        )


# =========================================================
# APPLICATION
# =========================================================

def build_application(
    settings: dict[str, str],
) -> Application:

    application = (
        Application
        .builder()
        .token(
            settings["BOT_TOKEN"]
        )
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

    # Image
    application.add_handler(
        MessageHandler(
            filters.PHOTO,
            handle_image,
        )
    )

    # Inline buttons
    application.add_handler(
        CallbackQueryHandler(
            button_callback
        )
    )

    # Everything else
    application.add_handler(
        MessageHandler(
            filters.ALL,
            unsupported_message,
        )
    )

    # Errors
    application.add_error_handler(
        error_handler
    )

    return application


# =========================================================
# MAIN
# =========================================================

def main() -> None:

    LOGGER.info(
        "========================================"
    )

    LOGGER.info(
        "Starting ZEE BOTS"
    )

    LOGGER.info(
        "Firebase: DISABLED"
    )

    LOGGER.info(
        "Database History: DISABLED"
    )

    LOGGER.info(
        "Telegram Chat History: ENABLED"
    )

    LOGGER.info(
        "========================================"
    )

    # Render HTTP server
    start_http_server()

    # ---------------------------------------------
    # Environment
    # ---------------------------------------------

    try:

        settings = get_environment()

        LOGGER.info(
            "Environment configuration loaded"
        )

    except RuntimeError:

        LOGGER.exception(
            "Environment configuration error"
        )

        raise SystemExit(1)

    # ---------------------------------------------
    # Cloudinary
    # ---------------------------------------------

    try:

        configure_cloudinary(
            settings
        )

    except Exception:

        LOGGER.exception(
            "Cloudinary configuration failed"
        )

        raise SystemExit(1)

    # ---------------------------------------------
    # Telegram Application
    # ---------------------------------------------

    try:

        application = build_application(
            settings
        )

        LOGGER.info(
            "Telegram application created"
        )

    except Exception:

        LOGGER.exception(
            "Failed to create Telegram application"
        )

        raise SystemExit(1)

    # ---------------------------------------------
    # Start Bot
    # ---------------------------------------------

    try:

        LOGGER.info(
            "ZEE BOTS is starting polling..."
        )

        application.run_polling(
            drop_pending_updates=True
        )

    except Conflict:

        LOGGER.error(
            "Another bot instance is already "
            "polling this token."
        )

        raise SystemExit(1)

    except KeyboardInterrupt:

        LOGGER.info(
            "Bot stopped manually"
        )

    except Exception:

        LOGGER.exception(
            "Bot stopped unexpectedly"
        )

        raise SystemExit(1)


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()
