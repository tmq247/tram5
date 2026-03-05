import time

import psutil

from HasiiMusic.misc import _boot_
from HasiiMusic.utils.formatters import get_readable_time


async def bot_sys_stats():
    bot_uptime = int(time.time() - _boot_)
    try:
        UP = f"{get_readable_time(bot_uptime)}"
    except:
        UP = "N/A"
    try:
        CPU = f"{psutil.cpu_percent(interval=0.5)}%"
    except:
        CPU = "N/A"
    try:
        RAM = f"{psutil.virtual_memory().percent}%"
    except:
        RAM = "N/A"
    try:
        DISK = f"{psutil.disk_usage('/').percent}%"
    except:
        DISK = "N/A"
    return UP, CPU, RAM, DISK
