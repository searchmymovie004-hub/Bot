import os
import re
import logging
import asyncio
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ChatJoinRequest
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, CallbackQueryHandler, ChatJoinRequestHandler, filters

# ലോഗിംഗ് സെറ്റപ്പ് ചെയ്യുക
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# കോൺഫിഗറേഷൻ വിവരങ്ങൾ
TOKEN = "8973220687:AAF2cQWtacCPmIW9rQA2WP8PVD-aajZJHTc"
CHANNEL_ID = -1004332383599        # മെയിൻ പ്രൈവറ്റ് ചാനൽ ഐഡി
BACKUP_CHANNEL_ID = -1004433067284   # ബാക്ക്അപ്പ് ചാനൽ ഐഡി (യൂസർമാർക്ക് ഫയൽ അയക്കുന്നത് ഇവിടെ നിന്നാണ്)
ADMIN_USER_ID = 7199304293
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
    
    cleaned = re.sub(r'@[^\s]+', '', caption)
    cleaned = re.sub(r'https?://\S+|www\.\S+', '', cleaned)
    cleaned = re.sub(r't\.me/\S+', '', cleaned, flags=re.IGNORECASE)
    
    cleaned = '\n'.join([line.strip() for line in cleaned.splitlines() if line.strip()])
    
    if not cleaned:
        return "🎬 New Movie Added!"
        
    return cleaned

# --- ഫയൽ സൈസ് കണക്കാക്കാനുള്ള ഫങ്ഷൻ ---
def get_file_size(message):
    size_bytes = 0
    if message.document:
        size_bytes = message.document.file_size or 0
    elif message.video:
        size_bytes = message.video.file_size or 0
    
    if size_bytes == 0:
        return "Unknown Size"
    
    size_mb = size_bytes / (1024 * 1024)
    if size_mb >= 1024:
        return f"{size_mb / 1024:.2f} GB"
    else:
        return f"{size_mb:.1f} MB"

# --- 3. Auto Accept Join Requests ---
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

    if chat.type == "private":
        # അഡ്മിൻ ആണ് ഫയൽ അയക്കുന്നതെങ്കിൽ (ID: 7199304293)
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
                    
                    # 2. ബാക്ക്അപ്പ് ചാനലിലേക്ക് കോപ്പി ചെയ്യുന്നു (ഇവിടെ നിന്നാണ് പിന്നീട് യൂസർമാർക്ക് ഫയൽ നൽകുന്നത്)
                    if sent_msg:
                        backup_msg = await context.bot.copy_message(
                            chat_id=BACKUP_CHANNEL_ID,
                            from_chat_id=CHANNEL_ID,
                            message_id=sent_msg.message_id
                        )
                        
                        # ഡാറ്റാബേസിൽ ഫയൽ സേവ് ചെയ്യുമ്പോൾ ബാക്ക്അപ്പ് ചാനലിലെ message_id ആണ് സ്റ്റോർ ചെയ്യുന്നത്
                        if 'movies_db' not in context.bot_data:
                            context.bot_data['movies_db'] = []
                        
                        movie_name = cleaned_cap.splitlines()[0] if cleaned_cap else "Unknown Movie"
                        file_size = get_file_size(sent_msg)
                        
                        context.bot_data['movies_db'].append({
                            'name': movie_name,
                            'size': file_size,
                            'message_id': backup_msg.message_id  # ബാക്ക്അപ്പ് ചാനൽ ഐഡി വഴിയുള്ള മെസ്സേജ് ഐഡി
                        })
                        
                    await message.reply_text("✨ Success! Movie uploaded to channels and added to search database.")
                
                except Exception as e:
                    logger.error(f"Error sending to channel: {e}")
                    await message.reply_text("❌ Error: Failed to upload file. Check bot admin rights in both channels.")
            else:
                await message.reply_text("👋 Hello Admin! Send movie files/posters here to upload.")
        
        else:
            # സാധാരണ യൂസേഴ്സ് മൂവി പേര് ചോദിച്ചു വരുമ്പോൾ
            query_text = message.text
            if not query_text:
                return
            
            movies_db = context.bot_data.get('movies_db', [])
            matched_movies = [m for m in movies_db if query_text.lower() in m['name'].lower()]
            
            keyboard = [[InlineKeyboardButton("📢 Join Main Channel", url=MAIN_CHANNEL_LINK)]]
            
            if matched_movies:
                context.user_data['search_results'] = matched_movies
                context.user_data['search_query'] = query_text
                await send_movie_page(update, context, matched_movies, page=0)
            else:
                reply_markup = InlineKeyboardMarkup(keyboard)
                await message.reply_text(
                    "❌ Sorry, no movies found matching your search.\n\nPlease join our main channel for more updates:",
                    reply_markup=reply_markup
                )

