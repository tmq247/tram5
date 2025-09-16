from pyrogram import Client, filters
import config

@Client.on_message(filters.group)
async def restrict_groups(client, message):
    if message.chat.id not in config.ALLOWED_CHAT_IDS:
        await client.leave_chat(message.chat.id)
