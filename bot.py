import os
import re
import logging
import asyncio
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ChatJoinRequest, CallbackQuery
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, ChatJoinRequestHandler, CallbackQueryHandler, filters

# ലോഗിംഗ് സെറ്റപ്പ്
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# കോൺഫിഗറേഷൻ വിവരങ്ങൾ
TOKEN = "8973220687:AAE-4JEQ_ND5zb7g0Y7Iuan4XN1ephfz1uw"
CHANNEL_ID = -1004332383599        # മെയിൻ പ്രൈവറ്റ് ചാനൽ ഐഡി
BACKUP_CHANNEL_ID = -1004433067284   # ബാക്ക്അപ്പ് ചാനൽ ഐഡി
ADMIN_USER_ID = 7199304293
MAIN_CHANNEL_LINK = "https://t.me/mfottupdates"

# --- 1. HTTP Web Service (Render-ന് വേണ്ടി) ---
app = Flask('')

@app.route('/')
def home():
    return "Movie Search Bot is running live!"

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
    return cleaned if cleaned else "🎬 New Movie Added!"

# --- 3. Auto Accept Join Requests ---
async def auto_accept(update: ChatJoinRequest, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.approve()
        logger.info(f"Approved join request for user: {update.from_user.id}")
    except Exception as e:
        logger.error(f"Failed to approve join request: {e}")

# --- 4. /admin കമാൻഡ് (അഡ്മിൻ പാനൽ ഓൺ ചെയ്യാൻ) ---
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id == ADMIN_USER_ID:
        context.user_data['admin_mode'] = True
        await update.message.reply_text(
            "🛠️ **Admin Panel Activated!**\n\n"
            "You can now send movie files/posters to upload them to the channels.\n"
            "To exit admin mode and use normal search, type `/exit`."
        )
    else:
        await update.message.reply_text("❌ You are not authorized to use this command.")

# --- 5. /exit കമാൻഡ് (അഡ്മിൻ മോഡ് ഓഫ് ചെയ്യാൻ) ---
async def exit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id == ADMIN_USER_ID:
        context.user_data['admin_mode'] = False
        await update.message.reply_text("🔒 **Admin Panel Closed.** Bot is back to normal search mode.")

# --- 6. മെസ്സേജുകൾ ഹാൻഡിൽ ചെയ്യുന്ന ഭാഗം ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    user = message.from_user
    chat = message.chat

    if chat.type == "private":
        # അഡ്മിൻ ആണോ എന്നും, അഡ്മിൻ മോഡ് ഓൺ ആണോ എന്നും പരിശോധിക്കുന്നു
        if user.id == ADMIN_USER_ID and context.user_data.get('admin_mode', False):
            if message.document or message.video or message.photo:
                caption = message.caption or message.text or ""
                cleaned_cap = clean_caption(caption)
                movie_name = cleaned_cap.splitlines()[0] if cleaned_cap else "Unknown Movie"

                try:
                    sent_msg = None
                    if message.photo:
                        sent_msg = await context.bot.send_photo(chat_id=CHANNEL_ID, photo=message.photo[-1].file_id, caption=cleaned_cap)
                    elif message.document:
                        sent_msg = await context.bot.send_document(chat_id=CHANNEL_ID, document=message.document.file_id, caption=cleaned_cap)
                    elif message.video:
                        sent_msg = await context.bot.send_video(chat_id=CHANNEL_ID, video=message.video.file_id, caption=cleaned_cap)
                    
                    if sent_msg:
                        # ബാക്ക്അപ്പ് ചാനലിലേക്ക് കോപ്പി ചെയ്യുന്നു
                        backup_msg = await context.bot.copy_message(
                            chat_id=BACKUP_CHANNEL_ID,
                            from_chat_id=CHANNEL_ID,
                            message_id=sent_msg.message_id
                        )
                        
                        # ഡാറ്റാബേസിൽ (bot_data) മൂവി സേവ് ചെയ്യുന്നു
                        if 'movies_db' not in context.bot_data:
                            context.bot_data['movies_db'] = []
                        
                        context.bot_data['movies_db'].append({
                            'name': movie_name,
                            'message_id': backup_msg.message_id
                        })
                        
                    await message.reply_text("✨ Success! Movie uploaded to channels and added to search database.")
                except Exception as e:
                    logger.error(f"Upload error: {e}")
                    await message.reply_text("❌ Error: Failed to upload file. Check bot admin permissions.")
            else:
                await message.reply_text("👋 Admin Mode is ON. Send any movie file/poster to upload, or type `/exit` to close.")
        
        else:
            # നോർമൽ യൂസർമാർക്കും (അഡ്മിൻ മോഡ് ഓഫ് ചെയ്ത സമയത്തെ അഡ്മിനും) മൂവി സെർച്ച് വർക്ക് ചെയ്യും
            query_text = message.text
            if not query_text or query_text.startswith("/"):
                return

            movies_db = context.bot_data.get('movies_db', [])
            matched_movies = [m for m in movies_db if query_text.lower() in m['name'].lower()]

            keyboard = [[InlineKeyboardButton("📢 Join Main Channel", url=MAIN_CHANNEL_LINK)]]
            
            if matched_movies:
                buttons = []
                for movie in matched_movies[:5]:
                    buttons.append([InlineKeyboardButton(f"📥 {movie['name']}", callback_data=f"get_{movie['message_id']}")])
                
                buttons.append([InlineKeyboardButton("📢 Join Main Channel", url=MAIN_CHANNEL_LINK)])
                reply_markup = InlineKeyboardMarkup(buttons)
                
                await message.reply_text(
                    f"🎬 Search Results for '{query_text}':\nSelect your movie below:",
                    reply_markup=reply_markup
                )
            else:
                reply_markup = InlineKeyboardMarkup(keyboard)
                await message.reply_text(
                    "❌ Sorry, no movies found matching your search.\n\nPlease join our main channel for more updates:",
                    reply_markup=reply_markup
                )

# --- 7. ബട്ടൺ ക്ലിക്ക് ചെയ്യുമ്പോൾ ഫയൽ അയച്ചുകൊടുക്കുന്ന ഭാഗം ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data.startswith("get_"):
        msg_id = int(data.split("_")[1])
        try:
            forwarded = await context.bot.copy_message(
                chat_id=query.message.chat.id,
                from_chat_id=BACKUP_CHANNEL_ID,
                message_id=msg_id
            )
            
            # 5 മിനിറ്റിനു ശേഷം ഓട്ടോ ഡിലീറ്റ് ചെയ്യാൻ
            asyncio.create_task(delete_after_delay(context, query.message.chat.id, forwarded.message_id, 300))
            
            await query.message.reply_text("⚡ Here is your movie! Note: This file will auto-delete in 5 minutes due to copyright.")
        except Exception as e:
            logger.error(f"Error sending file: {e}")
            await query.message.reply_text("❌ Failed to fetch movie file!")

async def delete_after_delay(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, delay: int):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.error(f"Auto-delete failed: {e}")

# സ്റ്റാർട്ട് കമാൻഡ്
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📢 Join Main Channel", url=MAIN_CHANNEL_LINK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Welcome! Send me the name of the movie you want to search, and I will find it for you.",
        reply_markup=reply_markup
    )

def main():
    keep_alive()
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("exit", exit_command))
    application.add_handler(ChatJoinRequestHandler(auto_accept))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.PRIVATE, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO | filters.DOCUMENT | filters.VIDEO & filters.PRIVATE, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))

    print("Movie Search Bot with Toggle Admin Panel is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
