import os
import re
import logging
import asyncio
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ChatJoinRequest
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, ChatJoinRequestHandler, filters

# ലോഗിംഗ് സെറ്റപ്പ് ചെയ്യുക
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# കോൺഫിഗറേഷൻ വിവരങ്ങൾ
TOKEN = "8973220687:AAGnS4YEi5vqGdaKnzg2yXlHSDQ-X2EqV8A"
CHANNEL_ID = -1004332383599        # മെയിൻ പ്രൈവറ്റ് ചാനൽ ഐഡി
BACKUP_CHANNEL_ID = -1004433067284   # ബാക്ക്അപ്പ് ചാനൽ ഐഡി (പഴയ ഫയലുകൾ സേവ് ആയി കിടക്കുന്നത് ഇവിടെയാണ്)
ADMIN_USER_ID = 7199304293
MAIN_CHANNEL_LINK = "https://t.me/mfottupdates"

# ഇവിടെ നിങ്ങളുടെ String Session കോഡ് നേരിട്ട് നൽകാം (ENV-ൽ കൊടുക്കേണ്ടതില്ല)
SESSION_STRING = "BQJVPVgAwc3boJ7aTpurbBFc0Fr12QKMVkCkT1dQ6QBi25nJzCrS0Vvg1YxNPisH8WR2mnUEYTGGRk4WVlu6Ydv69eFO-WMKIfL13kQBok3jJyHmDWEF4qnqUXOQXbsnjQNoVoSDEjdxd8AxUApcAV-d1YPTlVvXhdVd-_NNCCNQ--qFL7FrZtGPi1kCklzS-OEaByn8O9PIn4b-Gw9WQGEOik5KMJ4q_-GjS-oWu7EvjmZJt3V_nhF4f7TAKbayGhzbxqu6RwB31SP5bSL8CdomaV7n5v3WA-QhzGBGDjgFghjA3kkdfhbwYDNWcZAlqEMANzg6AW1jvRBzc_ZoEulO67pXlAAAAAGtHKplAA"

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
    
    cleaned = re.sub(r'@[^\s]+', '', caption)
    cleaned = re.sub(r'https?://\S+|www\.\S+', '', cleaned)
    cleaned = re.sub(r't\.me/\S+', '', cleaned, flags=re.IGNORECASE)
    
    cleaned = '\n'.join([line.strip() for line in cleaned.splitlines() if line.strip()])
    
    if not cleaned:
        return "🎬 New Movie Added!"
        
    return cleaned

