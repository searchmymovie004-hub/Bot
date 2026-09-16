import os
import logging
import threading
import urllib.parse
import requests

from flask import Flask

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ============================================================
# ZEE2AI CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

BOT_NAME = "ZEE2AI"

IMAGE_API = "https://image.pollinations.ai/prompt/"

PORT = int(os.getenv("PORT", "10000"))

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)

logger = logging.getLogger("ZEE2AI")

# ============================================================
# FLASK HTTP SERVER
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ZEE2AI</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                margin: 0;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                background: #0b0b0f;
                color: white;
                font-family: Arial, sans-serif;
                text-align: center;
            }

            .box {
                padding: 35px;
                border-radius: 24px;
                background: #15151c;
                box-shadow: 0 0 40px rgba(255,255,255,.08);
            }

            h1 {
                margin: 0 0 10px;
                font-size: 34px;
            }

            p {
                color: #aaa;
            }

            .status {
                margin-top: 20px;
                padding: 12px 20px;
                border-radius: 30px;
                background: #20202a;
                display: inline-block;
            }
        </style>
    </head>

    <body>
        <div class="box">
            <h1>✦ ZEE2AI ✦</h1>
            <p>AI Image Generator</p>
            <div class="status">🟢 Bot Online</div>
        </div>
    </body>
    </html>
    """


@app.route("/health")
def health():
    return {
        "status": "online",
        "bot": "ZEE2AI"
    }


def run_http_server():
    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        use_reloader=False
    )


# ============================================================
# MAIN MENU
# ============================================================

def main_menu():

    keyboard = [
        [
            InlineKeyboardButton(
                "🎨  CREATE IMAGE",
                callback_data="generate"
            )
        ],
        [
            InlineKeyboardButton(
                "📐 IMAGE SIZE",
                callback_data="size"
            ),
            InlineKeyboardButton(
                "ℹ️ HELP",
                callback_data="help"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# START
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["waiting_prompt"] = False

    text = (
        "╭━━━━━━━━━━━━━━━━━━━━╮\n"
        "       ✦ <b>Z E E 2 A I</b> ✦\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"

        "🎨 <b>AI IMAGE STUDIO</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"

        "Turn your imagination into images.\n"
        "Describe your idea and let ZEE2AI\n"
        "create it for you.\n\n"

        "✨ <b>FEATURES</b>\n"
        "• AI image generation\n"
        "• Multiple image formats\n"
        "• Premium interface\n"
        "• Simple & fast workflow\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <b>Tip:</b> Detailed prompts can\n"
        "give you more specific results.\n\n"

        "👇 <b>Select an option</b>"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=main_menu()
    )


# ============================================================
# GENERATE
# ============================================================

async def generate_button(update, context):

    query = update.callback_query
    await query.answer()

    context.user_data["waiting_prompt"] = True

    text = (
        "╭━━━━━━━━━━━━━━━━━━━━╮\n"
        "       🎨 <b>CREATE IMAGE</b>\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"

        "📝 Send a description of the image\n"
        "you want to generate.\n\n"

        "💡 <b>Example</b>\n"
        "<code>A cinematic Kerala village during "
        "monsoon, beautiful houses, dramatic sky, "
        "realistic photography, ultra detailed, 4K</code>\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n"
        "✦ Send your prompt"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "🔙 CANCEL",
                callback_data="back"
            )
        ]
    ]

    await query.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ============================================================
# SIZE
# ============================================================

async def size_button(update, context):

    query = update.callback_query
    await query.answer()

    current = context.user_data.get(
        "size",
        "1024x1024"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "⬜ 1:1",
                callback_data="size_1024_1024"
            )
        ],
        [
            InlineKeyboardButton(
                "🖼 16:9",
                callback_data="size_1280_720"
            ),
            InlineKeyboardButton(
                "📱 9:16",
                callback_data="size_720_1280"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 BACK",
                callback_data="back"
            )
        ]
    ]

    text = (
        "╭━━━━━━━━━━━━━━━━━━━━╮\n"
        "       📐 <b>IMAGE SIZE</b>\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"

        f"Current: <code>{current}</code>\n\n"

        "Choose your preferred format."
    )

    await query.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ============================================================
# SIZE SELECT
# ============================================================

async def size_select(update, context):

    query = update.callback_query
    await query.answer("Size selected ✓")

    data = query.data

    if data == "size_1024_1024":
        width, height = 1024, 1024

    elif data == "size_1280_720":
        width, height = 1280, 720

    elif data == "size_720_1280":
        width, height = 720, 1280

    else:
        return

    context.user_data["width"] = width
    context.user_data["height"] = height
    context.user_data["size"] = f"{width}x{height}"

    await query.message.reply_text(
        "╭━━━━━━━━━━━━━━━━━━━━╮\n"
        "       ✅ <b>SIZE UPDATED</b>\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"

        f"📐 <code>{width} × {height}</code>\n\n"
        "Your next image will use this format.",
        parse_mode="HTML",
        reply_markup=main_menu()
    )


# ============================================================
# HELP
# ============================================================

async def help_button(update, context):

    query = update.callback_query
    await query.answer()

    text = (
        "╭━━━━━━━━━━━━━━━━━━━━╮\n"
        "          ℹ️ <b>HELP</b>\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"

        "🎨 <b>CREATE IMAGE</b>\n"
        "Tap the button and send your prompt.\n\n"

        "📝 <b>GOOD PROMPT</b>\n"
        "<code>Futuristic Kochi city at night, "
        "neon lights, cinematic, realistic, "
        "highly detailed</code>\n\n"

        "📐 <b>AVAILABLE SIZES</b>\n"
        "• 1:1 Square\n"
        "• 16:9 Landscape\n"
        "• 9:16 Portrait\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n"
        "✦ Powered by ZEE2AI"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "🔙 BACK",
                callback_data="back"
            )
        ]
    ]

    await query.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ============================================================
# BACK
# ============================================================

async def back_button(update, context):

    query = update.callback_query
    await query.answer()

    context.user_data["waiting_prompt"] = False

    await query.message.reply_text(
        "╭━━━━━━━━━━━━━━━━━━━━╮\n"
        "       ✦ <b>ZEE2AI</b> ✦\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"

        "🏠 <b>Main Menu</b>\n\n"
        "Ready to create something?",
        parse_mode="HTML",
        reply_markup=main_menu()
    )


# ============================================================
# IMAGE URL
# ============================================================

def create_image_url(prompt, width, height):

    encoded = urllib.parse.quote(
        prompt,
        safe=""
    )

    return (
        IMAGE_API
        + encoded
        + f"?width={width}"
        + f"&height={height}"
        + "&nologo=true"
    )


# ============================================================
# GENERATE IMAGE
# ============================================================

async def handle_prompt(update, context):

    if not update.message:
        return

    prompt = update.message.text.strip()

    if not context.user_data.get(
        "waiting_prompt",
        False
    ):
        await update.message.reply_text(
            "👋 Please select <b>CREATE IMAGE</b> first.",
            parse_mode="HTML",
            reply_markup=main_menu()
        )
        return

    if len(prompt) < 3:
        await update.message.reply_text(
            "⚠️ Please enter a more detailed prompt."
        )
        return

    if len(prompt) > 1000:
        await update.message.reply_text(
            "⚠️ Prompt is too long.\n"
            "Please keep it below 1000 characters."
        )
        return

    context.user_data["waiting_prompt"] = False

    width = context.user_data.get(
        "width",
        1024
    )

    height = context.user_data.get(
        "height",
        1024
    )

    loading = await update.message.reply_text(
        "╭━━━━━━━━━━━━━━━━━━━━╮\n"
        "       ✦ <b>ZEE2AI</b> ✦\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"

        "🎨 <b>Creating your image...</b>\n\n"

        "▰▰▰▰▰▰▱▱▱▱ 60%\n\n"

        "⏳ Please wait..."
    ,
        parse_mode="HTML"
    )

    try:

        await update.message.chat.send_action(
            action=ChatAction.UPLOAD_PHOTO
        )

        image_url = create_image_url(
            prompt,
            width,
            height
        )

        logger.info(
            "Generating image | user=%s",
            update.effective_user.id
        )

        response = requests.get(
            image_url,
            timeout=120
        )

        if response.status_code != 200:

            logger.error(
                "Image API error: %s",
                response.status_code
            )

            await loading.edit_text(
                "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                "       ❌ <b>FAILED</b>\n"
                "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"

                "The image service is currently\n"
                "unavailable.\n\n"

                "Please try again later.",
                parse_mode="HTML",
                reply_markup=main_menu()
            )

            return

        await update.message.reply_photo(
            photo=image_url,
            caption=(
                "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                "        ✦ <b>ZEE2AI</b> ✦\n"
                "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"

                "✨ <b>IMAGE GENERATED</b>\n\n"

                f"📐 Size: <code>{width}×{height}</code>\n"
                "🎨 AI Image Studio\n\n"

                "━━━━━━━━━━━━━━━━━━━━\n"
                "💎 Created with ZEE2AI"
            ),
            parse_mode="HTML"
        )

        await loading.delete()

        await update.message.reply_text(
            "✨ <b>Create another image?</b>",
            parse_mode="HTML",
            reply_markup=main_menu()
        )

    except requests.exceptions.Timeout:

        await loading.edit_text(
            "╭━━━━━━━━━━━━━━━━━━━━╮\n"
            "       ⏱️ <b>TIMEOUT</b>\n"
            "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"

            "The image service took too long.\n\n"
            "Please try again.",
            parse_mode="HTML",
            reply_markup=main_menu()
        )

    except Exception:

        logger.exception(
            "Image generation error"
        )

        await loading.edit_text(
            "╭━━━━━━━━━━━━━━━━━━━━╮\n"
            "       ❌ <b>ERROR</b>\n"
            "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"

            "Something went wrong.\n\n"
            "Please try again.",
            parse_mode="HTML",
            reply_markup=main_menu()
        )


# ============================================================
# TEXT
# ============================================================

async def text_handler(update, context):

    if context.user_data.get(
        "waiting_prompt",
        False
    ):
        await handle_prompt(
            update,
            context
        )
        return

    await update.message.reply_text(
        "╭━━━━━━━━━━━━━━━━━━━━╮\n"
        "       ✦ <b>ZEE2AI</b> ✦\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"

        "Use the button below to create\n"
        "your AI image.",
        parse_mode="HTML",
        reply_markup=main_menu()
    )


# ============================================================
# ERROR
# ============================================================

async def error_handler(update, context):

    logger.error(
        "Unhandled error:",
        exc_info=context.error
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is missing."
        )

    logger.info("=" * 50)
    logger.info("ZEE2AI")
    logger.info("AI IMAGE GENERATOR")
    logger.info("=" * 50)

    # HTTP server thread
    http_thread = threading.Thread(
        target=run_http_server,
        daemon=True
    )

    http_thread.start()

    logger.info(
        "HTTP server started on port %s",
        PORT
    )

    # Telegram application
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands
    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_button
        )
    )

    # Buttons
    application.add_handler(
        CallbackQueryHandler(
            generate_button,
            pattern="^generate$"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            size_button,
            pattern="^size$"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            help_button,
            pattern="^help$"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            back_button,
            pattern="^back$"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            size_select,
            pattern="^size_"
        )
    )

    # Text
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler
        )
    )

    application.add_error_handler(
        error_handler
    )

    logger.info("Telegram bot starting...")

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
