import asyncio
import os
from datetime import datetime, timedelta
from typing import Union

from ntgcalls import TelegramServerError
from pyrogram import Client
from pyrogram.errors import FloodWait, ChatAdminRequired
from pyrogram.types import InlineKeyboardMarkup
from pytgcalls import PyTgCalls
from pytgcalls.exceptions import NoActiveGroupCall
from pytgcalls.types import AudioQuality, ChatUpdate, MediaStream, StreamEnded, Update, VideoQuality

import config
from strings import get_string
from HasiiMusic import LOGGER, YouTube, app
from HasiiMusic.misc import db
from HasiiMusic.utils.database import (
    add_active_chat,
    add_active_video_chat,
    get_lang,
    get_loop,
    group_assistant,
    is_autoend,
    music_on,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
)
from HasiiMusic.utils.exceptions import AssistantErr
from HasiiMusic.utils.formatters import check_duration, seconds_to_min, speed_converter
from HasiiMusic.utils.inline.play import stream_markup
from HasiiMusic.utils.stream.autoclear import auto_clean
from HasiiMusic.utils.thumbnails import get_thumb
from HasiiMusic.utils.errors import capture_internal_err, send_large_error

autoend = {}
counter = {}

#def dynamic_media_stream(path: str, video: bool = False, ffmpeg_params: str = None) -> MediaStream:
    #return MediaStream(
        #audio_path=path,
        #media_path=path,
        #audio_parameters=AudioQuality.MEDIUM if video else AudioQuality.STUDIO,
        #video_parameters=VideoQuality.HD_720p if video else VideoQuality.SD_360p,
        #video_flags=(MediaStream.Flags.AUTO_DETECT if video else MediaStream.Flags.IGNORE),
        #ffmpeg_parameters=ffmpeg_params,
    #)
# === BEGIN PATCH dynamic_media_stream ===
def dynamic_media_stream(path: str, video: bool = False, ffmpeg_params: str = None) -> MediaStream:
    """
    - Giữ video nhưng ép cấu hình 'nhẹ' để tránh đụng SIMD/encoder nặng.
    - Cho phép override qua ENV:
        VIDEO_MAX_RES:  "240" | "360" (mặc định 360)
        VIDEO_FPS:      số nguyên, mặc định 15
        VIDEO_BR_K:     bitrate kbps, mặc định 600
        VIDEO_SAFE:     "1" để luôn chèn ffmpeg_parameters an toàn
    """
    # --- defaults an toàn ---
    max_res = os.getenv("VIDEO_MAX_RES", "360")
    fps = int(os.getenv("VIDEO_FPS", "15"))
    br_k = int(os.getenv("VIDEO_BR_K", "600"))
    force_safe = os.getenv("VIDEO_SAFE", "1") == "1"

    # Chọn enum chất lượng thấp thay vì HD_720p
    vq = VideoQuality.SD_360p if (video and max_res == "360") else (
         VideoQuality.SD_240p if video else VideoQuality.SD_480p
    )
    aq = AudioQuality.MEDIUM if video else AudioQuality.STUDIO

    # FFmpeg “nhẹ”, baseline, zerolatency; khoá GOP đều để decoder dễ thở
    # FFmpeg “nhẹ” + GIỮ LUỒNG SỐNG
    safe_ffmpeg = (
        f'-vf "scale=-2:{max_res},fps={fps}" '
        f'-pix_fmt yuv420p '
        f'-c:v libx264 -profile:v baseline -level 3.1 '
        f'-preset veryfast -tune zerolatency '
        f'-g {fps*2} -keyint_min {fps*2} -sc_threshold 0 '
        f'-b:v {br_k}k -maxrate {br_k+100}k -bufsize {1200 if max_res=="360" else 800}k '
        f'-c:a aac -b:a 96k -ac 2 -ar 48000 '
        f'-fflags +genpts -flags +global_header -flush_packets 1 '
        f'-analyzeduration 2M -probesize 2M '
        f'-reconnect 1 -reconnect_streamed 1 -reconnect_on_network_error 1 -reconnect_delay_max 2'
    )

    return MediaStream(
        audio_path=path,
        media_path=path,
        audio_parameters=aq,
        video_parameters=vq if video else VideoQuality.SD_480p,
        video_flags=(MediaStream.Flags.AUTO_DETECT if video else MediaStream.Flags.IGNORE),
        ffmpeg_parameters=(ffmpeg_params or safe_ffmpeg) if (video and (force_safe or not ffmpeg_params)) else ffmpeg_params,
    )
