import os
import base64
import threading
import logging
import requests

from flask import Flask
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing.")

if not IMGBB_API_KEY:
    raise RuntimeError("IMGBB_API_KEY environment variable is missing.")


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# FLASK SERVER FOR RENDER
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "ZEE BOTS Image Link Bot is running."


@app.route("/health")
def health():
    return "OK"


def run_flask():
    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
    )


# =========================================================
# TELEGRAM KEYBOARDS
# =========================================================

main_keyboard = ReplyKeyboardMarkup(
    [
        ["📤 Upload Image"],
        ["❓ Help"],
    ],
    resize_keyboard=True,
)

upload_keyboard = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(
                "🌐 Open Image",
                url="https://example.com",
            )
        ],
        [
            InlineKeyboardButton(
                "📤 Upload Another",
                callback_data="upload_another",
            )
        ],
    ]
)

help_keyboard = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data="back_home",
            )
        ]
    ]
)


# =========================================================
# IMGBB UPLOAD
# =========================================================

def upload_to_imgbb(image_data):
    """
    Upload image bytes to ImgBB.

    Returns:
        (image_url, None) on success
        (None, error_message) on failure
    """

    try:

        # Convert image bytes to Base64
        encoded_image = base64.b64encode(image_data).decode("utf-8")

        logger.info(
            "Uploading image to ImgBB | size=%s bytes",
            len(image_data),
        )

        response = requests.post(
            "https://api.imgbb.com/1/upload",
            data={
                "key": IMGBB_API_KEY,
                "image": encoded_image,
            },
            timeout=60,
        )

        logger.info(
            "ImgBB response status=%s",
            response.status_code,
        )

        logger.info(
            "ImgBB response body=%s",
            response.text[:2000],
        )

        # HTTP error
        if response.status_code != 200:

            return (
                None,
                f"ImgBB HTTP {response.status_code}: "
                f"{response.text[:500]}",
            )

        # Parse JSON
        try:
            result = response.json()

        except Exception:

            return (
                None,
                "ImgBB returned an invalid response."
            )

        # API success check
        if not result.get("success"):

            error = result.get("error")

            if error:
                return (
                    None,
                    f"ImgBB Error: {error}"
                )

            return (
                None,
                f"ImgBB upload failed: {result}"
            )

        data = result.get("data", {})

        # =================================================
        # Try all common ImgBB URL fields
        # =================================================

        image_url = data.get("url")

        if not image_url:
            image_url = data.get("display_url")

        if not image_url:

            image_object = data.get("image", {})

            if isinstance(image_object, dict):
                image_url = image_object.get("url")

        # =================================================
        # URL missing
        # =================================================

        if not image_url:

            return (
                None,
                "Upload succeeded but ImgBB did not return "
                "an image URL."
            )

        logger.info(
            "ImgBB upload successful | url=%s",
            image_url,
        )

        return image_url, None

    except requests.exceptions.Timeout:

        logger.exception("ImgBB timeout")

        return (
            None,
            "ImgBB request timed out."
        )

    except requests.exceptions.ConnectionError:

        logger.exception("ImgBB connection error")

        return (
            None,
            "Could not connect to ImgBB."
        )

    except requests.exceptions.RequestException as e:

        logger.exception("ImgBB request error")

        return (
            None,
            f"ImgBB request error: {str(e)}"
        )

    except Exception as e:

        logger.exception("Unexpected ImgBB error")

        return (
            None,
            f"Unexpected error: {str(e)}"
        )


# =========================================================
# START COMMAND
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = """
╭───「 🖼️ ZEE BOTS 」───╮

🚀 IMAGE → DIRECT LINK

Convert your Telegram image into
a direct HTTPS image link.

✨ Fast Upload
🔗 Direct Image URL
📱 Mobile Friendly
⚡ Simple & Free
🕘 Telegram chat keeps your links

Just send an image to begin.

╰────────────────────╯
"""

    await update.message.reply_text(
        text,
        reply_markup=main_keyboard,
    )


# =========================================================
# HELP
# =========================================================

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = """
╭───「 ❓ HELP 」───╮

📌 HOW TO USE

1️⃣ Send an image to this bot.

2️⃣ The bot uploads your image.

3️⃣ You receive a direct HTTPS
   image URL.

4️⃣ Use the URL anywhere you need.

━━━━━━━━━━━━━━━━━━

🖼️ Supported:
• Telegram Photos
• Image Documents
• JPG
• JPEG
• PNG
• WEBP
• GIF
• Other supported image formats

━━━━━━━━━━━━━━━━━━

🔒 No separate history system.

Your generated links remain available
inside your Telegram chat history.

╰──────────────────╯
"""

    await update.message.reply_text(
        text,
        reply_markup=help_keyboard,
    )


# =========================================================
# BUTTON CALLBACK
# =========================================================

async def button_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    # Upload another
    if query.data == "upload_another":

        await query.message.reply_text(
            "📤 Send your next image.",
            reply_markup=main_keyboard,
        )

    # Back
    elif query.data == "back_home":

        text = """
╭───「 🖼️ ZEE BOTS 」───╮

Ready to convert your image.

📤 Send an image to get
your direct image link.

╰────────────────────╯
"""

        await query.message.edit_text(text)

        await query.message.reply_text(
            "Choose an option:",
            reply_markup=main_keyboard,
        )


