import asyncio
import logging
import re
import sqlite3
from threading import Thread

from flask import Flask

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)


# =========================================================
#                    CONFIGURATION
#             NO .ENV / NO ENVIRONMENT VARIABLES
# =========================================================

API_ID = 39140696
API_HASH = "64757b9724e7143c5cc554d7a776334b"
BOT_TOKEN = "8973220687:AAHpa64POFLGx4yVtjLQFBXrgfWoroCszqE"

# Your authorized movie library channel
CHANNEL_ID = -1004332383599

# Optional backup channel
BACKUP_CHANNEL_ID = -1004433067284

# Your Telegram user ID
ADMIN_USER_ID = 7199304293

# Main channel
MAIN_CHANNEL_LINK = "https://t.me/mfottupdates"


# =========================================================
#                       LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("MOVIE_SEARCH_BOT")


# =========================================================
#                       DATABASE
# =========================================================

DB_FILE = "movies.db"

db = sqlite3.connect(
    DB_FILE,
    check_same_thread=False
)

cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS movies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    message_id INTEGER UNIQUE NOT NULL,

    channel_id INTEGER NOT NULL,

    title TEXT,

    search_text TEXT,

    file_name TEXT,

    file_type TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

db.commit()


# =========================================================
#                         PYROGRAM
# =========================================================