# --- പേജിനേഷനും ബട്ടണുകളും ഹാൻഡിൽ ചെയ്യാൻ ---
async def send_movie_page(update_or_query, context, movies, page=0):
    items_per_page = 5
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    current_movies = movies[start_idx:end_idx]
    
    keyboard = []
    for m in current_movies:
        btn_text = f"📥 {m['name']} ({m['size']})"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"get_mov_{m['message_id']}")])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Back", callback_data=f"page_{page-1}"))
    if end_idx < len(movies):
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
        
    keyboard.append([InlineKeyboardButton("📢 Join Main Channel", url=MAIN_CHANNEL_LINK)])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"🎬 Search Results (Page {page+1}):\nSelect your movie below:"
    
    if isinstance(update_or_query, Update) and update_or_query.message:
        await update_or_query.message.reply_text(text, reply_markup=reply_markup)
    elif hasattr(update_or_query, 'edit_message_text'):
        await update_or_query.edit_message_text(text, reply_markup=reply_markup)

# --- ബട്ടൺ ക്ലിക്കുകൾ ഹാൻഡിൽ ചെയ്യുന്ന ഭാഗം (ബാക്ക്അപ്പ് ചാനലിൽ നിന്ന് ഫയൽ കൊടുക്കുന്നു) ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data.startswith("page_"):
        page = int(data.split("_")[1])
        matched_movies = context.user_data.get('search_results', [])
        await send_movie_page(query, context, matched_movies, page=page)
        
    elif data.startswith("get_mov_"):
        msg_id = int(data.split("_")[2])
        try:
            # യൂസർക്ക് ഫയൽ ഫോർവേഡ് ചെയ്തു നൽകുന്നത് ബാക്ക്അപ്പ് ചാനലിൽ നിന്നാണ് (-1004433067284)
            forwarded = await context.bot.copy_message(
                chat_id=query.message.chat_id,
                from_chat_id=BACKUP_CHANNEL_ID,
                message_id=msg_id
            )
            
            # 5 മിനിറ്റിനു ശേഷം ഓട്ടോ ഡിലീറ്റ് ആകാൻ
            asyncio.create_task(delete_after_delay(context, query.message.chat_id, forwarded.message_id, 300))
            
            await query.message.reply_text("⚡ Here is your movie! Note: This file will auto-delete in 5 minutes due to copyright.")
        except Exception as e:
            logger.error(f"Error sending file via button from backup channel: {e}")
            await query.message.reply_text("❌ Sorry, failed to fetch this movie file.")

async def delete_after_delay(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, delay: int):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.error(f"Failed to auto-delete: {e}")

# സ്റ്റാർട്ട് കമാൻഡ്
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📢 Join Main Channel", url=MAIN_CHANNEL_LINK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Welcome! Send me the name of the movie you want, and I will find it for you.",
        reply_markup=reply_markup
    )

def main():
    keep_alive()

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(ChatJoinRequestHandler(auto_accept))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    print("Bot is running and pulling files from Backup Channel...")
    application.run_polling()

if __name__ == '__main__':
    main()
