import asyncio
import contextlib
import os
import re
import time
from functools import partial
from glob import glob
from typing import Dict, Iterable, Optional, Union

from yt_dlp import YoutubeDL

from HasiiMusic.core.dir import DOWNLOAD_DIR as _DOWNLOAD_DIR, CACHE_DIR
from HasiiMusic.utils.cookie_handler import COOKIE_PATH
from HasiiMusic.utils.tuning import SEM
from config import (
    YTDLP_AUDIO_FORMAT,
    YTDLP_PREFERRED_AUDIO_BITRATE,
    YTDLP_VIDEO_FORMAT,
)

_COOKIES_FILE = str(COOKIE_PATH)

_inflight: Dict[str, asyncio.Future] = {}
_inflight_lock = asyncio.Lock()


# ===============================
# PROGRESS BAR
# ===============================

def progress_bar(percent: float) -> str:
    filled = int(percent / 5)
    bar = "█" * filled + "░" * (20 - filled)
    return f"[{bar}] {percent:.1f}%"


def ytdlp_progress(d, mystic):

    if not mystic:
        return

    if d["status"] == "downloading":

        percent = d.get("_percent_str", "0%").replace("%", "")
        speed = d.get("_speed_str", "0")
        eta = d.get("_eta_str", "0")

        try:
            percent_f = float(percent)
        except:
            percent_f = 0

        bar = progress_bar(percent_f)

        text = (
            "⬇️ **Đang tải từ YouTube...**\n\n"
            f"{bar}\n\n"
            f"⚡ **Tốc độ:** {speed}\n"
            f"⏳ **ETA:** {eta}"
        )

        if not hasattr(ytdlp_progress, "last"):
            ytdlp_progress.last = ""

        if percent != ytdlp_progress.last:
            ytdlp_progress.last = percent
            asyncio.create_task(mystic.edit_text(text))

    elif d["status"] == "finished":

        asyncio.create_task(
            mystic.edit_text("🔄 **Đang xử lý file...**")
        )


# ===============================
# COOKIE
# ===============================

def _cookiefile_path() -> Optional[str]:
    try:
        if _COOKIES_FILE and os.path.exists(_COOKIES_FILE):
            return _COOKIES_FILE
    except:
        pass
    return None


# ===============================
# YTDLP OPTIONS
# ===============================

def _ytdlp_base_opts(mystic=None):

    opts = {
        "outtmpl": f"{_DOWNLOAD_DIR}/%(id)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "overwrites": True,
        "continuedl": True,
        "concurrent_fragment_downloads": 16,
        "socket_timeout": 30,
        "retries": 5,
        "fragment_retries": 5,
        "cachedir": str(CACHE_DIR),
        "prefer_ffmpeg": True,
    }

    cookiefile = _cookiefile_path()

    if cookiefile:
        opts["cookiefile"] = cookiefile

    if mystic:
        opts["progress_hooks"] = [lambda d: ytdlp_progress(d, mystic)]

    return opts


# ===============================
# FILE SEARCH
# ===============================

def _find_downloaded_file(video_id: str) -> Optional[str]:

    base = f"{_DOWNLOAD_DIR}/{video_id}"

    for path in glob(f"{base}.*"):
        if os.path.exists(path):
            return path

    return None


# ===============================
# DOWNLOAD CORE
# ===============================

def _download_ytdlp(link: str, opts: Dict):

    try:

        with YoutubeDL(opts) as ydl:

            info = ydl.extract_info(link, download=False)

            vid = info.get("id")

            if not vid:
                return None

            existing = _find_downloaded_file(vid)

            if existing:
                return existing

            ydl.download([link])

            return _find_downloaded_file(vid)

    except Exception:
        return None


# ===============================
# MAIN DOWNLOAD FUNCTION
# ===============================

async def yt_dlp_download(
    link: str,
    type: str,
    format_id: str = None,
    title: str = None,
    mystic=None
) -> Optional[str]:

    loop = asyncio.get_running_loop()

    # AUDIO
    if type == "audio":

        opts = _ytdlp_base_opts(mystic)

        opts.update({
            "format": YTDLP_AUDIO_FORMAT
        })

        bitrate = YTDLP_PREFERRED_AUDIO_BITRATE

        if bitrate.isdigit():

            opts.setdefault("postprocessors", []).append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": bitrate,
            })

        return await loop.run_in_executor(
            None,
            partial(_download_ytdlp, link, opts)
        )

    # VIDEO
    if type == "video":

        opts = _ytdlp_base_opts(mystic)

        opts.update({
            "format": YTDLP_VIDEO_FORMAT
        })

        return await loop.run_in_executor(
            None,
            partial(_download_ytdlp, link, opts)
        )

    # SONG AUDIO
    if type == "song_audio" and format_id and title:

        safe_title = re.sub(r'[\\/*?:"<>|]+', "_", title)

        opts = _ytdlp_base_opts(mystic)

        opts.update({
            "format": format_id,
            "outtmpl": f"{_DOWNLOAD_DIR}/{safe_title}.%(ext)s",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })

        await loop.run_in_executor(
            None,
            lambda: YoutubeDL(opts).download([link])
        )

        return f"{_DOWNLOAD_DIR}/{safe_title}.mp3"

    # SONG VIDEO
    if type == "song_video" and format_id and title:

        safe_title = re.sub(r'[\\/*?:"<>|]+', "_", title)

        opts = _ytdlp_base_opts(mystic)

        opts.update({
            "format": f"{format_id}+140",
            "outtmpl": f"{_DOWNLOAD_DIR}/{safe_title}.mp4",
            "merge_output_format": "mp4",
        })

        await loop.run_in_executor(
            None,
            lambda: YoutubeDL(opts).download([link])
        )

        return f"{_DOWNLOAD_DIR}/{safe_title}.mp4"

    return None
    
async def download_audio_concurrent(link: str) -> Optional[str]:
    vid = extract_video_id(link)
    cached = file_exists(vid)
    if cached:
        return cached

    if not USE_API:
        return await yt_dlp_download(link, type="audio")

    key = f"rac:{link}"

    async def run():
        yt_task = asyncio.create_task(yt_dlp_download(link, type="audio"))
        api_task = asyncio.create_task(api_download_song(link))
        done, pending = await asyncio.wait(
            {yt_task, api_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for t in done:
            with contextlib.suppress(Exception):
                res = t.result()
                if res:
                    for p in pending:
                        p.cancel()
                        with contextlib.suppress(Exception, asyncio.CancelledError):
                            await p
                    return res
        for t in pending:
            with contextlib.suppress(Exception, asyncio.CancelledError):
                res = await t
                if res:
                    return res
        return None

    return await _dedup(key, lambda: _with_sem(run()))
