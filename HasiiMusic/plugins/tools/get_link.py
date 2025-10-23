-- coding: utf-8 --

""" Module: dl_link

Thêm vào dự án tram5 để tạo LIÊN KẾT tải 1 tệp âm thanh (audio/voice) về máy.

Cách dùng nhanh:

1. Sao chép file này vào thư mục: HasiiMusic/plugins/dl_link.py (hoặc bất kỳ thư mục plugin nào bạn đang dùng).


2. Cài thêm phụ thuộc: pip install fastapi uvicorn python-multipart (uvicorn dùng cho server nội bộ)


3. (Tuỳ chọn) Đặt biến môi trường:

DL_BASE_URL: URL công khai đến server tải, ví dụ: http://<IP hoặc domain>:8088 Nếu không đặt, module sẽ tự suy luận từ IP nội bộ (không khuyến nghị). Nên đặt rõ.

DL_BIND: địa chỉ bind server (mặc định "0.0.0.0").

DL_PORT: cổng server (mặc định 8088).

DL_KEEP_MIN: số phút link còn sống (mặc định 30).

DL_ONE_SHOT: 1 (mặc định) => link tải 1 lần tự huỷ; 0 => nhiều lần tới khi hết hạn.

DL_ROOT: thư mục lưu tạm file tải (mặc định ./_dl_cache).



4. Khởi động bot như bình thường. Plugin sẽ tự khởi server tải nền bằng FastAPI.


5. Trong Telegram: reply vào 1 tin nhắn có audio/voice rồi gõ /dl hoặc /getlink Bot sẽ trả về một URL tải trực tiếp. Mở trên điện thoại để tải về máy.



Lưu ý an toàn:

Link có chữ ký + hết hạn + (mặc định) chỉ tải 1 lần.

File chỉ tồn tại tạm thời và sẽ bị xoá khi hết hạn hoặc sau khi tải xong.

Không lộ bot_token.


Tương thích: Pyrogram (bot), Python 3.10+. """

import os import io import sys import time import json import mimetypes import socket import asyncio import hashlib import secrets import threading from pathlib import Path from typing import Dict, Optional, Tuple

from pyrogram import Client, filters from pyrogram.types import Message

=============== CẤU HÌNH ===============

DL_BASE_URL = os.environ.get("DL_BASE_URL", "")  # Nên đặt rõ, ví dụ: http://1.2.3.4:8088 DL_BIND = os.environ.get("DL_BIND", "0.0.0.0") DL_PORT = int(os.environ.get("DL_PORT", "8088")) DL_KEEP_MIN = int(os.environ.get("DL_KEEP_MIN", "30")) DL_ONE_SHOT = os.environ.get("DL_ONE_SHOT", "1") == "1" DL_ROOT = Path(os.environ.get("DL_ROOT", "./_dl_cache")).resolve()

DL_ROOT.mkdir(parents=True, exist_ok=True)

=============== FASTAPI SERVER ===============

try: from fastapi import FastAPI, HTTPException, Response from fastapi.responses import FileResponse, PlainTextResponse import uvicorn except Exception as e:  # pragma: no cover FastAPI = None  # type: ignore

Bảng phiên tạm: token -> (local_path, expire_ts, mime, one_shot)

_DL_TABLE: Dict[str, Tuple[Path, float, str, bool]] = {} _DL_LOCK = threading.RLock()

def _now() -> float: return time.time()

def _cleanup_loop(): while True: try: with _DL_LOCK: expired = [t for t, (p, exp, _m, _o) in _DL_TABLE.items() if _now() > exp] for t in expired: path = _DL_TABLE[t][0] try: if path.exists(): path.unlink(missing_ok=True) finally: _DL_TABLE.pop(t, None) except Exception: pass time.sleep(30)

_cleanup_thr = threading.Thread(target=_cleanup_loop, name="dl_cleanup", daemon=True) _cleanup_thr.start()

app_fastapi: Optional[FastAPI] = None _server_started = False _server_lock = threading.RLock()

def _guess_mime(path: Path) -> str: mime, _ = mimetypes.guess_type(str(path)) return mime or "application/octet-stream"

def _public_base() -> str: if DL_BASE_URL: return DL_BASE_URL.rstrip("/") # auto-guess: lấy IP bind (không khuyến nghị). Nên đặt DL_BASE_URL rõ ràng try: hostname = socket.gethostname() ip = socket.gethostbyname(hostname) except Exception: ip = "127.0.0.1" return f"http://{ip}:{DL_PORT}"

def ensure_server_running(): global app_fastapi, _server_started if FastAPI is None: raise RuntimeError("Bạn cần cài fastapi và uvicorn: pip install fastapi uvicorn python-multipart") with _server_lock: if _server_started: return app_fastapi = FastAPI(title="tram5-dl-link", version="1.0.0")

