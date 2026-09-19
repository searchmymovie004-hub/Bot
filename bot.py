import os
import re
import logging
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters

# ലോഗിംഗ് സെറ്റപ്പ് ചെയ്യുക
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# കോൺഫിഗറേഷൻ വിവരങ്ങൾ
TOKEN = "8973220687:AAHhU1cbD1ysEa4fIcfF0QTYYpW1xf3m2vg"
CHANNEL_ID = -1004332383599
MAIN_CHANNEL_LINK = "https://t.me/moviechannelsfree"

# --- 1. HTTP Web Service (Render-ന് വേണ്ടി) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running live!"

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_http_server)
    t.daemon = True
    t.start()

# --- 2. ക്യാപ്ഷൻ ക്ലീൻ ചെയ്യാനുള്ള ഫങ്ഷൻ ---
def clean_caption(caption: str) -> str:
    if not caption:
        return "🎬 New Movie Added!"
    
    # യൂസർഷണുകൾ (@username), ലിങ്കുകൾ (http/https/t.me), വെബ്‌സൈറ്റ് പേരുകൾ നീക്കം ചെയ്യാൻ
    cleaned = re.sub(r'@[^\s]+', '', caption)                    # യൂസർഷണുകൾ മാറ്റുന്നു
    cleaned = re.sub(r'https?://\S+|www\.\S+', '', cleaned)        # URL-കൾ മാറ്റുന്നു
    cleaned = re.sub(r't\.me/\S+', '', cleaned, flags=re.IGNORECASE) # Telegram ലിങ്കുകൾ മാറ്റുന്നു
    
    # അധികമുള്ള സ്പേസുകൾ ഒഴിവാക്കുക
    cleaned = '\n'.join([line.strip() for line in cleaned.splitlines() if line.strip()])
    
    if not cleaned:
        return "🎬 New Movie Added!"
        
    return cleaned

# --- 3. മെസ്സേജുകൾ ഹാൻഡിൽ ചെയ്യുന്ന ഭാഗം ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    user = message.from_user
    chat = message.chat

    # ബോട്ട് പ്രൈവറ്റ് ചാറ്റിലാണോ പ്രവർത്തിക്കുന്നത് എന്ന് നോക്കുക (ആരെങ്കിലും മൂവി ചോദിച്ചു വരുമ്പോൾ)
    if chat.type == "private":
        # അഡ്മിൻ ആണ് ഫയലുകൾ അയക്കുന്നതെങ്കിൽ ചാനലിലേക്ക് പോസ്റ്റ് ചെയ്യാം
        # (ഇവിടെ അഡ്മിൻ ഐഡി പരിശോധന ഒഴിവാക്കിയിരിക്കുന്നു, നിങ്ങൾക്ക് വേണമെങ്കിൽ അഡ്മിൻ ചെക്ക് വെക്കാം)
        
        # ഫയലോ പോസ്റ്ററോ ഡോക്യുമെന്റോ ആണോ എന്ന് പരിശോധിക്കുന്നു
        if message.document or message.video or message.photo:
            # മൾട്ടി ഫയൽ അപ്‌ലോഡിനായി മീഡിയ ഗ്രൂപ്പ് (Album) പിന്തുണയ്ക്കുന്നു
            caption = message.caption or message.text or ""
            cleaned_cap = clean_caption(caption)

            try:
                # ഫോട്ടോ (പോസ്റ്റർ) ആണെങ്കിൽ
                if message.photo:
                    photo_file_id = message.photo[-1].file_id
                    await context.bot.send_photo(
                        chat_id=CHANNEL_ID,
                        photo=photo_file_id,
                        caption=cleaned_cap
                    )
                # ഡോക്യുമെന്റ് അല്ലെങ്കിൽ വീഡിയോ ആണെങ്കിൽ
                elif message.document:
                    await context.bot.send_document(
                        chat_id=CHANNEL_ID,
                        document=message.document.file_id,
                        caption=cleaned_cap
                    )
                elif message.video:
                    await context.bot.send_video(
                        chat_id=CHANNEL_ID,
                        video=message.video.file_id,
                        caption=cleaned_cap
                    )
                
                await message.reply_text("✅ ഫയൽ/പോസ്റ്റർ വിജയകരമായി ചാനലിലേക്ക് ആഡ് ചെയ്തിരിക്കുന്നു!")
            except Exception as e:
                logger.error(f"Error sending to channel: {e}")
                await message.reply_text("❌ ഫയൽ ചാനലിലേക്ക് അയക്കുന്നതിൽ ചെറിയ തടസ്സമുണ്ടായി. ബോട്ട് ചാനലിൽ അഡ്മിൻ ആണെന്ന് ഉറപ്പുവരുത്തുക.")
        
        else:
            # സാധാരണ ടെക്സ്റ്റ് മെസ്സേജുകൾക്ക് (ആരെങ്കിലും മൂവി ചോദിച്ചു വന്നാൽ) മെയിൻ ചാനൽ ലിങ്ക് നൽകുക
            keyboard = [[InlineKeyboardButton("📢 Join Main Channel", url=MAIN_CHANNEL_LINK)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await message.reply_text(
                "👋 ഹലോ! നിങ്ങൾക്ക് മൂവികൾ ലഭിക്കാനും ജോയിൻ ചെയ്യാനും താഴെയുള്ള ഔദ്യോഗിക ചാനൽ സന്ദർശിക്കുക:",
                reply_markup=reply_markup
            )

# സ്റ്റാർട്ട് കമാൻഡ് ഹാൻഡ്ലർ
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📢 Join Main Channel", url=MAIN_CHANNEL_LINK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "സ്ഗതം! ഈ ബോട്ട് വഴി മൂവികൾ മാനേജ് ചെയ്യാം. കൂടുതൽ വിവരങ്ങൾക്ക് മെയിൻ ചാനൽ ജോയിൻ ചെയ്യുക:",
        reply_markup=reply_markup
    )

def main():
    # HTTP സർവർ ബാക്ക്ഗ്രൗണ്ടിൽ റൺ ചെയ്യുന്നു
    keep_alive()

    # ടെലിഗ്രാം ബോട്ട് ആപ്ലിക്കേഷൻ ബിൽഡ് ചെയ്യുന്നു
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    # എല്ലാത്തരം മീഡിയയും ടെക്സ്റ്റുകളും ഹാൻഡിൽ ചെയ്യാൻ
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    print("Bot is starting and running...")
    application.run_polling()

if __name__ == '__main__':
    main()
