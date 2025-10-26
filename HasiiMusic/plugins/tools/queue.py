import asyncio
import os

from pyrogram import filters
#from pyrogram.errors import FloodWait
from pyrogram.types import CallbackQuery, InputMediaPhoto, Message

import config
from HasiiMusic import app
from HasiiMusic.misc import db
from HasiiMusic.utils import TuneBin, get_channeplayCB, seconds_to_min
from HasiiMusic.utils.database import get_cmode, is_active_chat, is_music_playing
from HasiiMusic.utils.decorators.language import language, languageCB
from HasiiMusic.utils.inline import queue_back_markup, queue_markup
from config import BANNED_USERS

basic = {}
# HasiiMusic/plugins/tools/queue.py
from pyrogram.enums import ParseMode
from pyrogram.errors import EntityBoundsInvalid, FloodWait

MAX_CAPTION = 1024

_MD_META = r"_*`[]()~>#+-=|{}.!\\"
def md_escape(text: str) -> str:
    if not text:
        return ""
    # Escape các ký tự có ý nghĩa trong Markdown v2/pyrogram
    out = []
    for ch in str(text):
        if ch in _MD_META:
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)

def plain(text: str) -> str:
    # Bóc Markdown link kiểu [x](y) -> x (giữ text)
    import re
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text or "")
    # Gỡ các ký tự markup còn lại
    t = re.sub(r"[_*`~>|#\+\-=|{}\.\!\[\]\(\)\\]", "", t)
    return t

def cap_trunc(s: str, limit: int = MAX_CAPTION) -> str:
    s = s or ""
    if len(s) <= limit:
        return s
    return s[: limit - 1] + "…"

def get_image(videoid):
    if os.path.isfile(f"cache/{videoid}.png"):
        return f"cache/{videoid}.png"
    else:
        return config.YOUTUBE_IMG_URL


def get_duration(playing):
    file_path = playing[0]["file"]
    if "index_" in file_path or "live_" in file_path:
        return "Unknown"
    duration_seconds = int(playing[0]["seconds"])
    if duration_seconds == 0:
        return "Unknown"
    else:
        return "Inline"


@app.on_message(
    filters.command(["queue", "cqueue", "player", "cplayer", "playing", "cplaying"])
    & filters.group
    & ~BANNED_USERS
)
@language
async def get_queue(client, message: Message, _):
    if message.command[0][0] == "c":
        chat_id = await get_cmode(message.chat.id)
        if chat_id is None:
            return await message.reply_text(_["setting_7"])
        try:
            await app.get_chat(chat_id)
        except Exception:
            return await message.reply_text(_["cplay_4"])
        cplay = True
    else:
        chat_id = message.chat.id
        cplay = False

    if not await is_active_chat(chat_id):
        return await message.reply_text(_["general_5"])

    got = db.get(chat_id)
    if not got:
        return await message.reply_text(_["queue_2"])

    file = got[0]["file"]
    videoid = got[0]["vidid"]
    user = got[0]["by"]
    title = (got[0]["title"]).title()
    typo = (got[0]["streamtype"]).title()
    DUR = get_duration(got)

    # ==== chọn IMAGE như cũ ====
    if "live_" in file or "vid_" in file:
        IMAGE = get_image(videoid)
    elif "index_" in file:
        IMAGE = config.STREAM_IMG_URL
    else:
        if videoid == "telegram":
            IMAGE = (config.TELEGRAM_AUDIO_URL if typo == "Audio"
                     else config.TELEGRAM_VIDEO_URL)
        elif videoid == "soundcloud":
            IMAGE = config.SOUNCLOUD_IMG_URL
        else:
            IMAGE = get_image(videoid)

    send = _["queue_6"] if DUR == "Unknown" else _["queue_7"]

    # ==== Escape các field có thể gây lỗi MD ====
    safe_title = md_escape(title)
    safe_typo  = md_escape(typo)
    safe_user  = md_escape(user)
    # app.mention là Markdown: dạng [Name](tg://user?id=...)
    safe_mention = md_escape(app.mention)

    # i18n template: _["queue_8"] phải là Markdown hợp lệ
    cap_md = _["queue_8"].format(safe_mention, safe_title, safe_typo, safe_user, md_escape(send))
    cap_md = cap_trunc(cap_md, MAX_CAPTION)

    # ==== keyboard như cũ ====
    if DUR == "Unknown":
        upl = queue_markup(_, DUR, "c" if cplay else "g", videoid)
    else:
        upl = queue_markup(
            _,
            DUR,
            "c" if cplay else "g",
            videoid,
            seconds_to_min(got[0]["played"]),
            got[0]["dur"],
        )

    basic[videoid] = True

    # ==== Gửi caption an toàn với MARKDOWN; fallback: plain ====
    try:
        mystic = await message.reply_photo(
            IMAGE,
            caption=cap_md,
            reply_markup=upl,
            parse_mode=ParseMode.MARKDOWN,
        )
    except EntityBoundsInvalid:
        # Nếu template/i18n có markdown lỗi -> gửi plain text
        mystic = await message.reply_photo(
            IMAGE,
            caption=cap_trunc(plain(cap_md), MAX_CAPTION),
            reply_markup=upl,
            parse_mode=HTML,
        )

    if DUR != "Unknown":
        try:
            while db[chat_id][0]["vidid"] == videoid:
                await asyncio.sleep(5)
                if await is_active_chat(chat_id):
                    if basic[videoid]:
                        if await is_music_playing(chat_id):
                            try:
                                buttons = queue_markup(
                                    _,
                                    DUR,
                                    "c" if cplay else "g",
                                    videoid,
                                    seconds_to_min(db[chat_id][0]["played"]),
                                    db[chat_id][0]["dur"],
                                )
                                await mystic.edit_reply_markup(reply_markup=buttons)
                            except FloodWait:
                                pass
                        else:
                            pass
                    else:
                        break
                else:
                    break
        except Exception:
            return


