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


# ==========================================================
#                    CONFIGURATION
#                 NO .ENV REQUIRED
# ==========================================================

API_ID = 39140696
API_HASH = "64757b9724e7143c5cc554d7a776334b"

# Bot account
BOT_TOKEN = "8973220687:AAH55V8u7g-m8s31MWLEymWmU8neU9QyGck"

# User account session
SESSION_STRING = "BQJVPVgAC506aVEIB8oiezA2ZOuQc6IAkl9s_XW5nvCFSyNrnzSnR7aPgvgtM6uWYGL-GNqnqo-1hPU6aXwklftYWZVyYPmktJu2sQXgZYl_oPLcCeQFKYPEeHGCt_aGqv2vT_jW9wbW_QwOXaE3fwpq6wtE-CuCqQiNE9vtxI3CTra1PpNEXmUtaxV0M0vfv2fzX5_WP6oszXBp5e7IWdR7RJdCvy6VKY-2hOxRYDslFdgXNZEzfZNL-BsKhD1TGub8nNjyEBvVGmAvaCMlPjbyTuxv_nzjzLxxBbSSlSma7916CBiXSlB-bp1b5VWvnLsc67lk47CXHAYTePHup1aEiN772QAAAAGtHKplAA"

# Authorized library channel
CHANNEL_ID = -1004332383599

# Optional backup channel
BACKUP_CHANNEL_ID = -1004433067284

# Telegram admin user ID
ADMIN_USER_ID = 7199304293

# Main channel
MAIN_CHANNEL_LINK = "https://t.me/mfottupdates"


# ==========================================================
#                         LOGGING
# ==========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("MOVIE-BOT")


# ==========================================================
#                       DATABASE
# ==========================================================

DB_FILE = "movies.db"

db = sqlite3.connect(
    DB_FILE,
    check_same_thread=False
)

