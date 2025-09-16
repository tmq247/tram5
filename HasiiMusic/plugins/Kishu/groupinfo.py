from pyrogram import filters
from pyrogram.types import Message
from HasiiMusic import app


@app.on_message(filters.command("groupinfo", prefixes="/"))
async def get_group_status(_, message: Message):
    if len(message.command) != 2:
        await message.reply(
            "Please provide a group username. Example: `/groupinfo YourGroupUsername`"
        )
        return

    group_username = message.command[1]

    try:
        group = await app.get_chat(group_username)
    except Exception as e:
        await message.reply(f"Error: {e}")
        return

    total_members = await app.get_chat_members_count(group.id)
    group_description = group.description or "N/A"
    group_username_display = f"@{group.username}" if group.username else "Private"

    response_text = (
        "▰▰▰▰▰▰▰▰▰\n"
        f"➲ GROUP NAME : {group.title} ✅\n"
        f"➲ GROUP ID : `{group.id}`\n"
        f"➲ TOTAL MEMBERS : {total_members}\n"
        f"➲ DESCRIPTION : `{group_description}`\n"
        f"➲ USERNAME : {group_username_display}\n"
        "▰▰▰▰▰▰▰▰▰"
    )

    await message.reply(response_text)
