import os
import re
import logging
import asyncio
from flask import Flask
from threading import Thread
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ലോഗിംഗ് സെറ്റപ്പ്
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- കോൺഫിഗറേഷൻ വിവരങ്ങൾ ---
API_ID = int(os.getenv("API_ID", 39140696))
API_HASH = os.getenv("API_HASH", "64757b9724e7143c5cc554d7a776334b")
BOT_TOKEN = "8973220687:AAHIPnDWiITrgn7scOolBytJh8_Xqpvkhl0"

CHANNEL_ID = -1004433067284               # മെയിൻ പ്രൈവറ്റ് ചാനൽ ഐഡി
BACKUP_CHANNEL_ID = -1004433067284        # ബാക്ക്അപ്പ് ചാനൽ ഐഡി (യൂസർമാർക്ക് ഫയൽ നൽകുന്നത് ഇവിടെ നിന്നാണ്)
ADMIN_USER_ID = 7199304293
MAIN_CHANNEL_LINK = "https://t.me/moviechannelsfree"

SESSION_STRING = os.getenv("SESSION_STRING", "")
MOVIES_DB = []

# --- 1. HTTP Web Service (Render-ന് വേണ്ടി Flask സെറ്റപ്പ്) ---
app = Flask('')

@app.route('/')
def home():
    return "Movie Bot is running live!"

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_http_server)
    t.daemon = True
    t.start()

# --- 2. Pyrogram Client Initialization ---
if SESSION_STRING:
    bot = Client(
        "movie_bot_session",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING
    )
else:
    bot = Client(
        "movie_bot_session",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )

def clean_caption(caption: str) -> str:
    if not caption:
        return "🎬 New Movie Added!"
    cleaned = re.sub(r'@[^\s]+', '', caption)
    cleaned = re.sub(r'https?://\S+|www\.\S+', '', cleaned)
    cleaned = re.sub(r't\.me/\S+', '', cleaned, flags=re.IGNORECASE)
    cleaned = '\n'.join([line.strip() for line in cleaned.splitlines() if line.strip()])
    return cleaned if cleaned else "🎬 New Movie Added!"

def get_file_size(message):
    media = message.document or message.video
    if not media:
        return "Unknown Size"
    size_mb = media.file_size / (1024 * 1024)
    if size_mb >= 1024:
        return f"{size_mb / 1024:.2f} GB"
    else:
        return f"{size_mb:.1f} MB"

@bot.on_message(filters.private & filters.user(ADMIN_USER_ID) & (filters.document | filters.video | filters.photo))
async def handle_admin_upload(client, message):
    caption = message.caption or message.text or ""
    cleaned_cap = clean_caption(caption)
    
    try:
        # 1. മെയിൻ ചാനലിലേക്ക് അയക്കുന്നു
        sent_msg = await message.copy(chat_id=CHANNEL_ID, caption=cleaned_cap)
        
        # 2. ബാക്ക്അപ്പ് ചാനലിലേക്ക് കോപ്പി ചെയ്യുന്നു
        backup_msg = await client.copy_message(
            chat_id=BACKUP_CHANNEL_ID,
            from_chat_id=CHANNEL_ID,
            message_id=sent_msg.id
        )
        
        movie_name = cleaned_cap.splitlines()[0] if cleaned_cap else "Unknown Movie"
        file_size = get_file_size(message)
        
        MOVIES_DB.append({
            'name': movie_name,
            'size': file_size,
            'message_id': backup_msg.id
        })
        
        await message.reply("✨ Success! Movie uploaded to channels and added to search index.")
    except Exception as e:
        logger.error(f"Upload error: {e}")
        await message.reply("❌ Error: Failed to upload file. Check bot admin rights.")

