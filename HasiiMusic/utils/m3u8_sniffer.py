# HasiiMusic/utils/m3u8_sniffer.py
# -*- coding: utf-8 -*-

import asyncio
import contextlib
import json
import re
import subprocess
from typing import Dict, List, Optional, Tuple, Union

try:
    from playwright.async_api import async_playwright, BrowserContext, Page
except Exception as e:
    async_playwright = None
# --- bổ sung vào HasiiMusic/utils/m3u8_sniffer.py (thêm vào phía trên cùng với imports hiện có)
import json
import os
from urllib.parse import urlparse
from typing import Any

COOKIES_STORE_DIR = os.environ.get("M3U8_COOKIES_DIR", "/root/.tram5_cookies")


def _ensure_cookie_dir():
    try:
        os.makedirs(COOKIES_STORE_DIR, exist_ok=True)
    except Exception:
        pass


def _domain_key(url: str) -> str:
    p = urlparse(url)
    # lưu theo hostname, bỏ www để gom
    host = p.hostname or "default"
    if host.startswith("www."):
        host = host[4:]
    return host


async def fetch_and_store_cookies_for_domain(
    url: str,
    user_agent: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    headless: bool = True,
    wait_secs: int = 12,
) -> List[Dict[str, Any]]:
    """
    Mở page bằng Playwright, load url, đợi networkidle, rồi lấy cookies từ context,
    lưu vào file: {COOKIES_STORE_DIR}/{domain}.json
    Trả về list cookie dict theo định dạng Playwright (name,value,domain,path,...)
    """
    _ensure_cookie_dir()
    domain = _domain_key(url)
    outpath = os.path.join(COOKIES_STORE_DIR, f"{domain}.json")

    if async_playwright is None:
        return []

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=headless, args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx_args = {}
        if user_agent:
            ctx_args["user_agent"] = user_agent
        if headers:
            ctx_args["extra_http_headers"] = headers
        context = await browser.new_context(**ctx_args)
        page = await context.new_page()
        # Đi tới trang, đợi networkidle — mục tiêu để server set-cookie
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=wait_secs*1000)
        except Exception:
            # vẫn tiếp tục lấy cookie nếu load thất bại nhẹ
            pass

        # Một số site set cookie khi bấm play / click -> thử click nhẹ
        with contextlib.suppress(Exception):
            btn = await page.query_selector("button, .vjs-big-play-button, .jw-icon-play")
            if btn:
                await btn.click(force=True)
                await asyncio.sleep(0.5)
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass

        cookies = await context.cookies()
        # Lưu ra file
        try:
            with open(outpath, "w", encoding="utf-8") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        await context.close()
        await browser.close()

    return cookies


