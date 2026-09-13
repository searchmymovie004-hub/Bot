"""Telegram image-to-direct-link bot for ZEE BOTS."""

from __future__ import annotations

import asyncio
import html
import logging
import os
from io import BytesIO
from typing import Any

import cloudinary
import cloudinary.uploader
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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

LOGGER = logging.getLogger(__name__)

WELCOME_TEXT = (
    "╭───「 🖼️ <b>IMAGE LINK</b> 」───╮\n\n"
    "Welcome to <b>Image To Direct Image Link Convert Bot</b>.\n\n"
    "Send me any image and I'll convert it into a direct image link.\n\n"
    "⚡ Fast Processing\n"
    "🔗 Direct Image URL\n"
    "🖼️ High Quality\n"
    "🚀 Simple &amp; Easy\n\n"
    "╰────────────────────╯"
)
HELP_TEXT = (
    "╭───「 ℹ️ <b>HOW TO USE</b> 」───╮\n\n"
    "1️⃣ Send an image to this bot.\n\n"
    "2️⃣ Wait while the image is processed.\n\n"
    "3️⃣ The bot will return your direct image URL.\n\n"
    "4️⃣ Tap <b>Open Image</b> to view it.\n\n"
    "That's it.\n\n"
    "╰────────────────────╯"
)
PROCESSING_TEXT = (
    "╭───「 ⚡ <b>PROCESSING</b> 」───╮\n\n"
    "Your image is being processed...\n\n"
    "⏳ Please wait a moment.\n\n"
    "╰────────────────────╯"
)
READY_TEXT = (
    "╭───「 🖼️ <b>READY</b> 」───╮\n\n"
    "Send your next image.\n\n"
    "╰────────────────────╯"
)
IMAGE_ONLY_TEXT = (
    "╭───「 ⚠️ <b>IMAGE ONLY</b> 」───╮\n\n"
    "Please send an image to generate a direct image link.\n\n"
    "╰────────────────────╯"
)
UNSUPPORTED_TEXT = (
    "╭───「 ⚠️ <b>UNSUPPORTED</b> 」───╮\n\n"
    "This bot currently supports images only.\n\n"
    "Please send a JPG, JPEG, PNG or supported image.\n\n"
    "╰────────────────────╯"
)
DOWNLOAD_FAILED_TEXT = (
    "╭───「 ❌ <b>DOWNLOAD FAILED</b> 」───╮\n\n"
    "We couldn't download your image.\n\nPlease try again.\n\n"
    "╰────────────────────╯"
)
UPLOAD_FAILED_TEXT = (
    "╭───「 ❌ <b>UPLOAD FAILED</b> 」───╮\n\n"
    "Something went wrong while processing your image.\n\n"
    "Please try again later.\n\n"
    "╰────────────────────╯"
)


def required_environment() -> dict[str, str]:
    """Load and validate required settings without logging secret values."""
    names = (
        "BOT_TOKEN",
        "CLOUDINARY_CLOUD_NAME",
        "CLOUDINARY_API_KEY",
        "CLOUDINARY_API_SECRET",
    )
    values = {name: os.getenv(name, "").strip() for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError("Missing required environment variable(s): " + ", ".join(missing))
    return values


def configure_cloudinary(settings: dict[str, str]) -> None:
    cloudinary.config(
        cloud_name=settings["CLOUDINARY_CLOUD_NAME"],
        api_key=settings["CLOUDINARY_API_KEY"],
        api_secret=settings["CLOUDINARY_API_SECRET"],
        secure=True,
    )


def welcome_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("ℹ️ Help", callback_data="help")]]
    )


def result_keyboard(image_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🌐 Open Image", url=image_url)],
            [
                InlineKeyboardButton("🖼️ Upload Another", callback_data="upload_another"),
                InlineKeyboardButton("ℹ️ Help", callback_data="help"),
            ],
        ]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            WELCOME_TEXT, parse_mode=ParseMode.HTML, reply_markup=welcome_keyboard()
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.HTML)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if query.data == "help":
        await query.edit_message_text(HELP_TEXT, parse_mode=ParseMode.HTML)
    elif query.data == "upload_another":
        await query.edit_message_text(READY_TEXT, parse_mode=ParseMode.HTML)


def upload_to_cloudinary(buffer: BytesIO) -> dict[str, Any]:
    options: dict[str, Any] = {
        "resource_type": "image",
        "folder": "image_to_direct_link",
    }
    preset = os.getenv("CLOUDINARY_UPLOAD_PRESET", "").strip()
    if preset:
        options["upload_preset"] = preset
    return cloudinary.uploader.upload(buffer, **options)


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.photo:
        return
    processing = await message.reply_text(PROCESSING_TEXT, parse_mode=ParseMode.HTML)
    LOGGER.info("Image received")
    buffer = BytesIO()
    try:
        photo = message.photo[-1]
        telegram_file = await context.bot.get_file(photo.file_id)
        await telegram_file.download_to_memory(buffer)
        buffer.seek(0)
        LOGGER.info("Image downloaded")
    except TelegramError:
        LOGGER.exception("Telegram image download failed")
        await processing.edit_text(DOWNLOAD_FAILED_TEXT, parse_mode=ParseMode.HTML)
        return

    try:
        LOGGER.info("Uploading image")
        result = await asyncio.to_thread(upload_to_cloudinary, buffer)
        image_url = result.get("secure_url")
        if not isinstance(image_url, str) or not image_url.startswith("https://"):
            raise ValueError("Upload response did not contain a valid HTTPS secure_url")
        LOGGER.info("Image uploaded successfully")
    except Exception:
        LOGGER.exception("Image upload failed")
        await processing.edit_text(UPLOAD_FAILED_TEXT, parse_mode=ParseMode.HTML)
        return

    success_text = (
        "╭───「 ✅ <b>IMAGE READY</b> 」───╮\n\n"
        "Your direct image link is ready.\n\n"
        f"🔗 Direct URL:\n<code>{html.escape(image_url)}</code>\n\n"
        "⚡ Fast • Secure • Direct\n\n"
        "╰────────────────────╯"
    )
    await processing.edit_text(
        success_text, parse_mode=ParseMode.HTML, reply_markup=result_keyboard(image_url)
    )


async def unsupported_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        text = UNSUPPORTED_TEXT if update.message.effective_attachment else IMAGE_ONLY_TEXT
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if isinstance(context.error, Conflict):
        LOGGER.error("Another bot instance is already polling this token. Only one polling instance is allowed.")
    else:
        LOGGER.exception("Unhandled Telegram error", exc_info=context.error)


async def post_init(application: Application) -> None:
    # Remove stale webhooks before the single long-polling instance starts.
    await application.bot.delete_webhook(drop_pending_updates=True)
    LOGGER.info("Webhook removed; polling can start")


def build_application(settings: dict[str, str]) -> Application:
    application = Application.builder().token(settings["BOT_TOKEN"]).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.ALL, unsupported_message))
    application.add_error_handler(error_handler)
    return application


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
    )
    try:
        settings = required_environment()
        configure_cloudinary(settings)
        LOGGER.info("Configuration loaded")
        application = build_application(settings)
        LOGGER.info("Bot starting")
        application.run_polling(drop_pending_updates=True)
    except Conflict:
        LOGGER.error("Another bot instance is already polling this token. Only one polling instance is allowed.")
        raise SystemExit(1)
    except RuntimeError:
        LOGGER.exception("Configuration error")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
