# -*- coding: utf-8 -*-
# HasiiMusic/plugins/tools/iptv.py
# Menu IPTV Việt Nam lấy từ iptv-org, hiển thị tên kênh như trong vn.m3u
# /iptv -> danh sách kênh (phân trang) -> bấm kênh -> hiện link + nút back/close

import asyncio
import re
from typing import List, Tuple, Dict

from pyrogram import filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

# Lưu ý: dùng đúng 'app' theo phong cách của repo
from HasiiMusic import app

# Mirror ổn định do iptv-org build sẵn:
IPTV_VN_URL = "https://iptv-org.github.io/iptv/countries/vn.m3u"
# Nếu muốn bám đúng file trong repo:
# IPTV_VN_URL = "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/vn.m3u"

PAGE_SIZE = 15
_CHANNEL_CACHE: Dict[int, List[Tuple[str, str]]] = {}

async def _http_get(url: str, timeout: int = 15) -> str:
    try:
        import aiohttp  # type: ignore
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, timeout=timeout) as resp:
                resp.raise_for_status()
                return await resp.text()
    except Exception:
        import urllib.request
        def _fetch():
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        return await asyncio.to_thread(_fetch)

def _parse_m3u(content: str) -> List[Tuple[str, str]]:
    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
    out: List[Tuple[str, str]] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("#EXTINF"):
            m = re.search(r",\s*(.+)$", ln)
            name = m.group(1).strip() if m else "Unknown"
            if i + 1 < len(lines) and not lines[i + 1].startswith("#"):
                url = lines[i + 1]
                out.append((name, url))
                i += 2
                continue
        i += 1
    seen = set()
    uniq: List[Tuple[str, str]] = []
    for n, u in out:
        if n not in seen:
            uniq.append((n, u))
            seen.add(n)
    return uniq

def _build_page_keyboard(channels: List[Tuple[str, str]], page: int) -> InlineKeyboardMarkup:
    total = len(channels)
    max_page = max(0, (total - 1) // PAGE_SIZE)
    page = max(0, min(page, max_page))
    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, total)

    rows = []
    for idx in range(start, end):
        name, _ = channels[idx]
        rows.append([InlineKeyboardButton(text=name, callback_data=f"iptv:ch:{idx}")])

    navs = []
    if page > 0:
        navs.append(InlineKeyboardButton("◀️ Trước", callback_data=f"iptv:pg:{page-1}"))
    navs.append(InlineKeyboardButton(f"Trang {page+1}/{max_page+1}", callback_data="iptv:noop"))
    if page < max_page:
        navs.append(InlineKeyboardButton("Tiếp ▶️", callback_data=f"iptv:pg:{page+1}"))
    if navs:
        rows.append(navs)

    rows.append([InlineKeyboardButton("✖ Đóng", callback_data="iptv:close")])
    return InlineKeyboardMarkup(rows)

@app.on_message(filters.command(["iptv", "IPTV"]))
async def iptv_cmd(_, m: Message):
    chat_id = m.chat.id
    try:
        text = await _http_get(IPTV_VN_URL)
    except Exception as e:
        return await m.reply_text(
            f"⚠️ Không tải được playlist: {e}\nNguồn: {IPTV_VN_URL}",
            disable_web_page_preview=True,
        )

    channels = _parse_m3u(text)
    if not channels:
        return await m.reply_text("⚠️ Không tìm thấy kênh nào trong playlist VN.", disable_web_page_preview=True)

    _CHANNEL_CACHE[chat_id] = channels
    kb = _build_page_keyboard(channels, page=0)
    await m.reply_text(
        "📺 **IPTV Việt Nam**\nChọn kênh để xem link:",
        reply_markup=kb,
        disable_web_page_preview=True,
        parse_mode=None,
    )

@app.on_callback_query(filters.regex(r"^iptv:(.+)"))
async def iptv_cb(_, q: CallbackQuery):
    data = q.data
    chat_id = q.message.chat.id if q.message else q.from_user.id

    channels = _CHANNEL_CACHE.get(chat_id)
    if channels is None:
        try:
            text = await _http_get(IPTV_VN_URL)
            channels = _parse_m3u(text)
            _CHANNEL_CACHE[chat_id] = channels
        except Exception as e:
            return await q.answer(f"Lỗi nạp playlist: {e}", show_alert=True)

    if data == "iptv:close":
        try:
            await q.message.delete()
        except Exception:
            await q.message.edit_text("Đã đóng menu IPTV.")
        return

    if data == "iptv:noop":
        return await q.answer("Đây là chỉ báo trang.", cache_time=2)

    if data.startswith("iptv:pg:"):
        try:
            page = int(data.split(":")[-1])
        except ValueError:
            page = 0
        kb = _build_page_keyboard(channels, page)
        try:
            await q.message.edit_text(
                "📺 **IPTV Việt Nam**\nChọn kênh để xem link:",
                reply_markup=kb,
                disable_web_page_preview=True,
                parse_mode=None,
            )
        except Exception:
            await q.answer("Đã ở trang này.", cache_time=2)
        return

    if data.startswith("iptv:ch:"):
        try:
            idx = int(data.split(":")[-1])
        except ValueError:
            return await q.answer("Chỉ số kênh không hợp lệ.", show_alert=True)

        if idx < 0 or idx >= len(channels):
            return await q.answer("Kênh không tồn tại.", show_alert=True)

        page = idx // PAGE_SIZE
        name, url = channels[idx]
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🔗 Mở liên kết", url=url)],
                [
                    InlineKeyboardButton("🔙 Quay lại", callback_data=f"iptv:pg:{page}"),
                    InlineKeyboardButton("✖ Đóng", callback_data="iptv:close"),
                ],
            ]
        )
        text = (
            f"📺 **{name}**\n\n"
            f"🔗 Link:\n`{url}`\n\n"
            "👉 Bạn có thể copy link ở trên hoặc bấm **🔗 Mở liên kết**."
        )
        await q.message.edit_text(
            text,
            reply_markup=kb,
            disable_web_page_preview=True,
            parse_mode=None,
        )
        return

    await q.answer("Hành động không hỗ trợ.", cache_time=2)