def load_cookies_for_domain(url: str) -> List[Dict[str, Any]]:
    """
    Load cookies từ file theo domain, trả về [] nếu không có.
    """
    _ensure_cookie_dir()
    domain = _domain_key(url)
    path = os.path.join(COOKIES_STORE_DIR, f"{domain}.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # playwrigh-cookie format is acceptable
            if isinstance(data, list):
                return data
    except Exception:
        return []
    return []


async def ensure_cookies_for_domain(
    url: str,
    user_agent: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    headless: bool = True,
    force_refresh: bool = False,
) -> List[Dict[str, Any]]:
    """
    Kiểm tra file cookies có sẵn; nếu không có hoặc force_refresh thì fetch mới và lưu.
    """
    existing = load_cookies_for_domain(url)
    if existing and not force_refresh:
        return existing
    # fetch và lưu
    return await fetch_and_store_cookies_for_domain(
        url=url, user_agent=user_agent, headers=headers, headless=headless
    )


# --- cập nhật sniff_m3u8: khi cookies=None, tự gọi ensure_cookies_for_domain để tạo/nạp
async def sniff_m3u8(
    url: str,
    user_agent: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    cookies: Optional[List[Dict[str, Union[str, bool]]]] = None,
    prefer_browser: bool = True,
    wait_secs: int = 20,
    headless: bool = True,
    auto_create_cookies: bool = True,   # <-- thêm param mới mặc định True
    force_refresh_cookies: bool = False,
) -> Tuple[Optional[str], List[str]]:
    """
    Trả về (best_m3u8, all_m3u8s)
    - Nếu cookies không truyền vào và auto_create_cookies=True thì sẽ tự load
      cookies từ file theo domain, nếu không có sẽ fetch bằng Playwright và lưu lại.
    """
    all_urls: List[str] = []
    best: Optional[str] = None

    # nếu user không truyền cookies, thử nạp / tạo cookies tự động (useful cho nhiều site)
    if not cookies and auto_create_cookies:
        try:
            # lấy cookies theo domain URL
            c = await ensure_cookies_for_domain(
                url=url,
                user_agent=user_agent,
                headers=headers,
                headless=headless,
                force_refresh=force_refresh_cookies,
            )
            # chuyển định dạng cookies sang dạng Playwright context.add_cookies chấp nhận
            if c:
                cookies = []
                for ck in c:
                    # chuẩn hoá keys: đảm bảo có domain & path & name/value
                    if "name" in ck and "value" in ck:
                        cookies.append(
                            {
                                "name": ck.get("name"),
                                "value": ck.get("value"),
                                "domain": ck.get("domain"),
                                "path": ck.get("path", "/"),
                                "expires": ck.get("expires", -1),
                                "httpOnly": ck.get("httpOnly", False),
                                "secure": ck.get("secure", False),
                            }
                        )
        except Exception:
            # không quá khắt khe — tiếp tục fallback normal
            cookies = cookies or []

    if prefer_browser:
        got = await _firefox_m3u8(
            url=url,
            user_agent=user_agent,
            headers=headers,
            cookies=cookies,
            wait_secs=wait_secs,
            headless=headless,
        )
        all_urls.extend(got)

        if not all_urls:
            all_urls.extend(_yt_dlp_guess(url))
    else:
        all_urls.extend(_yt_dlp_guess(url))
        if not all_urls:
            all_urls.extend(
                await _firefox_m3u8(
                    url=url,
                    user_agent=user_agent,
                    headers=headers,
                    cookies=cookies,
                    wait_secs=wait_secs,
                    headless=headless,
                )
            )

    all_urls = _uniq([u for u in all_urls if "data:" not in u and "blob:" not in u])
    best = _best_candidate(all_urls)
    return best, all_urls
M3U8_RX = re.compile(r"\.m3u8(\?.*)?$", re.IGNORECASE)
M3U8_CT = (
    "application/vnd.apple.mpegurl",
    "application/x-mpegurl",
    "audio/mpegurl",
    "application/mpegurl",
)

def _uniq(seq: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out

async def _firefox_m3u8(
    url: str,
    user_agent: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    cookies: Optional[List[Dict[str, Union[str, bool]]]] = None,
    wait_secs: int = 20,
    extra_clicks: bool = True,
    headless: bool = True,
) -> List[str]:
    """
    Dùng Playwright (Firefox) để bắt các request/response có đuôi .m3u8
    hoặc Content-Type m3u8.
    """
    if async_playwright is None:
        return []

    found: List[str] = []

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=headless, args=[
            # giảm fingerprint cơ bản
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ])
        ctx_args = {}
        if user_agent:
            ctx_args["user_agent"] = user_agent
        if headers:
            ctx_args["extra_http_headers"] = headers
        context: BrowserContext = await browser.new_context(**ctx_args)

        if cookies:
            with contextlib.suppress(Exception):
                await context.add_cookies(cookies)

        page: Page = await context.new_page()

        # Lắng nghe mọi request để bắt URL chứa .m3u8
        page.on("request", lambda req: (
            found.append(req.url) if M3U8_RX.search(req.url) else None
        ))

        # Lắng nghe response theo content-type
        async def _on_response(resp):
            try:
                ct = (resp.headers or {}).get("content-type", "")
                if any(ct.lower().startswith(x) for x in M3U8_CT):
                    found.append(resp.url)
            except Exception:
                pass

        page.on("response", lambda resp: asyncio.create_task(_on_response(resp)))

        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # Một số trang chỉ sinh m3u8 sau khi "Play"
        if extra_clicks:
            selectors = [
                'button[aria-label="Play"]',
                ".vjs-big-play-button",
                ".jw-icon-play",
                ".plyr__control--overlaid",
                "button.ytp-large-play-button",
                "video",
            ]
            for sel in selectors:
                with contextlib.suppress(Exception):
                    btn = await page.query_selector(sel)
                    if btn:
                        await btn.click(force=True)
                        await asyncio.sleep(0.5)

        # Đợi network ổn định một chút để gom request
        with contextlib.suppress(Exception):
            await page.wait_for_load_state("networkidle", timeout=wait_secs * 1000)

        # Cuộn nhẹ để kích hoạt lazy loads
        with contextlib.suppress(Exception):
            await page.mouse.wheel(0, 1000)
            await asyncio.sleep(1)

        # Chờ thêm (trong trường hợp player khởi động chậm)
        await asyncio.sleep(max(0, wait_secs - 3))

        await context.close()
        await browser.close()

    return _uniq([u for u in found if u and "blob:" not in u])

def _yt_dlp_guess(url: str, timeout: int = 25) -> List[str]:
    """
    Fallback: dùng yt-dlp để cố lấy direct link/m3u8.
    Lưu ý: không phải site nào cũng trả m3u8 qua -g.
    """
    cmd = [
        "yt-dlp",
        "-g",
        "--no-warnings",
        "--skip-download",
        "--no-check-certificates",
        "--allow-unplayable-formats",
        url,
    ]
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        lines = [l.strip() for l in (out.stdout or "").splitlines() if l.strip()]
        # Lọc các dòng là m3u8 trước
        m3u8_lines = [l for l in lines if M3U8_RX.search(l)]
        return _uniq(m3u8_lines or lines)
    except Exception:
        return []

def _best_candidate(urls: List[str]) -> Optional[str]:
    """
    Ưu tiên master playlist / có tham số quality / index / manifest.
    """
    if not urls:
        return None
    # ưu tiên các chuỗi trông giống master
    prefs = ["master.m3u8", "index.m3u8", "manifest.m3u8"]
    for p in prefs:
        for u in urls:
            if p in u.lower():
                return u
    # tiếp: có từ khóa quality/playlist/chunklist
    for u in urls:
        uu = u.lower()
        if any(k in uu for k in ["quality", "playlist", "chunklist", "hls"]):
            return u
    # mặc định: lấy cái đầu
    return urls[0]

async def sniff_m3u8(
    url: str,
    user_agent: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    cookies: Optional[List[Dict[str, Union[str, bool]]]] = None,
    prefer_browser: bool = True,
    wait_secs: int = 20,
    headless: bool = True,
) -> Tuple[Optional[str], List[str]]:
    """
    Trả về (best_m3u8, all_m3u8s)
    - prefer_browser=True: thử Firefox trước, fail thì mới yt-dlp
    """
    all_urls: List[str] = []
    best: Optional[str] = None

    if prefer_browser:
        got = await _firefox_m3u8(
            url=url,
            user_agent=user_agent,
            headers=headers,
            cookies=cookies,
            wait_secs=wait_secs,
            headless=headless,
        )
        all_urls.extend(got)

        if not all_urls:
            all_urls.extend(_yt_dlp_guess(url))
    else:
        all_urls.extend(_yt_dlp_guess(url))
        if not all_urls:
            all_urls.extend(
                await _firefox_m3u8(
                    url=url,
                    user_agent=user_agent,
                    headers=headers,
                    cookies=cookies,
                    wait_secs=wait_secs,
                    headless=headless,
                )
            )

    all_urls = _uniq([u for u in all_urls if "data:" not in u and "blob:" not in u])
    best = _best_candidate(all_urls)
    return best, all_urls