# === END PATCH dynamic_media_stream ===

async def _clear_(chat_id: int) -> None:
    popped = db.pop(chat_id, None)
    if popped:
        await auto_clean(popped)
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)
    await set_loop(chat_id, 0)

class Call:
    def __init__(self):
        self.userbot1 = Client(
            "HasiiXAssis1", config.API_ID, config.API_HASH, session_string=config.STRING1
        ) if config.STRING1 else None
        self.one = PyTgCalls(self.userbot1) if self.userbot1 else None

        self.userbot2 = Client(
            "HasiiXAssis2", config.API_ID, config.API_HASH, session_string=config.STRING2
        ) if config.STRING2 else None
        self.two = PyTgCalls(self.userbot2) if self.userbot2 else None

        self.userbot3 = Client(
            "HasiiXAssis3", config.API_ID, config.API_HASH, session_string=config.STRING3
        ) if config.STRING3 else None
        self.three = PyTgCalls(self.userbot3) if self.userbot3 else None

        self.userbot4 = Client(
            "HasiiXAssis4", config.API_ID, config.API_HASH, session_string=config.STRING4
        ) if config.STRING4 else None
        self.four = PyTgCalls(self.userbot4) if self.userbot4 else None

        self.userbot5 = Client(
            "HasiiXAssis5", config.API_ID, config.API_HASH, session_string=config.STRING5
        ) if config.STRING5 else None
        self.five = PyTgCalls(self.userbot5) if self.userbot5 else None

        self.active_calls: set[int] = set()


    @capture_internal_err
    async def pause_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.pause(chat_id)

    @capture_internal_err
    async def resume_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.resume(chat_id)

    @capture_internal_err
    async def mute_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.mute(chat_id)

    @capture_internal_err
    async def unmute_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.unmute(chat_id)

    @capture_internal_err
    async def stop_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await _clear_(chat_id)
        if chat_id not in self.active_calls:
            return
        try:
            await assistant.leave_call(chat_id)
        except Exception:
            pass
        finally:
            self.active_calls.discard(chat_id)


    @capture_internal_err
    async def force_stop_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        try:
            check = db.get(chat_id)
            if check:
                check.pop(0)
        except (IndexError, KeyError):
            pass
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        await _clear_(chat_id)
        if chat_id not in self.active_calls:
            return
        try:
            await assistant.leave_call(chat_id)
        except Exception:
            pass
        finally:
            self.active_calls.discard(chat_id)


    @capture_internal_err
    async def skip_stream(self, chat_id: int, link: str, video: Union[bool, str] = None, image: Union[bool, str] = None) -> None:
        assistant = await group_assistant(self, chat_id)
        stream = dynamic_media_stream(path=link, video=bool(video))
        try:
            await assistant.play(chat_id, stream)
        except Exception:
            ultra_ffmpeg = (
    '-vf "scale=-2:240,fps=15" -pix_fmt yuv420p '
    '-c:v libx264 -profile:v baseline -level 3.0 '
    '-preset ultrafast -tune zerolatency '
    '-g 30 -keyint_min 30 -sc_threshold 0 '
    '-b:v 450k -maxrate 500k -bufsize 800k '
    '-c:a aac -b:a 96k -ac 2 -ar 48000 '
    '-fflags +genpts -flags +global_header -flush_packets 1 '
    '-analyzeduration 2M -probesize 2M '
    '-reconnect 1 -reconnect_streamed 1 -reconnect_on_network_error 1 -reconnect_delay_max 2'
)
            stream2 = dynamic_media_stream(path=link, video=bool(video), ffmpeg_params=ultra_ffmpeg)
            await assistant.play(chat_id, stream2)

    @capture_internal_err
    async def vc_users(self, chat_id: int) -> list:
        assistant = await group_assistant(self, chat_id)
        participants = await assistant.get_participants(chat_id)
        return [p.user_id for p in participants if not p.is_muted]

    @capture_internal_err
    async def seek_stream(self, chat_id: int, file_path: str, to_seek: str, duration: str, mode: str) -> None:
        assistant = await group_assistant(self, chat_id)
        ffmpeg_params = f"-ss {to_seek} -to {duration}"
        is_video = mode == "video"
        stream = dynamic_media_stream(path=file_path, video=is_video, ffmpeg_params=ffmpeg_params)
        await assistant.play(chat_id, stream)

    @capture_internal_err
    async def speedup_stream(self, chat_id: int, file_path: str, speed: float, playing: list) -> None:
        if not isinstance(playing, list) or not playing or not isinstance(playing[0], dict):
            raise AssistantErr("Thông tin luồng không hợp lệ để tăng tốc độ.")

        assistant = await group_assistant(self, chat_id)
        base = os.path.basename(file_path)
        chatdir = os.path.join("playback", str(speed))
        os.makedirs(chatdir, exist_ok=True)
        out = os.path.join(chatdir, base)

        if not os.path.exists(out):
            vs = str(2.0 / float(speed))
            cmd = f"ffmpeg -i {file_path} -filter:v setpts={vs}*PTS -filter:a atempo={speed} {out}"
            proc = await asyncio.create_subprocess_shell(cmd, stdin=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await proc.communicate()

        dur = int(await asyncio.get_event_loop().run_in_executor(None, check_duration, out))
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration_min = seconds_to_min(dur)
        is_video = playing[0]["streamtype"] == "video"
        ffmpeg_params = f"-ss {played} -to {duration_min}"
        stream = dynamic_media_stream(path=out, video=is_video, ffmpeg_params=ffmpeg_params)

        if chat_id in db and db[chat_id] and db[chat_id][0].get("file") == file_path:
            await assistant.play(chat_id, stream)
        else:
            raise AssistantErr("Không khớp luồng trong quá trình tăng tốc.")

        db[chat_id][0].update({
            "played": con_seconds,
            "dur": duration_min,
            "seconds": dur,
            "speed_path": out,
            "speed": speed,
            "old_dur": db[chat_id][0].get("dur"),
            "old_second": db[chat_id][0].get("seconds"),
        })


    @capture_internal_err
    async def stream_call(self, link: str) -> None:
        assistant = await group_assistant(self, config.LOGGER_ID)
        try:
            # Tham số ffmpeg “nhẹ” giúp ffmpeg check sớm kết thúc:
            # -t 3: giới hạn chạy 3s trong bước check
            # -analyzeduration/-probesize: giảm thời gian dò
            # các cờ reconnect: ổn định link mạng
            ff_fast = (
                '-t 3 -analyzeduration 1M -probesize 1M -nostdin '
                '-reconnect 1 -reconnect_streamed 1 -reconnect_on_network_error 1 -reconnect_delay_max 2'
            )
            stream = dynamic_media_stream(path=link, video=False, ffmpeg_params=ff_fast)
            await assistant.play(config.LOGGER_ID, stream)
            await asyncio.sleep(8)
        except Exception:
            # Thử lần 2 với cấu hình “siêu nhẹ” 240p nếu là video test
            ultra = (
                '-t 3 -vf "scale=-2:240,fps=15" -pix_fmt yuv420p '
                '-c:v libx264 -profile:v baseline -level 3.0 -preset ultrafast -tune zerolatency '
                '-g 30 -keyint_min 30 -sc_threshold 0 '
                '-b:v 450k -maxrate 500k -bufsize 800k '
                '-c:a aac -b:a 96k -ac 2 -ar 48000 '
                '-analyzeduration 1M -probesize 1M -nostdin '
                '-reconnect 1 -reconnect_streamed 1 -reconnect_on_network_error 1 -reconnect_delay_max 2'
            )
            try:
                vstream = dynamic_media_stream(path=link, video=True, ffmpeg_params=ultra)
                await assistant.play(config.LOGGER_ID, vstream)
                await asyncio.sleep(8)
            except Exception:
                # Cuối cùng: bỏ qua bước test nếu mạng kém/nguồn treo
                pass
        finally:
            try:
                await assistant.leave_call(config.LOGGER_ID)
            except:
                pass

    @capture_internal_err
    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ) -> None:
        assistant = await group_assistant(self, chat_id)
        lang = await get_lang(chat_id)
        _ = get_string(lang)
        stream = dynamic_media_stream(path=link, video=bool(video))
        try:
            await assistant.play(chat_id, stream)
        except Exception as e:
            # Nếu encoder nổ (SIGILL / invalid opcode), thử hạ chất lượng xuống 240p
            ultra_ffmpeg = (
    '-vf "scale=-2:240,fps=15" -pix_fmt yuv420p '
    '-c:v libx264 -profile:v baseline -level 3.0 '
    '-preset ultrafast -tune zerolatency '
    '-g 30 -keyint_min 30 -sc_threshold 0 '
    '-b:v 450k -maxrate 500k -bufsize 800k '
    '-c:a aac -b:a 96k -ac 2 -ar 48000 '
    '-fflags +genpts -flags +global_header -flush_packets 1 '
    '-analyzeduration 2M -probesize 2M '
    '-reconnect 1 -reconnect_streamed 1 -reconnect_on_network_error 1 -reconnect_delay_max 2'
)
            try:
                stream2 = dynamic_media_stream(path=link, video=bool(video), ffmpeg_params=ultra_ffmpeg)
                await assistant.play(chat_id, stream2)
            except Exception as e2:
                # fallback audio-only
                if video:
                    safe_audio = dynamic_media_stream(path=link, video=False)
                    await assistant.play(chat_id, safe_audio)
                    await app.send_message(
                        original_chat_id,
                        "⚠️ CPU không hỗ trợ video (AVX). Đang phát audio-only."
                    )
                else:
                    raise
        except (NoActiveGroupCall, ChatAdminRequired):
            raise AssistantErr(_["call_8"])
        except TelegramServerError:
            raise AssistantErr(_["call_10"])
        except Exception as e:
            raise AssistantErr(
                f"Không thể tham gia cuộc gọi nhóm.\nLý do: {e}"
            )
        self.active_calls.add(chat_id)
        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video:
            await add_active_video_chat(chat_id)

        if await is_autoend():
            counter[chat_id] = {}
            users = len(await assistant.get_participants(chat_id))
            if users == 1:
                autoend[chat_id] = datetime.now() + timedelta(minutes=1)


    @capture_internal_err
    async def play(self, client, chat_id: int) -> None:
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)
        try:
            if loop == 0:
                popped = check.pop(0)
            else:
                loop = loop - 1
                await set_loop(chat_id, loop)
            await auto_clean(popped)
            if not check:
                    await _clear_(chat_id)
                    if chat_id in self.active_calls:
                        try:
                            await client.leave_call(chat_id)
                        except NoActiveGroupCall:
                            pass
                        except Exception:
                            pass
                        finally:
                            self.active_calls.discard(chat_id)
                    return
        except:
            try:
                await _clear_(chat_id)
                return await client.leave_call(chat_id)
            except:
                return
        else:
            queued = check[0]["file"]
            language = await get_lang(chat_id)
            _ = get_string(language)
            title = (check[0]["title"]).title()
            user = check[0]["by"]
            original_chat_id = check[0]["chat_id"]
            streamtype = check[0]["streamtype"]
            videoid = check[0]["vidid"]
            db[chat_id][0]["played"] = 0

            exis = (check[0]).get("old_dur")
            if exis:
                db[chat_id][0]["dur"] = exis
                db[chat_id][0]["seconds"] = check[0]["old_second"]
                db[chat_id][0]["speed_path"] = None
                db[chat_id][0]["speed"] = 1.0

            video = True if str(streamtype) == "video" else False

            if "live_" in queued:
                n, link = await YouTube.video(videoid, True)
                if n == 0:
                    return await app.send_message(original_chat_id, text=_["call_6"])

                stream = dynamic_media_stream(path=link, video=video)
                try:
                    await client.play(chat_id, stream)
                except Exception as e:
                    ultra_ffmpeg = (
    '-vf "scale=-2:240,fps=15" -pix_fmt yuv420p '
    '-c:v libx264 -profile:v baseline -level 3.0 '
    '-preset ultrafast -tune zerolatency '
    '-g 30 -keyint_min 30 -sc_threshold 0 '
    '-b:v 450k -maxrate 500k -bufsize 800k '
    '-c:a aac -b:a 96k -ac 2 -ar 48000 '
    '-fflags +genpts -flags +global_header -flush_packets 1 '
    '-analyzeduration 2M -probesize 2M '
    '-reconnect 1 -reconnect_streamed 1 -reconnect_on_network_error 1 -reconnect_delay_max 2'
)
                    try:
                        stream2 = dynamic_media_stream(path=..., video=video, ffmpeg_params=ultra_ffmpeg)
                        await client.play(chat_id, stream2)
                    except Exception:
                        if video:
                            audio_safe = dynamic_media_stream(path=..., video=False)
                            await client.play(chat_id, audio_safe)
                            await app.send_message(
                            original_chat_id,
                            "⚠️ CPU yếu, tự động chuyển audio-only."
                        )
                        else:
                            raise

                img = await get_thumb(videoid)
                button = stream_markup(_, chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title[:23],
                        check[0]["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

            elif "vid_" in queued:
                mystic = await app.send_message(original_chat_id, _["call_7"])
                try:
                    file_path, direct = await YouTube.download(
                        videoid,
                        mystic,
                        videoid=True,
                        video=True if str(streamtype) == "video" else False,
                    )
                except:
                    return await mystic.edit_text(
                        _["call_6"], disable_web_page_preview=True
                    )

                stream = dynamic_media_stream(path=link, video=video)
                try:
                    await client.play(chat_id, stream)
                except Exception as e:
                    ultra_ffmpeg = (
    '-vf "scale=-2:240,fps=15" -pix_fmt yuv420p '
    '-c:v libx264 -profile:v baseline -level 3.0 '
    '-preset ultrafast -tune zerolatency '
    '-g 30 -keyint_min 30 -sc_threshold 0 '
    '-b:v 450k -maxrate 500k -bufsize 800k '
    '-c:a aac -b:a 96k -ac 2 -ar 48000 '
    '-fflags +genpts -flags +global_header -flush_packets 1 '
    '-analyzeduration 2M -probesize 2M '
    '-reconnect 1 -reconnect_streamed 1 -reconnect_on_network_error 1 -reconnect_delay_max 2'
)
                    try:
                        stream2 = dynamic_media_stream(path=..., video=video, ffmpeg_params=ultra_ffmpeg)
                        await client.play(chat_id, stream2)
                    except Exception:
                        if video:
                            audio_safe = dynamic_media_stream(path=..., video=False)
                            await client.play(chat_id, audio_safe)
                            await app.send_message(
                            original_chat_id,
                            "⚠️ CPU yếu, tự động chuyển audio-only."
                        )
                        else:
                            raise
                img = await get_thumb(videoid)
                button = stream_markup(_, chat_id)
                await mystic.delete()
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title[:23],
                        check[0]["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"

            elif "index_" in queued:
                stream = dynamic_media_stream(path=link, video=video)
                try:
                    await client.play(chat_id, stream)
                except Exception as e:
                    ultra_ffmpeg = (
    '-vf "scale=-2:240,fps=15" -pix_fmt yuv420p '
    '-c:v libx264 -profile:v baseline -level 3.0 '
    '-preset ultrafast -tune zerolatency '
    '-g 30 -keyint_min 30 -sc_threshold 0 '
    '-b:v 450k -maxrate 500k -bufsize 800k '
    '-c:a aac -b:a 96k -ac 2 -ar 48000 '
    '-fflags +genpts -flags +global_header -flush_packets 1 '
    '-analyzeduration 2M -probesize 2M '
    '-reconnect 1 -reconnect_streamed 1 -reconnect_on_network_error 1 -reconnect_delay_max 2'
)
                    try:
                        stream2 = dynamic_media_stream(path=..., video=video, ffmpeg_params=ultra_ffmpeg)
                        await client.play(chat_id, stream2)
                    except Exception:
                        if video:
                            audio_safe = dynamic_media_stream(path=..., video=False)
                            await client.play(chat_id, audio_safe)
                            await app.send_message(
                            original_chat_id,
                            "⚠️ CPU yếu, tự động chuyển audio-only."
                        )
                        else:
                            raise
                button = stream_markup(_, chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=config.STREAM_IMG_URL,
                    caption=_["stream_2"].format(user),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

            else:
                stream = dynamic_media_stream(path=link, video=video)
                try:
                    await client.play(chat_id, stream)
                except Exception as e:
                    ultra_ffmpeg = (
    '-vf "scale=-2:240,fps=15" -pix_fmt yuv420p '
    '-c:v libx264 -profile:v baseline -level 3.0 '
    '-preset ultrafast -tune zerolatency '
    '-g 30 -keyint_min 30 -sc_threshold 0 '
    '-b:v 450k -maxrate 500k -bufsize 800k '
    '-c:a aac -b:a 96k -ac 2 -ar 48000 '
    '-fflags +genpts -flags +global_header -flush_packets 1 '
    '-analyzeduration 2M -probesize 2M '
    '-reconnect 1 -reconnect_streamed 1 -reconnect_on_network_error 1 -reconnect_delay_max 2'
)
                    try:
                        stream2 = dynamic_media_stream(path=..., video=video, ffmpeg_params=ultra_ffmpeg)
                        await client.play(chat_id, stream2)
                    except Exception:
                        if video:
                            audio_safe = dynamic_media_stream(path=..., video=False)
                            await client.play(chat_id, audio_safe)
                            await app.send_message(
                            original_chat_id,
                            "⚠️ CPU yếu, tự động chuyển audio-only."
                        )
                        else:
                            raise

                if videoid == "telegram":
                    button = stream_markup(_, chat_id)
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=(
                            config.TELEGRAM_AUDIO_URL
                            if str(streamtype) == "audio"
                            else config.TELEGRAM_VIDEO_URL
                        ),
                        caption=_["stream_1"].format(
                            config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"

                elif videoid == "soundcloud":
                    button = stream_markup(_, chat_id)
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=config.SOUNCLOUD_IMG_URL,
                        caption=_["stream_1"].format(
                            config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"

                else:
                    img = await get_thumb(videoid)
                    button = stream_markup(_, chat_id)
                    try:
                        run = await app.send_photo(
                            chat_id=original_chat_id,
                            photo=img,
                            caption=_["stream_1"].format(
                                f"https://t.me/{app.username}?start=info_{videoid}",
                                title[:23],
                                check[0]["dur"],
                                user,
                            ),
                            reply_markup=InlineKeyboardMarkup(button),
                        )
                    except FloodWait as e:
                        LOGGER(__name__).warning(f"FloodWait: Sleeping for {e.value}")
                        await asyncio.sleep(e.value)
                        run = await app.send_photo(
                            chat_id=original_chat_id,
                            photo=img,
                            caption=_["stream_1"].format(
                                f"https://t.me/{app.username}?start=info_{videoid}",
                                title[:23],
                                check[0]["dur"],
                                user,
                            ),
                            reply_markup=InlineKeyboardMarkup(button),
                        )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"


    async def start(self) -> None:
        LOGGER(__name__).info("Starting PyTgCalls Clients...")
        if config.STRING1:
            await self.one.start()
        if config.STRING2:
            await self.two.start()
        if config.STRING3:
            await self.three.start()
        if config.STRING4:
            await self.four.start()
        if config.STRING5:
            await self.five.start()

    @capture_internal_err
    async def ping(self) -> str:
        pings = []
        if config.STRING1:
            pings.append(self.one.ping)
        if config.STRING2:
            pings.append(self.two.ping)
        if config.STRING3:
            pings.append(self.three.ping)
        if config.STRING4:
            pings.append(self.four.ping)
        if config.STRING5:
            pings.append(self.five.ping)
        return str(round(sum(pings) / len(pings), 3)) if pings else "0.0"

    @capture_internal_err
    async def decorators(self) -> None:
        assistants = list(filter(None, [self.one, self.two, self.three, self.four, self.five]))

        CRITICAL = (
            ChatUpdate.Status.KICKED
            | ChatUpdate.Status.LEFT_GROUP
            | ChatUpdate.Status.CLOSED_VOICE_CHAT
            | ChatUpdate.Status.DISCARDED_CALL
            | ChatUpdate.Status.BUSY_CALL
        )

        async def unified_update_handler(client, update: Update) -> None:
            try:
                if isinstance(update, ChatUpdate):
                    status = update.status
                    if (status & ChatUpdate.Status.LEFT_CALL) or (status & CRITICAL):
                        await self.stop_stream(update.chat_id)
                        return

                elif isinstance(update, StreamEnded):
                    if update.stream_type == StreamEnded.Type.AUDIO:
                        assistant = await group_assistant(self, update.chat_id)
                        await self.play(assistant, update.chat_id)

            except Exception:
                import sys, traceback
                exc_type, exc_obj, exc_tb = sys.exc_info()
                full_trace = "".join(traceback.format_exception(exc_type, exc_obj, exc_tb))
                caption = (
                    f"🚨 <b>Stream Update Error</b>\n"
                    f"📍 <b>Update Type:</b> <code>{type(update).__name__}</code>\n"
                    f"📍 <b>Error Type:</b> <code>{exc_type.__name__}</code>"
                )
                filename = f"update_error_{getattr(update, 'chat_id', 'unknown')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                await send_large_error(full_trace, caption, filename)

        for assistant in assistants:
            assistant.on_update()(unified_update_handler)


JARVIS = Call()
