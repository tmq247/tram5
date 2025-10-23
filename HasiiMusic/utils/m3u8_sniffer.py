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
    wait_secs: int = 25,
    headless: bool = True,
    auto_create_cookies: bool = True,
    force_refresh_cookies: bool = False,
    engines: Optional[List[str]] = None,   # <-- thêm: thứ tự engine
) -> Tuple[Optional[str], List[str]]:
    if engines is None:
        # Thử firefox trước (hợp với hướng đi gốc), rồi fallback chromium
        engines = ["firefox", "chromium"]

    all_urls: List[str] = []
    best: Optional[str] = None

    # cookies tự tạo/nạp nếu cần
    if not cookies and auto_create_cookies:
        try:
            c = await ensure_cookies_for_domain(
                url=url,
                user_agent=user_agent,
                headers=headers,
                headless=headless,
                force_refresh=force_refresh_cookies,
            )
            if c:
                cookies = []
                for ck in c:
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
            cookies = cookies or []

    if prefer_browser:
        for eng in engines:
            got = await _browser_m3u8(
                engine=eng,
                url=url,
                user_agent=user_agent,
                headers=headers,
                cookies=cookies,
                wait_secs=wait_secs,
                headless=headless,
            )
            all_urls.extend(got)
            if all_urls:
                break  # đã có thì thôi
        if not all_urls:
            all_urls.extend(_yt_dlp_guess(url))
    else:
        all_urls.extend(_yt_dlp_guess(url))
        if not all_urls:
            for eng in engines:
                got = await _browser_m3u8(
                    engine=eng,
                    url=url,
                    user_agent=user_agent,
                    headers=headers,
                    cookies=cookies,
                    wait_secs=wait_secs,
                    headless=headless,
                )
                all_urls.extend(got)
                if all_urls:
                    break

    all_urls = _uniq([u for u in all_urls if "data:" not in u and "blob:" not in u])
    best = _best_candidate(all_urls)
    return best, all_urls
