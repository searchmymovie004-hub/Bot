import os
import logging
from io import BytesIO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import cloudinary
import cloudinary.uploader

BOT_TOKEN = os.getenv('BOT_TOKEN')
CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME')
CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY')
CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')
CLOUDINARY_UPLOAD_PRESET = os.getenv('CLOUDINARY_UPLOAD_PRESET', 'Risham')

if not BOT_TOKEN:
    raise RuntimeError('BOT_TOKEN is missing')
for key, value in {
    'CLOUDINARY_CLOUD_NAME': CLOUDINARY_CLOUD_NAME,
    'CLOUDINARY_API_KEY': CLOUDINARY_API_KEY,
    'CLOUDINARY_API_SECRET': CLOUDINARY_API_SECRET,
}.items():
    if not value:
        raise RuntimeError(f'{key} is missing')

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

WELCOME = '''<blockquote>╭───「 🖼️ IMAGE LINK 」───╮
│
│  <b>Welcome!</b>
│
│  Turn your image into a clean
│  direct image link in seconds.
│
│  ⚡ Fast • 🔗 Direct • ✨ Simple
│
╰────────────────────────╯</blockquote>

<b>Send me an image to get started.</b>'''

HELP = '''<blockquote>╭───「 ℹ️ HOW IT WORKS 」───╮
│
│  1️⃣ Send an image
│  2️⃣ Wait for the upload
│  3️⃣ Get your direct link
│
╰────────────────────────╯</blockquote>

<b>Supported:</b> JPG • JPEG • PNG • WEBP • GIF

<blockquote>🔒 Your API credentials stay on the server.</blockquote>'''

ERROR = '''<blockquote>╭───「 ⚠️ INVALID FILE 」───╮
│
│  Please send an <b>image only</b>.
│
│  JPG • PNG • WEBP • GIF
│
╰────────────────────────╯</blockquote>'''

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton('ℹ️ Help', callback_data='help')]]
    await update.message.reply_text(
        WELCOME,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP, parse_mode=ParseMode.HTML)

async def image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    photo = message.photo[-1]
    status = await message.reply_text(
        '<blockquote>╭───「 ⏳ PROCESSING 」───╮\n│\n│  Uploading your image…\n│\n╰────────────────────────╯</blockquote>',
        parse_mode=ParseMode.HTML,
    )
    try:
        tg_file = await context.bot.get_file(photo.file_id)
        buffer = BytesIO()
        await tg_file.download_to_memory(buffer)
        buffer.seek(0)

        result = cloudinary.uploader.upload(
            buffer,
            resource_type='image',
            folder='image_to_direct_link',
            upload_preset=CLOUDINARY_UPLOAD_PRESET,
        )
        url = result.get('secure_url') or result.get('url')
        if not url:
            raise RuntimeError('No URL returned')

        keyboard = [
            [InlineKeyboardButton('🌐 Open Image', url=url)],
            [InlineKeyboardButton('🖼️ Upload Another', callback_data='again')],
        ]
        text = f'''<blockquote>╭───「 ✅ IMAGE READY 」───╮
│
│  Your image is ready.
│
│  🔗 <b>Direct Image Link</b>
│
╰────────────────────────╯</blockquote>

<code>{url}</code>

<blockquote>⚡ Fast image hosting • Clean direct URL</blockquote>'''
        await status.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as exc:
        logger.exception('Upload failed: %s', exc)
        await status.edit_text(
            '<blockquote>╭───「 ❌ UPLOAD FAILED 」───╮\n│\n│  Something went wrong while\n│  processing your image.\n│\n│  Please try again.\n│\n╰────────────────────────╯</blockquote>',
            parse_mode=ParseMode.HTML,
        )

async def non_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(ERROR, parse_mode=ParseMode.HTML)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'help':
        await query.message.reply_text(HELP, parse_mode=ParseMode.HTML)
    elif query.data == 'again':
        await query.message.reply_text(
            '<blockquote>╭───「 🖼️ READY 」───╮\n│\n│  Send another image.\n│\n╰────────────────────╯</blockquote>',
            parse_mode=ParseMode.HTML,
        )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_cmd))
    app.add_handler(MessageHandler(filters.PHOTO, image_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, non_image))
    logger.info('Bot started')
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
