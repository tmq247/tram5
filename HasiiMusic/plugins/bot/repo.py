from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from HasiiMusic import app
from config import BOT_USERNAME

repo_caption = """**
🚀 ᴄʟᴏɴᴇ ᴀɴᴅ ᴅᴇᴘʟᴏʏ – ʀᴇᴘᴏ 🚀

➤ ᴅᴇᴘʟᴏʏ ᴇᴀsɪʟʏ ᴏɴ ʜᴇʀᴏᴋᴜ ᴡɪᴛʜᴏᴜᴛ ᴇʀʀᴏʀꜱ  
➤ ɴᴏ ʜᴇʀᴏᴋᴜ ʙᴀɴ ɪꜱꜱᴜᴇ  
➤ ɴᴏ ɪᴅ ʙᴀɴ ɪꜱꜱᴜᴇ  
➤ ᴜɴʟɪᴍɪᴛᴇᴅ ᴅʏɴᴏꜱ  
➤ ʀᴜɴ 24/7 ʟᴀɢ ꜰʀᴇᴇ

ɪꜰ ʏᴏᴜ ꜰᴀᴄᴇ ᴀɴʏ ᴘʀᴏʙʟᴇᴍ, ꜱᴇɴᴅ ꜱꜱ ɪɴ ꜱᴜᴘᴘᴏʀᴛ
**"""

@app.on_message(filters.command("repo0000000000"))
async def show_repo(_, msg):
    buttons = [
        [InlineKeyboardButton("➕ ᴀᴅᴅ ᴍᴇ ʙᴀʙʏ ✨", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
        [
            InlineKeyboardButton("👑 ᴏᴡɴᴇʀ", url="https://t.me/COIHAYCOC"),
            InlineKeyboardButton("💬 ꜱᴜᴘᴘᴏʀᴛ", url="https://t.me/COIHAYCOC")
        ],
        [
            InlineKeyboardButton("🛠️ ꜱᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ", url="https://t.me/COIHAYCOC"),
            InlineKeyboardButton("🎵 ɢɪᴛʜᴜʙ", url="https://github.com")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(buttons)

    try:
        await msg.reply_photo(
            photo="https://files.catbox.moe/bcif0t.png",
            caption=repo_caption,
            reply_markup=reply_markup
        )
    except:
        pass