db.execute("""
CREATE TABLE IF NOT EXISTS movies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    message_id INTEGER UNIQUE NOT NULL,

    channel_id INTEGER NOT NULL,

    title TEXT NOT NULL,

    search_text TEXT NOT NULL,

    file_name TEXT,

    file_type TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

db.commit()


# ==========================================================
#                       FLASK HTTP
# ==========================================================

web = Flask(__name__)


@web.route("/")
def home():

    return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport"
          content="width=device-width,initial-scale=1">

    <title>Movie Search Bot</title>

    <style>

        body {
            margin: 0;
            min-height: 100vh;

            display: flex;
            align-items: center;
            justify-content: center;

            background: #080808;
            color: white;

            font-family: Arial, sans-serif;
            text-align: center;
        }

        .box {
            padding: 35px;

            border-radius: 22px;

            background: #151515;

            box-shadow:
                0 0 35px
                rgba(255,255,255,.08);
        }

        h1 {
            margin-bottom: 10px;
        }

        p {
            color: #aaa;
        }

        .online {
            color: #6cff8b;
            font-weight: bold;
        }

    </style>
</head>

<body>

<div class="box">

    <h1>🎬 Movie Search Bot</h1>

    <p class="online">● ONLINE</p>

    <p>Telegram Bot + Userbot + HTTP Server</p>

</div>

</body>
</html>
"""


@web.route("/health")
def health():

    return {
        "status": "online",
        "service": "movie-search-bot"
    }


def run_http():

    web.run(
        host="0.0.0.0",
        port=10000,
        debug=False,
        use_reloader=False
    )


# ==========================================================
#                     TELEGRAM CLIENTS
# ==========================================================

# Userbot
userbot = Client(
    "movie_userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)


# Bot
bot = Client(
    "movie_search_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# ==========================================================
#                        HELPERS
# ==========================================================

def clean_text(text):

    if not text:
        return ""

    text = text.lower()

    text = re.sub(
        r"[^a-z0-9\u0D00-\u0D7F]+",
        " ",
        text
    )

    return " ".join(text.split())


def get_file_info(message):

    file_name = ""
    file_type = ""

    if message.document:

        file_name = (
            message.document.file_name or ""
        )

        file_type = "document"

    elif message.video:

        file_name = (
            message.video.file_name or ""
        )

        file_type = "video"

    elif message.audio:

        file_name = (
            message.audio.file_name or ""
        )

        file_type = "audio"

    elif message.animation:

        file_name = (
            message.animation.file_name or ""
        )

        file_type = "animation"

    return file_name, file_type


def get_title(message):

    caption = (
        message.caption or ""
    ).strip()

    file_name, _ = get_file_info(message)

    if caption:

        return caption[:200]

    if file_name:

        title = re.sub(
            r"\.[^.]+$",
            "",
            file_name
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


# ==========================================================
#                     DATABASE SAVE
# ==========================================================

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

        db.execute("""
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
            "Database save error: %s",
            error
        )


# ==========================================================
#                 USERBOT: INDEX CHANNEL
# ==========================================================

async def index_channel():

    logger.info(
        "Starting authorized library indexing..."
    )

    count = 0

    try:

        async for message in userbot.get_chat_history(
            CHANNEL_ID
        ):

            if (
                message.document
                or message.video
                or message.audio
                or message.animation
            ):

                save_movie(message)

                count += 1

                if count % 100 == 0:

                    logger.info(
                        "Indexed %s files",
                        count
                    )

        logger.info(
            "Index completed: %s files",
            count
        )

        return count

    except Exception as error:

        logger.error(
            "Indexing failed: %s",
            error
        )

        return 0


# ==========================================================
#              USERBOT: NEW FILE AUTO INDEX
# ==========================================================

@userbot.on_message(
    filters.chat(CHANNEL_ID) &
    (
        filters.document |
        filters.video |
        filters.audio |
        filters.animation
    )
)
async def new_file(message):

    save_movie(message)

    logger.info(
        "New library file indexed: %s",
        message.id
    )


# ==========================================================
#                         /START
# ==========================================================

@bot.on_message(
    filters.private &
    filters.command("start")
)
async def start_command(
    client,
    message
):

    keyboard = InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "🔎 SEARCH",
                callback_data="search"
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

Welcome! 👋

🔎 Search the authorized
movie/video library instantly.

Just send a movie name.

<b>Examples:</b>

<code>Avatar</code>

<code>Interstellar</code>

<code>Avengers</code>

━━━━━━━━━━━━━━━━━━━━

⚡ Fast Search
🎬 Library Search
📂 File Database

━━━━━━━━━━━━━━━━━━━━

<b>Send a movie name to search.</b>
        """,

        reply_markup=keyboard,

        parse_mode=ParseMode.HTML
    )


# ==========================================================
#                         HELP
# ==========================================================

@bot.on_callback_query(
    filters.regex("^help$")
)
async def help_callback(
    client,
    callback
):

    await callback.answer()

    await callback.message.edit_text(

        """
<b>ℹ️ HOW TO USE</b>

━━━━━━━━━━━━━━━━━━━━

<b>1️⃣</b> Send movie name.

<b>2️⃣</b> Bot searches the library.

<b>3️⃣</b> Matching results appear.

<b>4️⃣</b> Select a result.

<b>5️⃣</b> The authorized file is
sent to your chat.

━━━━━━━━━━━━━━━━━━━━

<b>ADMIN</b>

<code>/stats</code>

<code>/reindex</code>

<code>/clear</code>
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


# ==========================================================
#                         SEARCH INFO
# ==========================================================

@bot.on_callback_query(
    filters.regex("^search$")
)
async def search_callback(
    client,
    callback
):

    await callback.answer()

    await callback.message.edit_text(

        """
<b>🔎 SEARCH MOVIE</b>

━━━━━━━━━━━━━━━━━━━━

Send the movie name here.

<b>Example:</b>

<code>Interstellar</code>

<code>Avatar</code>

<code>Batman</code>

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


# ==========================================================
#                          BACK
# ==========================================================

@bot.on_callback_query(
    filters.regex("^back$")
)
async def back_callback(
    client,
    callback
):

    await callback.answer()

    keyboard = InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "🔎 SEARCH",
                callback_data="search"
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

━━━━━━━━━━━━━━━━━━━━

Send a movie name to search
the authorized library.
        """,

        reply_markup=keyboard,

        parse_mode=ParseMode.HTML
    )


# ==========================================================
#                       MOVIE SEARCH
# ==========================================================

@bot.on_message(
    filters.private &
    filters.text &
    ~filters.command("start")
)
async def search_movies(
    client,
    message
):

    query = (
        message.text or ""
    ).strip()

    if len(query) < 2:

        await message.reply_text(
            "🔎 Enter at least 2 characters."
        )

        return

    search = clean_text(query)

    words = search.split()

    conditions = []
    values = []

    for word in words:

        conditions.append(
            "search_text LIKE ?"
        )

        values.append(
            "%" + word + "%"
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

    cursor = db.execute(
        sql,
        values
    )

    results = cursor.fetchall()

    # ------------------------------------------------------
    # NO RESULTS
    # ------------------------------------------------------

    if not results:

        await message.reply_text(

            f"""
<b>🔍 NO RESULTS</b>

━━━━━━━━━━━━━━━━━━━━

Search:
<code>{query}</code>

No matching file was found.

Try another spelling.
            """,

            parse_mode=ParseMode.HTML
        )

        return

    # ------------------------------------------------------
    # RESULTS
    # ------------------------------------------------------

    buttons = []

    for (
        message_id,
        channel_id,
        title,
        file_name
    ) in results:

        title = title[:45]

        buttons.append([

            InlineKeyboardButton(
                f"🎬 {title}",
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

👇 Select a result:
        """,

        reply_markup=InlineKeyboardMarkup(
            buttons
        ),

        parse_mode=ParseMode.HTML
    )


# ==========================================================
#                    MOVIE RESULT
# ==========================================================

@bot.on_callback_query(
    filters.regex(r"^movie:(\d+)$")
)
async def movie_callback(
    client,
    callback
):

    message_id = int(
        callback.matches[0].group(1)
    )

    cursor = db.execute("""
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
        "⏳ Preparing..."
    )

    try:

        # Use the USERBOT to access the
        # authorized library message.

        await userbot.copy_message(
            chat_id=callback.from_user.id,
            from_chat_id=channel_id,
            message_id=message_id
        )

        await bot.send_message(

            callback.from_user.id,

            f"""
<b>🎬 {title}</b>

━━━━━━━━━━━━━━━━━━━━

📁 <code>{file_name}</code>

━━━━━━━━━━━━━━━━━━━━

📢 Main Channel
            """,

            reply_markup=InlineKeyboardMarkup([

                [
                    InlineKeyboardButton(
                        "📢 MAIN CHANNEL",
                        url=MAIN_CHANNEL_LINK
                    )
                ]

            ]),

            parse_mode=ParseMode.HTML
        )

    except Exception as error:

        logger.error(
            "Send error: %s",
            error
        )

        await callback.answer(
            "❌ Unable to access this file.",
            show_alert=True
        )


# ==========================================================
#                       ADMIN CHECK
# ==========================================================

def is_admin(user_id):

    return (
        user_id == ADMIN_USER_ID
    )


# ==========================================================
#                         /STATS
# ==========================================================

@bot.on_message(
    filters.private &
    filters.command("stats")
)
async def stats_command(
    client,
    message
):

    if not is_admin(
        message.from_user.id
    ):
        return

    cursor = db.execute(
        "SELECT COUNT(*) FROM movies"
    )

    total = cursor.fetchone()[0]

    await message.reply_text(

        f"""
<b>📊 LIBRARY STATISTICS</b>

━━━━━━━━━━━━━━━━━━━━

🎬 Indexed Files:
<b>{total}</b>

🗄 Database:
<b>SQLite</b>

🤖 Bot:
<b>ONLINE</b>

👤 Userbot:
<b>ONLINE</b>

🌐 HTTP:
<b>ONLINE</b>

━━━━━━━━━━━━━━━━━━━━
        """,

        parse_mode=ParseMode.HTML
    )


# ==========================================================
#                        /REINDEX
# ==========================================================

@bot.on_message(
    filters.private &
    filters.command("reindex")
)
async def reindex_command(
    client,
    message
):

    if not is_admin(
        message.from_user.id
    ):
        return

    status = await message.reply_text(
        "⏳ <b>Reindexing...</b>",
        parse_mode=ParseMode.HTML
    )

    count = await index_channel()

    await status.edit_text(

        f"""
<b>✅ REINDEX COMPLETE</b>

━━━━━━━━━━━━━━━━━━━━

🎬 Indexed:
<b>{count}</b> files

📂 Database:
<b>Updated</b>

━━━━━━━━━━━━━━━━━━━━
        """,

        parse_mode=ParseMode.HTML
    )


# ==========================================================
#                          /CLEAR
# ==========================================================

@bot.on_message(
    filters.private &
    filters.command("clear")
)
async def clear_command(
    client,
    message
):

    if not is_admin(
        message.from_user.id
    ):
        return

    db.execute(
        "DELETE FROM movies"
    )

    db.commit()

    await message.reply_text(

        """
<b>🗑 DATABASE CLEARED</b>

The local search index has been cleared.

Use:

<code>/reindex</code>

to rebuild it from the authorized library.
        """,

        parse_mode=ParseMode.HTML
    )


# ==========================================================
#                         START ALL
# ==========================================================

async def main():

    logger.info(
        "Starting HTTP server..."
    )

    Thread(
        target=run_http,
        daemon=True
    ).start()

    logger.info(
        "Starting USERBOT..."
    )

    await userbot.start()

    me = await userbot.get_me()

    logger.info(
        "USERBOT: @%s",
        me.username or me.first_name
    )

    logger.info(
        "Starting BOT..."
    )

    await bot.start()

    bot_me = await bot.get_me()

    logger.info(
        "BOT: @%s",
        bot_me.username
    )

    logger.info(
        "Indexing authorized library..."
    )

    await index_channel()

    logger.info(
        "======================================"
    )

    logger.info(
        "🎬 MOVIE SEARCH SYSTEM ONLINE"
    )

    logger.info(
        "🤖 BOT       : ONLINE"
    )

    logger.info(
        "👤 USERBOT   : ONLINE"
    )

    logger.info(
        "🌐 HTTP      : ONLINE"
    )

    logger.info(
        "======================================"
    )

    await asyncio.Event().wait()


# ==========================================================
#                          RUN
# ==========================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        logger.info(
            "Bot stopped."
    )