@app.on_callback_query(filters.regex("GetTimer") & ~BANNED_USERS)
async def quite_timer(client, CallbackQuery: CallbackQuery):
    try:
        await CallbackQuery.answer()
    except:
        pass


@app.on_callback_query(filters.regex("GetQueued") & ~BANNED_USERS)
@languageCB
async def queued_tracks(client, CallbackQuery: CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    what, videoid = callback_request.split("|")
    try:
        chat_id, channel = await get_channeplayCB(_, what, CallbackQuery)
    except:
        return
    if not await is_active_chat(chat_id):
        return await CallbackQuery.answer(_["general_5"], show_alert=True)
    got = db.get(chat_id)
    if not got:
        return await CallbackQuery.answer(_["queue_2"], show_alert=True)
    if len(got) == 1:
        return await CallbackQuery.answer(_["queue_5"], show_alert=True)
    await CallbackQuery.answer()
    basic[videoid] = False
    buttons = queue_back_markup(_, what)
    med = InputMediaPhoto(
        media="https://files.catbox.moe/70ak97.jpg",
        caption=_["queue_1"],
    )
    await CallbackQuery.edit_message_media(media=med)
    j = 0
    msg = ""
    for x in got:
        j += 1
        if j == 1:
            msg += f'Streaming :\n\n✨ Title : {x["title"]}\nDuration : {x["dur"]}\nBy : {x["by"]}\n\n'
        elif j == 2:
            msg += f'Queued :\n\n✨ Title : {x["title"]}\nDuration : {x["dur"]}\nBy : {x["by"]}\n\n'
        else:
            msg += f'✨ Title : {x["title"]}\nDuration : {x["dur"]}\nBy : {x["by"]}\n\n'
    if "Queued" in msg:
        if len(msg) < 700:
            await asyncio.sleep(1)
            return await CallbackQuery.edit_message_text(msg, reply_markup=buttons)
        if "✨" in msg:
            msg = msg.replace("✨", "")
        link = await TuneBin(msg)
        med = InputMediaPhoto(media=link, caption=_["queue_3"].format(link))
        await CallbackQuery.edit_message_media(media=med, reply_markup=buttons)
    else:
        await asyncio.sleep(1)
        return await CallbackQuery.edit_message_text(msg, reply_markup=buttons)


@app.on_callback_query(filters.regex("queue_back_timer") & ~BANNED_USERS)
@languageCB
async def queue_back(client, CallbackQuery: CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    cplay = callback_data.split(None, 1)[1]
    try:
        chat_id, channel = await get_channeplayCB(_, cplay, CallbackQuery)
    except:
        return
    if not await is_active_chat(chat_id):
        return await CallbackQuery.answer(_["general_5"], show_alert=True)
    got = db.get(chat_id)
    if not got:
        return await CallbackQuery.answer(_["queue_2"], show_alert=True)
    await CallbackQuery.answer(_["set_cb_5"], show_alert=True)
    file = got[0]["file"]
    videoid = got[0]["vidid"]
    user = got[0]["by"]
    title = (got[0]["title"]).title()
    typo = (got[0]["streamtype"]).title()
    DUR = get_duration(got)
    if "live_" in file:
        IMAGE = get_image(videoid)
    elif "vid_" in file:
        IMAGE = get_image(videoid)
    elif "index_" in file:
        IMAGE = config.STREAM_IMG_URL
    else:
        if videoid == "telegram":
            IMAGE = (
                config.TELEGRAM_AUDIO_URL
                if typo == "Audio"
                else config.TELEGRAM_VIDEO_URL
            )
        elif videoid == "soundcloud":
            IMAGE = config.SOUNCLOUD_IMG_URL
        else:
            IMAGE = get_image(videoid)
    send = _["queue_6"] if DUR == "Unknown" else _["queue_7"]
    cap = _["queue_8"].format(app.mention, title, typo, user, send)
    upl = (
        queue_markup(_, DUR, cplay, videoid)
        if DUR == "Unknown"
        else queue_markup(
            _,
            DUR,
            cplay,
            videoid,
            seconds_to_min(got[0]["played"]),
            got[0]["dur"],
        )
    )
    basic[videoid] = True

    med = InputMediaPhoto(media=IMAGE, caption=cap)
    mystic = await CallbackQuery.edit_message_media(media=med, reply_markup=upl)
    if DUR != "Unknown":
        try:
            while db[chat_id][0]["vidid"] == videoid:
                await asyncio.sleep(5)
                if await is_active_chat(chat_id):
                    if basic[videoid]:
                        if await is_music_playing(chat_id):
                            try:
                                buttons = queue_markup(
                                    _,
                                    DUR,
                                    cplay,
                                    videoid,
                                    seconds_to_min(db[chat_id][0]["played"]),
                                    db[chat_id][0]["dur"],
                                )
                                await mystic.edit_reply_markup(reply_markup=buttons)
                            except FloodWait:
                                pass
                        else:
                            pass
                    else:
                        break
                else:
                    break
        except:
            return
