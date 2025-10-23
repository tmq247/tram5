# HasiiMusic/plugins/tools/m3u8.py
# -*- coding: utf-8 -*-

from pyrogram import Client, filters
from pyrogram.types import Message
import asyncio
import json
from typing import Optional
from HasiiMusic.utils.m3u8_sniffer import sniff_m3u8

# Tuỳ repo, bạn có thể đã có app = Client(...). Nếu đã có, import app thay vì tạo mới.

@Client.on_message(filters.command(["m3u8", "getm3u8"], prefixes=["/", "!", "."]))
async def cmd_m3u8(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage:\n`/m3u8 <url>`\n\nTuỳ chọn: Reply kèm JSON headers/cookies/ua", quote=True)

    url = message.text.split(None, 1)[1].strip()

    # Nếu user reply kèm JSON (headers/cookies/ua) trong message trước
    ua = None
    headers = None
    cookies = None
    if message.reply_to_message and (message.reply_to_message.text or message.reply_to_message.caption):
        raw = (message.reply_to_message.text or message.reply_to_message.caption).strip()
        try:
            obj = json.loads(raw)
            ua = obj.get("user_agent") or obj.get("ua")
            headers = obj.get("headers")
            cookies = obj.get("cookies")
        except Exception:
            pass

    msg = await message.reply_text("🔎 Đang sniff m3u8 bằng Firefox + yt-dlp fallback...", quote=True)

    try:
        best, all_urls = await sniff_m3u8(
            url=url,
            user_agent=ua,
            headers=headers,
            cookies=cookies,
            prefer_browser=True,
            wait_secs=22,
            headless=True,
        )
        if not all_urls:
            return await msg.edit_text("❌ Không bắt được m3u8 nào (thử thêm headers/cookies hoặc tăng wait_secs).")

        text = "✅ **Best m3u8:**\n{}\n\n".format(best or all_urls[0])
        if len(all_urls) > 1:
            preview = "\n".join(f"- {u}" for u in all_urls[:20])
            more = "" if len(all_urls) <= 20 else f"\n… và {len(all_urls)-20} link khác."
            text += f"**Tất cả m3u8 bắt được ({len(all_urls)}):**\n{preview}{more}"
        await msg.edit_text(text, disable_web_page_preview=True)
    except Exception as e:
        await msg.edit_text(f"⚠️ Lỗi: `{type(e).__name__}: {e}`")