@app_fastapi.get("/")
    def root():
        return {"ok": True, "service": "tram5-dl-link", "expires_in_min": DL_KEEP_MIN}

    @app_fastapi.get("/dl/{token}")
    def download(token: str):
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

            headers = {
                "Content-Type": mime,
                "Cache-Control": "no-store",
                "Content-Disposition": f"attachment; filename=\"{path.name}\"",
            }

            # one-shot -> xoá mapping ngay lập tức, xoá file sau khi trả xong (best-effort)
            if one_shot:
                _DL_TABLE.pop(token, None)
                # Lên lịch xoá file sau 5 giây
                def _del_later(p: Path):
                    time.sleep(5)
                    try:
                        p.unlink(missing_ok=True)
                    except Exception:
                        pass
                threading.Thread(target=_del_later, args=(path,), daemon=True).start()

            return FileResponse(str(path), headers=headers, media_type=mime)

    # Chạy uvicorn trong thread riêng
    def _run():
        uvicorn.run(app_fastapi, host=DL_BIND, port=DL_PORT, log_level="info")

    t = threading.Thread(target=_run, name="dl_link_server", daemon=True)
    t.start()
    _server_started = True

=============== TIỆN ÍCH ===============

async def download_audio_to_temp(client: Client, msg: Message) -> Path: """Tải audio/voice về thư mục DL_ROOT, trả về Path tuyệt đối.""" media = None name = None if getattr(msg, "audio", None): media = msg.audio name = media.file_name or f"audio{msg.id}.mp3" elif getattr(msg, "voice", None): media = msg.voice name = f"voice_{msg.id}.ogg" else: raise ValueError("Tin nhắn không có audio/voice")

# Đảm bảo tên file an toàn
safe = "".join(ch if ch.isalnum() or ch in (".", "_", "-") else "_" for ch in name)
out = DL_ROOT / safe
out.parent.mkdir(parents=True, exist_ok=True)

# Nếu đã có, bỏ qua tải lại
if not out.exists():
    await client.download_media(msg, file_name=str(out))
return out.resolve()

def _make_token(path: Path, minutes: int, mime: str, one_shot: bool = True) -> str: payload = f"{path}|{minutes}|{mime}|{one_shot}|{_now()}|{secrets.token_urlsafe(12)}" token = hashlib.sha256(payload.encode()).hexdigest()[:32] with _DL_LOCK: _DL_TABLE[token] = (path, _now() + minutes * 60.0, mime, one_shot) return token

def _build_url(token: str) -> str: return f"{_public_base()}/dl/{token}"

=============== LỆNH /dl & /getlink ===============

@Client.on_message(filters.command(["dl", "getlink"]) & filters.private | filters.group) async def dl_command(client: Client, message: Message): try: ensure_server_running() except Exception as e: return await message.reply_text(f"❌ Không khởi chạy được server tải: {e}")

replied = message.reply_to_message
if not replied:
    return await message.reply_text("Hãy reply vào 1 tin nhắn có audio/voice rồi dùng /dl")

try:
    path = await _download_audio_to_temp(client, replied)
except Exception as e:
    return await message.reply_text(f"❌ Không lấy được audio/voice: {e}")

mime = _guess_mime(path)
token = _make_token(path, DL_KEEP_MIN, mime, one_shot=DL_ONE_SHOT)
url = _build_url(token)

mins = DL_KEEP_MIN
bullet = "(1 lần)" if DL_ONE_SHOT else "(nhiều lần)"
text = (
    "🔗 **Link tải sẵn sàng**\n\n"
    f"• File: `{path.name}`\n"
    f"• Loại: `{mime}`\n"
    f"• Hết hạn: ~{mins} phút {bullet}\n"
    f"• URL: {url}"
)
await message.reply_text(text, disable_web_page_preview=True)

=============== HELPER: Tạo link từ file đã có (API nội bộ cho các module khác) ===============

async def create_download_link_from_message(client: Client, msg: Message, *, minutes: Optional[int] = None, one_shot: Optional[bool] = None) -> str: """Cho phép module khác gọi: đưa vào msg (audio/voice), trả về URL tải""" ensure_server_running() path = await _download_audio_to_temp(client, msg) mime = _guess_mime(path) token = _make_token(path, minutes or DL_KEEP_MIN, mime, one_shot=DL_ONE_SHOT if one_shot is None else one_shot) return _build_url(token)

=============== THÔNG BÁO KHỞI ĐỘNG (tuỳ chọn) ===============

@Client.on_message(filters.command(["dl_status"])) async def dl_status(client: Client, message: Message): try: ensure_server_running() base = _public_base() await message.reply_text( "✅ dl_link hoạt động.\n" f"• Base: {base}\n" f"• Port: {DL_PORT}\n" f"• TTL mặc định: {DL_KEEP_MIN} phút\n" f"• One-shot: {DL_ONE_SHOT}\n" f"• Cache: {DL_ROOT}", disable_web_page_preview=True, ) except Exception as e: await message.reply_text(f"❌ Lỗi: {e}")
