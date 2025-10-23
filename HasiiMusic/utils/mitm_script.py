# HasiiMusic/utils/mitm_script.py
from mitmproxy import http
import os

OUTFILE = "/tmp/m3u8_found.txt"

def request(flow: http.HTTPFlow) -> None:
    try:
        u = flow.request.pretty_url
        if any(x in u.lower() for x in [".m3u8", ".mpd", ".ts", ".mp4"]):
            # ensure dir exists
            d = os.path.dirname(OUTFILE)
            if d and not os.path.exists(d):
                try: os.makedirs(d, exist_ok=True)
                except: pass
            with open(OUTFILE, "a") as f:
                f.write(u + "\n")
    except Exception:
        pass
