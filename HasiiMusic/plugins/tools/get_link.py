# -*- coding: utf-8 -*-
"""
Module: dl_link
----------------
Thêm vào dự án tram5 để tạo LIÊN KẾT tải một tệp âm thanh (audio/voice) về máy.

Cách dùng nhanh:
1) Sao chép file này vào: HasiiMusic/plugins/dl_link.py
2) Cài phụ thuộc: pip install fastapi uvicorn python-multipart
3) (Khuyến nghị) đặt biến môi trường:
   - DL_BASE_URL: http://<IP hoặc domain>:8088
   - DL_BIND: địa chỉ bind (mặc định 0.0.0.0)
   - DL_PORT: cổng server (mặc định 8088)
   - DL_KEEP_MIN: số phút link còn sống (mặc định 30)
   - DL_ONE_SHOT: 1 (mặc định) => link tải 1 lần tự huỷ; 0 => nhiều lần tới khi hết hạn
   - DL_ROOT: thư mục lưu tạm (mặc định ./_dl_cache)
4) Khởi động bot bình thường. Reply vào audio/voice rồi dùng /dl hoặc /getlink
"""

from __future__ import annotations
import os, time, socket, hashlib, secrets, threading, mimetypes
# ---- NẠP .env (để không phụ thuộc vào shell export) ----
try:
    from dotenv import load_dotenv
    load_dotenv()  # tự động đọc file .env ở thư mục dự án (nếu có)
except Exception:
    pass
   from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pathlib import Path
from typing import Dict, Optional, Tuple
from pyrogram import Client, filters
from pyrogram.types import Message
from HasiiMusic import app
import unicodedata, urllib.parse
# ==================== CẤU HÌNH ====================
DL_BASE_URL = os.environ.get("DL_BASE_URL", "")
DL_BIND = os.environ.get("DL_BIND", "0.0.0.0")
DL_PORT = int(os.environ.get("DL_PORT", "8088"))
DL_KEEP_MIN = int(os.environ.get("DL_KEEP_MIN", "30"))
DL_ONE_SHOT = os.environ.get("DL_ONE_SHOT", "1") == "1"
DL_ROOT = Path(os.environ.get("DL_ROOT", "./_dl_cache")).resolve()
DL_ROOT.mkdir(parents=True, exist_ok=True)

# ==================== FASTAPI SERVER ====================
try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse
    import uvicorn
except Exception:
    FastAPI = None  # type: ignore

_DL_TABLE: Dict[str, Tuple[Path, float, str, bool]] = {}
_DL_LOCK = threading.RLock()
app_fastapi: Optional[FastAPI] = None
_server_started = False
_server_lock = threading.RLock()

def _now() -> float: return time.time()
def _guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"
def _public_base() -> str:
    if DL_BASE_URL: return DL_BASE_URL.rstrip("/")
    try: ip = socket.gethostbyname(socket.gethostname())
    except Exception: ip = "127.0.0.1"
    return f"http://{ip}:{DL_PORT}"

def _cleanup_loop():
    while True:
        try:
            with _DL_LOCK:
                expired = [t for t, (_p, exp, _m, _o) in list(_DL_TABLE.items()) if _now() > exp]
                for t in expired:
                    path = _DL_TABLE[t][0]
                    try:
                        if path.exists(): path.unlink(missing_ok=True)
                    finally:
                        _DL_TABLE.pop(t, None)
        except Exception: pass
        time.sleep(30)
threading.Thread(target=_cleanup_loop, name="dl_cleanup", daemon=True).start()

def ensure_server_running() -> None:
    global app_fastapi, _server_started
    if FastAPI is None:
        raise RuntimeError("Cần cài fastapi & uvicorn: pip install fastapi uvicorn python-multipart")
    with _server_lock:
        if _server_started:
            return
        app_fastapi = FastAPI(title="tram5-dl-link", version="1.0.1")

        @app_fastapi.get("/")
        def root():
            return {"ok": True, "service": "tram5-dl-link", "ttl_min": DL_KEEP_MIN, "one_shot": DL_ONE_SHOT}

        @app_fastapi.get("/dl/{token}")
        def download(token: str):
            import unicodedata, urllib.parse
            with _DL_LOCK:
                meta = _DL_TABLE.get(token)
                if not meta:
                    raise HTTPException(status_code=404, detail="Token không hợp lệ hoặc đã hết hạn")
                path, exp, mime, one_shot = meta
                if _now() > exp:
                    _DL_TABLE.pop(token, None)
                    try:
                        path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    raise HTTPException(status_code=410, detail="Token hết hạn")
                if not path.exists():
                    _DL_TABLE.pop(token, None)
                    raise HTTPException(status_code=404, detail="Tệp không còn tồn tại")
                orig_name = path.name
                ascii_name = unicodedata.normalize("NFKD", orig_name).encode("ascii", "ignore").decode() or "file"
                if not os.path.splitext(ascii_name)[1] and os.path.splitext(orig_name)[1]:
                    ascii_name += os.path.splitext(orig_name)[1]
                utf8_quoted = urllib.parse.quote(orig_name.encode("utf-8"))
                content_disp = "attachment; filename=\"%s\"; filename*=UTF-8''%s" % (ascii_name, utf8_quoted)
                headers = {"Cache-Control": "no-store", "Content-Disposition": content_disp}
                if one_shot:
                    _DL_TABLE.pop(token, None)
                    def _del_later(p: Path):
                        time.sleep(5)
                        try:
                            p.unlink(missing_ok=True)
                        except Exception:
                            pass
                    threading.Thread(target=_del_later, args=(path,), daemon=True).start()
                return FileResponse(str(path), headers=headers, media_type=mime)

        def _run():
            uvicorn.run(app_fastapi, host=DL_BIND, port=DL_PORT, log_level="info")

        threading.Thread(target=_run, name="dl_link_server", daemon=True).start()
        _server_started = True

