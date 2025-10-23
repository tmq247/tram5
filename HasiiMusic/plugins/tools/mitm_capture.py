# HasiiMusic/plugins/tools/mitm_capture.py
# -*- coding: utf-8 -*-
import os
import time
import shlex
import subprocess
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from HasiiMusic import app
# Paths (sửa nếu cần)
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")  # dự đoán repo root relative
MITM_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "..", "utils", "mitm_script.py")
MITM_OUTPUT = "/tmp/m3u8_found.txt"
DEFAULT_MITM_PORT = 8080

# Helper: spawn mitmdump (returns subprocess)
def start_mitmdump(mitm_script=MITM_SCRIPT, port=DEFAULT_MITM_PORT):
    # clear old output
    try:
        if os.path.exists(MITM_OUTPUT):
            os.remove(MITM_OUTPUT)
    except:
        pass

    cmd = ["mitmdump", "-s", mitm_script, "--listen-port", str(port)]
    # Start mitmdump in background
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return p

def stop_process(p):
    try:
        p.terminate()
        p.wait(timeout=5)
    except Exception:
        try:
            p.kill()
        except Exception:
            pass

# Import mitmproxy CA into a firefox profile using certutil
def import_mitm_cert_into_profile(profile_dir):
    cert_path = os.path.expanduser("~/.mitmproxy/mitmproxy-ca-cert.pem")
    if not os.path.exists(cert_path):
        return False, f"mitm CA not found at {cert_path}"
    # try sql DB first, fallback to dbm
    for db_type in ("sql", "dbm"):
        try:
            cmd = [
                "certutil",
                "-A",
                "-n", "mitmproxy",
                "-t", "C,,",
                "-d", f"{db_type}:{profile_dir}",
                "-i", cert_path,
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True, "OK"
        except subprocess.CalledProcessError:
            continue
        except FileNotFoundError:
            return False, "certutil not installed (install libnss3-tools)"
    return False, "import failed (tried sql and dbm)"

# Main capture routine, synchronous blocking (we'll call it in thread)
def run_capture(url, profile_dir=None, wait_secs=18, headless=True, mitm_port=DEFAULT_MITM_PORT, timeout=60):
    # start mitmdump
    mitm_proc = start_mitmdump()
    # ensure mitmproxy CA exists (mitmdump will create it)
    time.sleep(0.8)

    # ensure firefox profile exists (create temp if not provided)
    tmp_profile = False
    if not profile_dir:
        # create ephemeral profile dir
        profile_dir = os.path.expanduser("~/mitm_firefox_profile_temp")
        if not os.path.exists(profile_dir):
            os.makedirs(profile_dir, exist_ok=True)
        tmp_profile = True

    # import mitm CA
    ok, msg = import_mitm_cert_into_profile(profile_dir)
    if not ok:
        # stop mitm and return error
        stop_process(mitm_proc)
        return {"error": f"Import CA failed: {msg}"}

    # prepare selenium call via small python subprocess to avoid heavy deps inside pyrogram thread
    helper_py = os.path.join(os.path.dirname(__file__), "mitm_helper_runner.py")
    # ensure helper exists (we will create it dynamically below if missing)
    if not os.path.exists(helper_py):
        # write helper file
        helper_code = r'''
import sys, time, os
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By

URL = sys.argv[1]
PROFILE = sys.argv[2]
MITM_OUTPUT = sys.argv[3]
PROXY = sys.argv[4]
WAIT = int(sys.argv[5])

opts = Options()
opts.headless = True
fp = webdriver.FirefoxProfile(PROFILE)
# proxy
ph, pp = PROXY.split(":")
fp.set_preference("network.proxy.type", 1)
fp.set_preference("network.proxy.http", ph)
fp.set_preference("network.proxy.http_port", int(pp))
fp.set_preference("network.proxy.ssl", ph)
fp.set_preference("network.proxy.ssl_port", int(pp))
fp.set_preference("network.proxy.no_proxies_on", "")
fp.update_preferences()

driver = webdriver.Firefox(firefox_profile=fp, options=opts)
try:
    driver.set_page_load_timeout(60)
    driver.get(URL)
    time.sleep(2)
    selectors = [
        'button[aria-label="Play"]',
        ".vjs-big-play-button",
        ".jw-icon-play",
        ".plyr__control--overlaid",
        "button.ytp-large-play-button",
        "video",
    ]
    for sel in selectors:
        try:
            els = driver.find_elements(By.CSS_SELECTOR, sel)
            if els:
                try:
                    els[0].click()
                except:
                    driver.execute_script("arguments[0].click();", els[0])
                time.sleep(0.3)
        except Exception:
            pass
    try:
        driver.execute_script("""
            (async () => {
              const vids = Array.from(document.querySelectorAll('video'));
              for (const v of vids) {
                try { v.muted = true; v.play && v.play(); } catch(e) {}
              }
            })();
        """)
    except:
        pass
    time.sleep(WAIT)
    # print nothing; main process will read MITM_OUTPUT
finally:
    try: driver.quit()
    except: pass
'''
        with open(helper_py, "w", encoding="utf-8") as fh:
            fh.write(helper_code)

    # run helper as subprocess
    proxy_arg = f"127.0.0.1:{mitm_port}"
    helper_cmd = [
        "python3",
        helper_py,
        url,
        profile_dir,
        MITM_OUTPUT,
        proxy_arg,
        str(wait_secs),
    ]
    try:
        subprocess.run(helper_cmd, check=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        stop_process(mitm_proc)
        return {"error": "Capture timed out"}
    except Exception as e:
        stop_process(mitm_proc)
        return {"error": f"Capture helper failed: {e}"}

    # read results
    links = []
    if os.path.exists(MITM_OUTPUT):
        with open(MITM_OUTPUT, "r") as f:
            for l in f:
                l = l.strip()
                if l and l not in links:
                    links.append(l)

    # stop mitmdump
    stop_process(mitm_proc)

    # cleanup temp profile if created
    if tmp_profile:
        try:
            # keep profile for debugging? remove to clean
            pass
        except:
            pass

    return {"links": links}

# Pyrogram command
@app.on_message(filters.command(["m3u8", "grabstream"], prefixes=["/", "!", "."]))
async def cmd_mitm(client: Client, message: Message):
    # usage: /mitm <url> [--wait=20]
    if len(message.command) < 2:
        await message.reply_text("Usage: /mitm <url> [--wait=SECONDS]\nNote: first time may take ~10s to create mitm CA.", quote=True)
        return

    raw = message.text.split(None, 1)[1].strip()
    parts = raw.split()
    url = parts[0]
    wait = 18
    for p in parts[1:]:
        if p.startswith("--wait="):
            try: wait = int(p.split("=",1)[1])
            except: pass

    msg = await message.reply_text("🔎 Starting capture (mitmproxy + headless Firefox). This may take ~20s...", quote=True)
    loop = asyncio.get_event_loop()
    # run blocking work in thread to avoid blocking event loop
    result = await loop.run_in_executor(None, run_capture, url, None, wait, True, DEFAULT_MITM_PORT, 120)
    if result.get("error"):
        await msg.edit_text(f"❌ Error: {result['error']}")
        return

    links = result.get("links", [])
    if not links:
        await msg.edit_text("❌ Không tìm thấy link nào. Thử tăng --wait=40 hoặc dùng profile có cookies/đăng nhập.")
        return

    text = "✅ Found links:\n" + "\n".join(f"- {l}" for l in links[:50])
    await msg.edit_text(text, disable_web_page_preview=True)