app = Client(
    "movie_search_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# =========================================================
#                       FLASK SERVER
#                     FOR RENDER HOST
# =========================================================

web = Flask(__name__)


@web.route("/")
def home():

    return """
    <!DOCTYPE html>

    <html>

    <head>

        <title>Movie Search Bot</title>

        <meta name="viewport"
              content="width=device-width, initial-scale=1">

        <style>

            body {
                margin: 0;
                min-height: 100vh;

                display: flex;
                align-items: center;
                justify-content: center;

                background: #080808;
                color: white;

                font-family:
                Arial,
                sans-serif;

                text-align: center;
            }

            .box {
                padding: 35px;
                border-radius: 20px;

                background: #151515;

                box-shadow:
                0 0 30px
                rgba(255,255,255,0.08);
            }

            h1 {
                margin-bottom: 10px;
            }

            p {
                color: #aaa;
            }

        </style>

    </head>

    <body>

        <div class="box">

            <h1>🎬 Movie Search Bot</h1>

            <p>Bot is online and running.</p>

            <p>⚡ Status: ONLINE</p>

        </div>

    </body>

    </html>
    """


@web.route("/health")
def health():

    return {
        "status": "online",
        "service": "Movie Search Bot"
    }


def run_web():

    web.run(
        host="0.0.0.0",
        port=10000
    )


# =========================================================
#                       TEXT CLEANER
# =========================================================

def clean_text(text):

    if not text:
        return ""

    text = text.lower()

    text = re.sub(
        r"[^a-z0-9\u0D00-\u0D7F]+",
        " ",
        text
    )

    return " ".join(
        text.split()
    )


# =========================================================
#                    FILE INFORMATION
# =========================================================

def get_file_info(message):

    file_name = ""
    file_type = ""

    if message.document:

        file_name = (
            message.document.file_name
            or ""
        )

        file_type = "document"

    elif message.video:

        file_name = (
            message.video.file_name
            or ""
        )

        file_type = "video"

    elif message.audio:

        file_name = (
            message.audio.file_name
            or ""
        )

        file_type = "audio"

    elif message.animation:

        file_name = (
            message.animation.file_name
            or ""
        )

        file_type = "animation"

    return file_name, file_type


# =========================================================
#                       GET TITLE
# =========================================================

def get_title(message):

    caption = (
        message.caption
        or ""
    ).strip()

    file_name, _ = get_file_info(
        message
    )

    # Caption has priority
    if caption:

        return caption[:200]

    # Otherwise filename
    if file_name:

        title = file_name

        title = re.sub(
            r"\.[^.]+$",
            "",
            title
        )

        title = re.sub(
            r"[_\-.]+",
            " ",
            title
        )

        title = re.sub(
            r"\s+",
            " ",
            title
        )

        return title.strip()

    return "Unknown Movie"


# =========================================================
#                    SAVE MOVIE TO DB
# =========================================================

def save_movie(message):

    if not (
        message.document
        or message.video
        or message.audio
        or message.animation
    ):

        return

    file_name, file_type = get_file_info(
        message
    )

    title = get_title(
        message
    )

    search_text = clean_text(
        f"{title} {file_name}"
    )

    try:

        cursor.execute("""
        INSERT OR REPLACE INTO movies
        (
            message_id,
            channel_id,
            title,
            search_text,
            file_name,
            file_type
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            message.id,
            message.chat.id,
            title,
            search_text,
            file_name,
            file_type
        ))

        db.commit()

    except Exception as error:

        logger.error(
            f"Database error: {error}"
        )


# =========================================================
#                    INDEX OLD CHANNEL FILES
# =========================================================

async def index_channel():

    logger.info(
        "Starting channel indexing..."
    )

    count = 0

    try:

        async for message in app.get_chat_history(
            CHANNEL_ID
        ):

            if (
                message.document
                or message.video
                or message.audio
                or message.animation
            ):

                save_movie(
                    message
                )

                count += 1

                if count % 100 == 0:

                    logger.info(
                        f"Indexed {count} files"
                    )

        logger.info(
            f"Index complete: {count} files"
        )

        return count

    except Exception as error:

        logger.error(
            f"Index error: {error}"
        )

        return 0


# =========================================================
#                         /START
# =========================================================

@app.on_message(
    filters.private &
    filters.command("start")
)
async def start_handler(
    client,
    message
):

    keyboard = InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "🔎 SEARCH MOVIE",
                callback_data="search_info"
            )
        ],

        [
            InlineKeyboardButton(
                "📢 MAIN CHANNEL",
                url=MAIN_CHANNEL_LINK
            )
        ],

        [
            InlineKeyboardButton(
                "ℹ️ HELP",
                callback_data="help"
            )
        ]

    ])

    await message.reply_text(

        """
<b>🎬 MOVIE SEARCH BOT</b>

━━━━━━━━━━━━━━━━━━━━

🔎 <b>Search your movie library</b>

Simply send the movie name.

<b>Example:</b>

<code>Avatar</code>

<code>Interstellar</code>

<code>Batman</code>

<code>Avengers Endgame</code>

━━━━━━━━━━━━━━━━━━━━

⚡ Fast Search
🎬 Movie Library
📂 File Search

━━━━━━━━━━━━━━━━━━━━

<b>Send a movie name to begin.</b>
        """,

        reply_markup=keyboard,

        parse_mode=ParseMode.HTML
    )


# =========================================================
#                     SEARCH INFO
# =========================================================

@app.on_callback_query(
    filters.regex("^search_info$")
)
async def search_info(
    client,
    callback
):

    await callback.answer()

    await callback.message.edit_text(

        """
<b>🔎 MOVIE SEARCH</b>

━━━━━━━━━━━━━━━━━━━━

Send the movie name in this chat.

<b>Examples:</b>

<code>Avatar</code>

<code>Interstellar</code>

<code>KGF</code>

<code>Avengers</code>

━━━━━━━━━━━━━━━━━━━━

The bot searches the indexed
authorized movie library.
        """,

        reply_markup=InlineKeyboardMarkup([

            [
                InlineKeyboardButton(
                    "🔙 BACK",
                    callback_data="back"
                )
            ]

        ]),

        parse_mode=ParseMode.HTML
    )


# =========================================================
#                         HELP
# =========================================================

@app.on_callback_query(
    filters.regex("^help$")
)
async def help_handler(
    client,
    callback
):

    await callback.answer()

    await callback.message.edit_text(

        """
<b>ℹ️ HOW TO USE</b>

━━━━━━━━━━━━━━━━━━━━

<b>1.</b> Send the movie name.

<b>2.</b> Bot searches the library.

<b>3.</b> Matching movies appear.

<b>4.</b> Select the movie.

<b>5.</b> The authorized file is sent.

━━━━━━━━━━━━━━━━━━━━

<b>ADMIN COMMANDS</b>

<code>/stats</code>

<code>/reindex</code>

━━━━━━━━━━━━━━━━━━━━
        """,

        reply_markup=InlineKeyboardMarkup([

            [
                InlineKeyboardButton(
                    "🔙 BACK",
                    callback_data="back"
                )
            ]

        ]),

        parse_mode=ParseMode.HTML
    )


# =========================================================
#                         BACK
# =========================================================

@app.on_callback_query(
    filters.regex("^back$")
)
async def back_handler(
    client,
    callback
):

    await callback.answer()

    keyboard = InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "🔎 SEARCH",
                callback_data="search_info"
            )
        ],

        [
            InlineKeyboardButton(
                "📢 MAIN CHANNEL",
                url=MAIN_CHANNEL_LINK
            )
        ],

        [
            InlineKeyboardButton(
                "ℹ️ HELP",
                callback_data="help"
            )
        ]

    ])

    await callback.message.edit_text(

        """
<b>🎬 MOVIE SEARCH BOT</b>

Send a movie name to search.
        """,

        reply_markup=keyboard,

        parse_mode=ParseMode.HTML
    )


# =========================================================
#                        SEARCH
# =========================================================

@app.on_message(
    filters.private &
    filters.text &
    ~filters.command(
        "start"
    )
)
async def search_handler(
    client,
    message
):

    query = (
        message.text
        or ""
    ).strip()

    if len(query) < 2:

        await message.reply_text(
            "🔎 Please enter at least 2 characters."
        )

        return

    search = clean_text(
        query
    )

    words = search.split()

    conditions = []
    values = []

    for word in words:

        conditions.append(
            "search_text LIKE ?"
        )

        values.append(
            f"%{word}%"
        )

    sql = f"""
    SELECT
        message_id,
        channel_id,
        title,
        file_name
    FROM movies
    WHERE {" AND ".join(conditions)}
    ORDER BY id DESC
    LIMIT 10
    """

    cursor.execute(
        sql,
        values
    )

    results = cursor.fetchall()

    # -----------------------------------------------------
    # NO RESULTS
    # -----------------------------------------------------

    if not results:

        await message.reply_text(

            f"""
<b>🔍 NO RESULTS FOUND</b>

━━━━━━━━━━━━━━━━━━━━

Search:
<code>{query}</code>

Try another movie name or spelling.

━━━━━━━━━━━━━━━━━━━━
            """,

            parse_mode=ParseMode.HTML
        )

        return

    # -----------------------------------------------------
    # RESULTS BUTTONS
    # -----------------------------------------------------

    buttons = []

    for (
        message_id,
        channel_id,
        title,
        file_name
    ) in results:

        display_title = title[:45]

        buttons.append([

            InlineKeyboardButton(
                f"🎬 {display_title}",
                callback_data=f"movie:{message_id}"
            )

        ])

    buttons.append([

        InlineKeyboardButton(
            "📢 MAIN CHANNEL",
            url=MAIN_CHANNEL_LINK
        )

    ])

    await message.reply_text(

        f"""
<b>🔎 SEARCH RESULTS</b>

━━━━━━━━━━━━━━━━━━━━

Query:
<code>{query}</code>

Found:
<b>{len(results)}</b>

━━━━━━━━━━━━━━━━━━━━

👇 Select a movie:
        """,

        reply_markup=InlineKeyboardMarkup(
            buttons
        ),

        parse_mode=ParseMode.HTML
    )


# =========================================================
#                     MOVIE SELECTION
# =========================================================

@app.on_callback_query(
    filters.regex(
        r"^movie:(\d+)$"
    )
)
async def movie_handler(
    client,
    callback
):

    message_id = int(
        callback.matches[0].group(1)
    )

    cursor.execute("""
    SELECT
        channel_id,
        title,
        file_name
    FROM movies
    WHERE message_id = ?
    """, (
        message_id,
    ))

    movie = cursor.fetchone()

    if not movie:

        await callback.answer(
            "❌ Movie not found.",
            show_alert=True
        )

        return

    channel_id, title, file_name = movie

    await callback.answer(
        "⏳ Preparing file..."
    )

    try:

        # Send/copy the authorized library message
        await client.copy_message(

            chat_id=callback.from_user.id,

            from_chat_id=channel_id,

            message_id=message_id

        )

        await client.send_message(

            callback.from_user.id,

            f"""
<b>🎬 {title}</b>

━━━━━━━━━━━━━━━━━━━━

📁 <code>{file_name}</code>

━━━━━━━━━━━━━━━━━━━━

📢 <b>Main Channel</b>
            """,

            reply_markup=InlineKeyboardMarkup([

                [
                    InlineKeyboardButton(
                        "📢 JOIN CHANNEL",
                        url=MAIN_CHANNEL_LINK
                    )
                ]

            ]),

            parse_mode=ParseMode.HTML
        )

    except Exception as error:

        logger.error(
            f"File sending error: {error}"
        )

        await callback.message.reply_text(

            """
❌ <b>Unable to send this file.</b>

The original channel message may no
longer be available or the bot may
not have permission to access it.
            """,

            parse_mode=ParseMode.HTML
        )


# =========================================================
#                AUTO INDEX NEW CHANNEL FILES
# =========================================================

@app.on_message(
    filters.chat(CHANNEL_ID) &
    (
        filters.document |
        filters.video |
        filters.audio |
        filters.animation
    )
)
async def new_file_handler(
    client,
    message
):

    save_movie(
        message
    )

    logger.info(
        f"New file indexed: {message.id}"
    )


# =========================================================
#                      ADMIN CHECK
# =========================================================

def is_admin(user_id):

    return user_id == ADMIN_USER_ID


# =========================================================
#                     ADMIN /STATS
# =========================================================

@app.on_message(
    filters.command("stats")
)
async def stats_handler(
    client,
    message
):

    if not is_admin(
        message.from_user.id
    ):

        return

    cursor.execute(
        "SELECT COUNT(*) FROM movies"
    )

    total = cursor.fetchone()[0]

    await message.reply_text(

        f"""
<b>📊 LIBRARY STATISTICS</b>

━━━━━━━━━━━━━━━━━━━━

🎬 Total Files:
<b>{total}</b>

🗄 Database:
<b>SQLite</b>

⚡ Bot:
<b>ONLINE</b>

━━━━━━━━━━━━━━━━━━━━
        """,

        parse_mode=ParseMode.HTML
    )


# =========================================================
#                    ADMIN /REINDEX
# =========================================================

@app.on_message(
    filters.command("reindex")
)
async def reindex_handler(
    client,
    message
):

    if not is_admin(
        message.from_user.id
    ):

        return

    status = await message.reply_text(
        "⏳ <b>Reindexing library...</b>",
        parse_mode=ParseMode.HTML
    )

    count = await index_channel()

    await status.edit_text(

        f"""
<b>✅ REINDEX COMPLETED</b>

━━━━━━━━━━━━━━━━━━━━

🎬 Indexed Files:
<b>{count}</b>

📂 Library:
<b>Updated</b>

⚡ Status:
<b>READY</b>

━━━━━━━━━━━━━━━━━━━━
        """,

        parse_mode=ParseMode.HTML
    )


# =========================================================
#                       ADMIN /CLEAR
# =========================================================

@app.on_message(
    filters.command("clear")
)
async def clear_handler(
    client,
    message
):

    if not is_admin(
        message.from_user.id
    ):

        return

    cursor.execute(
        "DELETE FROM movies"
    )

    db.commit()

    await message.reply_text(

        """
<b>🗑 DATABASE CLEARED</b>

All indexed records have been removed.

Use:

<code>/reindex</code>

to index the authorized channel again.
        """,

        parse_mode=ParseMode.HTML
    )


# =========================================================
#                    BOT STARTUP
# =========================================================

async def main():

    logger.info(
        "Starting Movie Search Bot..."
    )

    await app.start()

    me = await app.get_me()

    logger.info(
        f"Bot started: @{me.username}"
    )

    # Initial indexing
    await index_channel()

    logger.info(
        "================================="
    )

    logger.info(
        "MOVIE SEARCH BOT IS ONLINE"
    )

    logger.info(
        "================================="
    )

    # Keep bot running
    await asyncio.Event().wait()


# =========================================================
#                         RUN
# =========================================================

if __name__ == "__main__":

    # Render HTTP server
    Thread(
        target=run_web,
        daemon=True
    ).start()

    # Telegram bot
    asyncio.run(
        main()
    )