# =========================================================
# IMAGE HANDLER
# =========================================================

async def process_image(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    try:

        user = update.effective_user

        logger.info(
            "Image received | user=%s",
            user.id if user else "unknown",
        )

        # -------------------------------------------------
        # PHOTO
        # -------------------------------------------------

        if update.message.photo:

            # Highest resolution photo
            photo = update.message.photo[-1]

            telegram_file = await context.bot.get_file(
                photo.file_id
            )

        # -------------------------------------------------
        # IMAGE DOCUMENT
        # -------------------------------------------------

        elif update.message.document:

            document = update.message.document

            mime_type = document.mime_type or ""

            # Accept image MIME types
            if not mime_type.startswith("image/"):

                await update.message.reply_text(
                    "❌ Please send an image file only.",
                    reply_markup=main_keyboard,
                )

                return

            telegram_file = await context.bot.get_file(
                document.file_id
            )

        else:

            return

        # -------------------------------------------------
        # DOWNLOAD FROM TELEGRAM
        # -------------------------------------------------

        image_data = await telegram_file.download_as_bytearray()

        image_data = bytes(image_data)

        logger.info(
            "Image downloaded | user=%s | size=%s",
            user.id if user else "unknown",
            len(image_data),
        )

        # -------------------------------------------------
        # UPLOAD TO IMGBB
        # -------------------------------------------------

        status_message = await update.message.reply_text(
            "⏳ Uploading your image...\n\n"
            "Please wait a moment."
        )

        image_url, error = upload_to_imgbb(image_data)

        # -------------------------------------------------
        # FAILED
        # -------------------------------------------------

        if not image_url:

            logger.error(
                "UPLOAD FAILED | user=%s | error=%s",
                user.id if user else "unknown",
                error,
            )

            await status_message.edit_text(
                "╭───「 ❌ UPLOAD FAILED 」───╮\n"
                "\n"
                "Something went wrong while\n"
                "processing your image.\n"
                "\n"
                "Please try again later.\n"
                "\n"
                "╰────────────────────────╯"
            )

            return

        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        logger.info(
            "UPLOAD SUCCESS | user=%s | url=%s",
            user.id if user else "unknown",
            image_url,
        )

        # Delete loading message
        try:
            await status_message.delete()
        except Exception:
            pass

        # -------------------------------------------------
        # SUCCESS MESSAGE
        # -------------------------------------------------

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🌐 Open Image",
                        url=image_url,
                    )
                ],
                [
                    InlineKeyboardButton(
                        "📤 Upload Another",
                        callback_data="upload_another",
                    )
                ],
            ]
        )

        success_text = f"""
╭───「 ✅ UPLOAD COMPLETE 」───╮

🖼️ Your image is ready!

🔗 DIRECT IMAGE LINK

{image_url}

━━━━━━━━━━━━━━━━━━

⚡ Fast & Direct
🔒 No separate history database
💬 Link saved in your Telegram chat

╰────────────────────────────╯
"""

        await update.message.reply_text(
            success_text,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )

    except Exception as e:

        logger.exception(
            "IMAGE HANDLER ERROR"
        )

        try:

            await update.message.reply_text(
                "╭───「 ❌ ERROR 」───╮\n"
                "\n"
                "Unable to process this image.\n"
                "\n"
                "Please try another image.\n"
                "\n"
                "╰──────────────────╯",
                reply_markup=main_keyboard,
            )

        except Exception:
            pass


# =========================================================
# TEXT HANDLER
# =========================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    text = (update.message.text or "").strip()

    if text == "📤 Upload Image":

        await update.message.reply_text(
            """
╭───「 📤 UPLOAD IMAGE 」───╮

Send an image now.

I will convert it into
a direct HTTPS image link.

╰──────────────────────────╯
""",
            reply_markup=main_keyboard,
        )

    elif text == "❓ Help":

        await show_help(update, context)

    else:

        await update.message.reply_text(
            """
🖼️ Please send an image.

I will convert it into
a direct image URL.
""",
            reply_markup=main_keyboard,
        )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):

    logger.exception(
        "Telegram error:",
        exc_info=context.error,
    )


# =========================================================
# MAIN
# =========================================================

def main():

    logger.info("===================================")
    logger.info("ZEE BOTS IMAGE LINK BOT")
    logger.info("===================================")
    logger.info("Storage: ImgBB")
    logger.info("Firebase: DISABLED")
    logger.info("Database History: DISABLED")
    logger.info("Telegram Chat History: ENABLED")
    logger.info("===================================")

    # Start Flask
    flask_thread = threading.Thread(
        target=run_flask,
        daemon=True,
    )

    flask_thread.start()

    # Telegram application
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands
    application.add_handler(
        CommandHandler("start", start)
    )

    # Callback buttons
    application.add_handler(
        CallbackQueryHandler(button_callback)
    )

    # Photos
    application.add_handler(
        MessageHandler(
            filters.PHOTO,
            process_image,
        )
    )

    # Image documents
    application.add_handler(
        MessageHandler(
            filters.Document.IMAGE,
            process_image,
        )
    )

    # Text
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler,
        )
    )

    # Errors
    application.add_error_handler(
        error_handler
    )

    logger.info("Application started")

    # Polling
    application.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()