@bot.on_message(filters.private & ~filters.user(ADMIN_USER_ID) & filters.text)
async def handle_user_search(client, message):
    query_text = message.text
    if not query_text or query_text.startswith("/"):
        return
    
    matched_movies = [m for m in MOVIES_DB if query_text.lower() in m['name'].lower()]
    
    if matched_movies:
        client.storage_results = getattr(client, 'storage_results', {})
        client.storage_results[message.from_user.id] = matched_movies
        await send_movie_page(client, message.chat.id, matched_movies, page=0)
    else:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Main Channel", url=MAIN_CHANNEL_LINK)]])
        await message.reply(
            "❌ Sorry, no movies found matching your search.\n\nPlease join our main channel for more updates:",
            reply_markup=keyboard
        )

async def send_movie_page(client, chat_id, movies, page=0):
    items_per_page = 5
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    current_movies = movies[start_idx:end_idx]
    
    keyboard_buttons = []
    for m in current_movies:
        btn_text = f"📥 {m['name']} ({m['size']})"
        keyboard_buttons.append([InlineKeyboardButton(btn_text, callback_data=f"get_mov_{m['message_id']}")])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Back", callback_data=f"page_{page-1}"))
    if end_idx < len(movies):
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{page+1}"))
    
    if nav_buttons:
        keyboard_buttons.append(nav_buttons)
        
    keyboard_buttons.append([InlineKeyboardButton("📢 Join Main Channel", url=MAIN_CHANNEL_LINK)])
    reply_markup = InlineKeyboardMarkup(keyboard_buttons)
    
    text = f"🎬 Search Results (Page {page+1}):\nSelect your movie below:"
    await client.send_message(chat_id, text, reply_markup=reply_markup)

@bot.on_callback_query()
async def button_callback(client, callback_query):
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    if data.startswith("page_"):
        page = int(data.split("_")[1])
        matched_movies = getattr(client, 'storage_results', {}).get(user_id, [])
        
        if matched_movies:
            items_per_page = 5
            start_idx = page * items_per_page
            end_idx = start_idx + items_per_page
            current_movies = matched_movies[start_idx:end_idx]
            
            keyboard_buttons = []
            for m in current_movies:
                btn_text = f"📥 {m['name']} ({m['size']})"
                keyboard_buttons.append([InlineKeyboardButton(btn_text, callback_data=f"get_mov_{m['message_id']}")])
            
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton("⬅️ Back", callback_data=f"page_{page-1}"))
            if end_idx < len(matched_movies):
                nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{page+1}"))
            
            if nav_buttons:
                keyboard_buttons.append(nav_buttons)
                
            keyboard_buttons.append([InlineKeyboardButton("📢 Join Main Channel", url=MAIN_CHANNEL_LINK)])
            reply_markup = InlineKeyboardMarkup(keyboard_buttons)
            
            try:
                await callback_query.message.edit_text(
                    f"🎬 Search Results (Page {page+1}):\nSelect your movie below:",
                    reply_markup=reply_markup
                )
            except Exception:
                pass
        await callback_query.answer()

    elif data.startswith("get_mov_"):
        msg_id = int(data.split("_")[2])
        try:
            forwarded = await client.copy_message(
                chat_id=callback_query.message.chat.id,
                from_chat_id=BACKUP_CHANNEL_ID,
                message_id=msg_id
            )
            asyncio.create_task(delete_after_delay(client, callback_query.message.chat.id, forwarded.id, 300))
            await callback_query.message.reply("⚡ Here is your movie! Note: This file will auto-delete in 5 minutes due to copyright.")
            await callback_query.answer()
        except Exception as e:
            logger.error(f"Error sending file: {e}")
            await callback_query.answer("❌ Failed to fetch movie file!", show_alert=True)

async def delete_after_delay(client, chat_id, message_id, delay):
    await asyncio.sleep(delay)
    try:
        await client.delete_messages(chat_id=chat_id, message_ids=message_id)
    except Exception as e:
        logger.error(f"Auto-delete failed: {e}")

@bot.on_message(filters.private & filters.command("start"))
async def start_cmd(client, message):
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Main Channel", url=MAIN_CHANNEL_LINK)]])
    await message.reply(
        "👋 Welcome! Send me the name of the movie you want, and I will find it for you.",
        reply_markup=keyboard
    )

if __name__ == "__main__":
    keep_alive()
    print("Starting Pyrogram Bot with configured API credentials...")
    bot.run()
