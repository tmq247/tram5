import time
from asyncio import sleep
from pyrogram import filters, enums
from HasiiMusic import app

@app.on_message(~filters.private & filters.command(["groupdata"]), group=2)
async def instatus(app, message):
    start_time = time.perf_counter()
    user = await app.get_chat_member(message.chat.id, message.from_user.id)
    count = await app.get_chat_members_count(message.chat.id)

    if user.status not in (enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER):
        sent_message = await message.reply_text("🚫 ONLY ADMINS CAN USE THIS!")
        await sleep(5)
        return await sent_message.delete()

    sent_message = await message.reply_text("🔍 Gathering group stats...")

    stats = {
        "banned": 0,
        "deleted": 0,
        "bots": 0,
        "premium": 0,
        "restricted": 0,
        "fake": 0,
        "admins": 0,
        "uncached": 0,
    }

    async for member in app.get_chat_members(message.chat.id, filter=enums.ChatMembersFilter.BANNED):
        stats["banned"] += 1

    async for member in app.get_chat_members(message.chat.id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
        stats["admins"] += 1

    async for member in app.get_chat_members(message.chat.id):
        u = member.user
        if u.is_deleted:
            stats["deleted"] += 1
        elif u.is_bot:
            stats["bots"] += 1
        elif u.is_premium:
            stats["premium"] += 1
        elif getattr(member, "status", None) == enums.ChatMemberStatus.RESTRICTED:
            stats["restricted"] += 1
        elif u.username is None and u.first_name is not None and len(u.first_name) <= 2:
            stats["fake"] += 1
        else:
            stats["uncached"] += 1

    end_time = time.perf_counter()
    timelog = "{:.2f}".format(end_time - start_time)

    await sent_message.edit(f"""
**▰▰▰ GROUP DATA REPORT ▰▰▰
➲ NAME : {message.chat.title} ✅
➲ TOTAL MEMBERS : {count} 🫂
➖➖➖➖➖➖➖
➲ ADMINS : {stats['admins']} 👮‍♂️
➲ BOTS : {stats['bots']} 🤖
➲ ZOMBIES : {stats['deleted']} 🧟
➲ BANNED : {stats['banned']} 🚫
➲ PREMIUM USERS : {stats['premium']} 🎁
➲ RESTRICTED USERS : {stats['restricted']} 🔒
➲ FAKE USERS : {stats['fake']} 👻
➖➖➖➖➖➖➖
⏱ TIME TAKEN : {timelog} sec**""")