# ==================== TIỆN ÍCH ====================
async def _download_audio_to_temp(client: Client, msg: Message) -> Path:
    if getattr(msg, "audio", None):
        media, name = msg.audio, msg.audio.file_name or f"audio_{msg.id}.mp3"
    elif getattr(msg, "voice", None):
        media, name = msg.voice, f"voice_{msg.id}.ogg"
    else:
        raise ValueError("Tin nhắn không có audio/voice")
    safe = "".join(ch if ch.isalnum() or ch in (".", "_", "-") else "_" for ch in name)
    out = DL_ROOT / safe
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists(): await client.download_media(msg, file_name=str(out))
    return out.resolve()

def _make_token(path: Path, minutes: int, mime: str, one_shot: bool = True) -> str:
    payload = f"{path}|{minutes}|{mime}|{one_shot}|{_now()}|{secrets.token_urlsafe(12)}"
    token = hashlib.sha256(payload.encode()).hexdigest()[:32]
    with _DL_LOCK: _DL_TABLE[token] = (path, _now() + minutes * 60.0, mime, one_shot)
    return token

def _build_url(token: str) -> str: return f"{_public_base()}/dl/{token}"

# ==================== LỆNH /dl & /getlink ====================
@app.on_message(filters.command(["dl", "getlink"]) & (filters.private | filters.group))
async def dl_command(client: Client, message: Message):
    try: ensure_server_running()
    except Exception as e:
        await message.reply_text(f"❌ Không khởi chạy được server tải: {e}")
        return
    replied = message.reply_to_message
    if not replied:
        await message.reply_text("Hãy reply vào 1 tin nhắn có audio/voice rồi dùng /dl")
        return
    try: path = await _download_audio_to_temp(client, replied)
    except Exception as e:
        await message.reply_text(f"❌ Không lấy được audio/voice: {e}")
        return
    mime = _guess_mime(path)
token = _make_token(path, DL_KEEP_MIN, mime, one_shot=DL_ONE_SHOT)
url = _build_url(token)

bullet = "(1 lần)" if DL_ONE_SHOT else "(nhiều lần)"
text = (
    "🔗 Link tải sẵn sàng\n\n"
    f"• File: {path.name}\n"
    f"• Loại: {mime}\n"
    f"• Hết hạn: ~{DL_KEEP_MIN} phút {bullet}\n"
)

kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬇️ Tải file", url=url)]])
await message.reply_text(text, reply_markup=kb, disable_web_page_preview=True, parse_mode=None)

# ==================== API nội bộ ====================
async def create_download_link_from_message(client: Client, msg: Message, *, minutes: Optional[int] = None, one_shot: Optional[bool] = None) -> str:
    ensure_server_running()
    path = await _download_audio_to_temp(client, msg)
    mime = _guess_mime(path)
    token = _make_token(path, minutes or DL_KEEP_MIN, mime, one_shot=DL_ONE_SHOT if one_shot is None else one_shot)
    return _build_url(token)

# ==================== /dl_status ====================
@app.on_message(filters.command(["dl_status"]))
async def dl_status(client: Client, message: Message):
    try:
        ensure_server_running()
        base = _public_base()
        await message.reply_text(
            "✅ dl_link hoạt động.\n"
            f"• Base: {base}\n"
            f"• Port: {DL_PORT}\n"
            f"• TTL mặc định: {DL_KEEP_MIN} phút\n"
            f"• One-shot: {DL_ONE_SHOT}\n"
            f"• Cache: {DL_ROOT}",
            disable_web_page_preview=True,
        )
    except Exception as e:
        await message.reply_text(f"❌ Lỗi: {e}")