# --- 3. Auto Accept Join Requests for Private Channel ---
async def auto_accept(update: ChatJoinRequest, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.approve()
        logger.info(f"Approved join request for user: {update.from_user.id}")
    except Exception as e:
        logger.error(f"Failed to approve join request: {e}")

# --- 4. മെസ്സേജുകൾ ഹാൻഡിൽ ചെയ്യുന്ന ഭാഗം ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    user = message.from_user
    chat = message.chat

    # ബോട്ട് പ്രൈവറ്റ് ചാറ്റിലാണോ പ്രവർത്തിക്കുന്നത് എന്ന് നോക്കുക
    if chat.type == "private":
        
        # ഫയൽ അപ്‌ലോഡ് ചെയ്യാൻ ശ്രമിക്കുന്നത് അഡ്മിൻ ആണോ എന്ന് പരിശോധിക്കുന്നു (ID: 7199304293)
        if user.id == ADMIN_USER_ID:
            if message.document or message.video or message.photo:
                caption = message.caption or message.text or ""
                cleaned_cap = clean_caption(caption)

                try:
                    sent_msg = None
                    # 1. മെയിൻ പ്രൈവറ്റ് ചാനലിലേക്ക് അയക്കുന്നു
                    if message.photo:
                        sent_msg = await context.bot.send_photo(
                            chat_id=CHANNEL_ID,
                            photo=message.photo[-1].file_id,
                            caption=cleaned_cap
                        )
                    elif message.document:
                        sent_msg = await context.bot.send_document(
                            chat_id=CHANNEL_ID,
                            document=message.document.file_id,
                            caption=cleaned_cap
                        )
                    elif message.video:
                        sent_msg = await context.bot.send_video(
                            chat_id=CHANNEL_ID,
                            video=message.video.file_id,
                            caption=cleaned_cap
                        )
                    
                    # 2. ബാക്ക്അപ്പ് ചാനലിലേക്ക് പുതിയ ഫയലും ഒപ്പം പഴയ ഫയലുകളും സുരക്ഷിതമായി ബാക്ക്അപ്പ് ചെയ്യുന്നു
                    if sent_msg:
                        backup_msg = await context.bot.copy_message(
                            chat_id=BACKUP_CHANNEL_ID,
                            from_chat_id=CHANNEL_ID,
                            message_id=sent_msg.message_id
                        )
                        
                        if 'all_movies' not in context.bot_data:
                            context.bot_data['all_movies'] = []
                        
                        context.bot_data['all_movies'].append(backup_msg)
                        context.bot_data['last_movie'] = backup_msg
                        
                    await message.reply_text("✨ Success! Movie has been added to your channels and safely backed up.")
                
                except Exception as e:
                    logger.error(f"Error sending to channel: {e}")
                    await message.reply_text("❌ Error: Failed to upload file. Please check if the bot is an admin in both channels.")
            else:
                await message.reply_text("👋 Hello Admin! Send any movie file/poster here to upload it to your channels.")
        
        else:
            # സാധാരണ യൂസേഴ്സ് മൂവി ചോദിച്ചു വരുമ്പോൾ (ബാക്ക്അപ്പ് ചാനലിൽ നിന്ന് ഫയൽ എടുക്കുന്നു)
            keyboard = [[InlineKeyboardButton("📢 Join Main Channel", url=MAIN_CHANNEL_LINK)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            last_movie = context.bot_data.get('last_movie')
            if last_movie:
                try:
                    # ബാക്ക്അപ്പ് ചാനലിൽ നിന്നാണ് യൂസർക്ക് ഫയൽ അയക്കുന്നത്
                    forwarded_msg = await context.bot.copy_message(
                        chat_id=chat.id,
                        from_chat_id=BACKUP_CHANNEL_ID,
                        message_id=last_movie.message_id
                    )
                    
                    # കോപ്പിറൈറ്റ് പ്രശ്നങ്ങൾ ഒഴിവാക്കാൻ യൂസർക്ക് അയച്ച ഫയൽ 5 മിനിറ്റിനു ശേഷം ഓട്ടോ ഡിലീറ്റ് ചെയ്യും
                    asyncio.create_task(delete_after_delay(context, chat.id, forwarded_msg.message_id, 300))
                    
                    await message.reply_text(
                        "🎬 Here is your requested movie! Note: This file will auto-delete in 5 minutes due to copyright policies.\n\n"
                        "Please join our main channel for more movies:",
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.error(f"Error sending movie to user: {e}")
                    await message.reply_text(
                        "👋 Welcome! Please join our main channel to access all movies:",
                        reply_markup=reply_markup
                    )
            else:
                await message.reply_text(
                    "👋 Welcome! Please join our main channel to get updates and watch movies:",
                    reply_markup=reply_markup
                )

# 5 മിനിറ്റിനു ശേഷം യൂസർക്ക് അയച്ച ഫയൽ മാത്രം ഡിലീറ്റ് ചെയ്യാൻ
async def delete_after_delay(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, delay: int):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.error(f"Failed to auto-delete user message: {e}")

# സ്റ്റാർട്ട് കമാൻഡ് ഹാൻഡ്ലർ
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📢 Join Main Channel", url=MAIN_CHANNEL_LINK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Welcome! This is your automated movie assistant bot.\n\n"
        "To get movies and regular updates, please join our official main channel below:",
        reply_markup=reply_markup
    )

def main():
    keep_alive()

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(ChatJoinRequestHandler(auto_accept))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    print("Bot is starting and running with backup channel feature...")
    application.run_polling()

if __name__ == '__main__':
    main()
