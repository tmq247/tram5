HELP_1 = """<b><u>ᴀᴅᴍɪɴ ᴄᴏᴍᴍᴀɴᴅs :</b></u>

ᴄʜỉ ᴄầɴ ᴛʜêᴍ <b>ᴄ</b> ᴠàᴏ đầᴜ ʟệɴʜ ᴅể sᴜ̉ ᴅụɴɢ ᴄʜᴜɴɢ ᴄʜᴏ ᴋêɴʜ.

/pause : Tạm dừng luồng đang phát.

/resume : Tiếp tục luồng đang tạm dừng.

/skip : Bỏ qua bài đang phát và phát bài tiếp theo trong hàng chờ.

/end ᴏʀ /stop : Xoá hàng chờ và kết thúc luồng đang phát.

/player : Mở bảng điều khiển phát nhạc tương tác.

/queue : Hiển thị danh sách bài hát trong hàng chờ.
"""

HELP_2 = """
<b><u>ᴀᴜᴛʜ ᴜsᴇʀs :</b></u>

Người dùng được uỷ quyền có thể dùng quyền quản trị trong bot mà không cần quyền admin trong cuộc trò chuyện.

/auth [tên_nguời_dùng/ID] : Thêm người dùng vào danh sách uỷ quyền của bot.
/unauth [tên_người_dùng/ID] : Gỡ người dùng khỏi danh sách uỷ quyền.
/authusers : Hiển thị danh sách người dùng được uỷ quyền của nhóm.
"""

HELP_3 = """
<u><b>ʙʀᴏᴀᴅᴄᴀsᴛ ғᴇᴀᴛᴜʀᴇ</b></u> [chỉ cho sᴜᴅᴏᴇʀs] :

/broadcast [nội dung hoặc trả lời một tin nhắn] : Phát (gửi) tin nhắn tới các đoạn chat mà bot phục vụ.

<u>Chế độ phát:</u>
<b>-pin</b> : Ghim tin nhắn đã phát ở các đoạn chat được phục vụ.
<b>-pinloud</b> : Ghim và gửi thông báo đến các thành viên.
<b>-user</b> : Phát tin nhắn tới người dùng đã bắt đầu bot của bạn.
<b>-assistant</b> : Phát tin nhắn từ tài khoản trợ lý của bot.
<b>-nobot</b> : Buộc bot KHÔNG phát tin nhắn.

<b>Ví dụ:</b> <code>/broadcast -user -assistant -pin kiểm tra phát</code>
"""

HELP_4 = """<u><b>ᴄʜᴀᴛ ʙʟᴀᴄᴋʟɪsᴛ ғᴇᴀᴛᴜʀᴇ :</b></u> [chỉ cho sᴜᴅᴏᴇʀs]

Hạn chế các đoạn chat rác sử dụng bot của chúng ta.

/blacklistchat [chat_id] : Chặn một đoạn chat khỏi việc dùng bot.
/whitelistchat [chat_id] : Bỏ chặn đoạn chat đã nằm trong danh sách đen.
/blacklistedchat : Hiển thị danh sách các đoạn chat bị chặn.
"""

HELP_5 = """
<u><b>ʙʟᴏᴄᴋ ᴜsᴇʀs:</b></u> [chỉ cho sᴜᴅᴏᴇʀs]

Bắt đầu bỏ qua người dùng bị chặn, khiến họ không thể dùng lệnh bot.

/block [tên người dùng hoặc trả lời một người dùng] : Chặn người dùng khỏi bot.
/unblock [tên người dùng hoặc trả lời một người dùng] : Bỏ chặn người dùng.
/blockedusers : Hiển thị danh sách người dùng bị chặn.
"""

HELP_6 = """
<u><b>ᴄʜᴀɴɴᴇʟ ᴩʟᴀʏ ᴄᴏᴍᴍᴀɴᴅs:</b></u>

Bạn có thể phát âm thanh/video trong kênh.

/cplay : Bắt đầu phát bản nhạc được yêu cầu trên videochat của kênh.
/cvplay : Bắt đầu phát video được yêu cầu trên videochat của kênh.
/cplayforce or /cvplayforce : Dừng luồng đang phát và bắt đầu phát bản được yêu cầu.

/channelplay [tên người dùng hoặc ID kênh] hoặc [disable] : Kết nối kênh với nhóm và bắt đầu phát nhạc bằng các lệnh gửi trong nhóm.
"""

HELP_7 = """
<u><b>ɢʟᴏʙᴀʟ ʙᴀɴ ғᴇᴀᴛᴜʀᴇ</b></u> [chỉ cho sᴜᴅᴏᴇʀs] :

/gban [tên người dùng hoặc trả lời người dùng] : Cấm người đó ở tất cả đoạn chat được bot phục vụ và đưa vào danh sách đen.
/ungban [tên người dùng hoặc trả lời người dùng] : Bỏ cấm người dùng đã bị cấm toàn cục.
/gbannedusers : Hiển thị danh sách người dùng bị cấm toàn cục.
"""

HELP_8 = """
<b><u>ʟᴏᴏᴘ sᴛʀᴇᴀᴍ :</b></u>

<b>Bắt đầu phát lặp lại luồng hiện tại</b>

/loop [enable/disable] : Bật/tắt phát lặp cho luồng đang phát.
/loop [1, 2, 3, ...] : Bật phát lặp theo số lần được chỉ định.
"""

HELP_9 = """
<u><b>ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ</b></u> [chỉ cho sᴜᴅᴏᴇʀs] :

/logs : Lấy nhật ký của bot.

/logger [enable/disable] : Bot sẽ bắt đầu ghi lại các hoạt động diễn ra trên bot.

/maintenance [enable/disable] : Bật hoặc tắt chế độ bảo trì của bot.
"""

HELP_10 = """
<b><u>ᴘɪɴɢ & sᴛᴀᴛs :</b></u>

/start : Khởi động bot nhạc.
/help : Mở menu trợ giúp với giải thích các lệnh.

/ping : Hiển thị ping và thống kê hệ thống của bot.

/stats : Hiển thị thống kê tổng thể của bot.
"""

HELP_11 = """
<u><b>ᴩʟᴀʏ ᴄᴏᴍᴍᴀɴᴅs :</b></u>

<b>v :</b> là phát video.
<b>force :</b> là phát cưỡng bức.

/play hoặc /vplay : Bắt đầu phát bản được yêu cầu trên videochat.

/playforce hoặc /vplayforce : Dừng luồng đang phát và bắt đầu phát bản được yêu cầu.
"""

HELP_12 = """
<b><u>sʜᴜғғʟᴇ ᴏ̨ᴜᴇᴜᴇ :</b></u>

/shuffle : Trộn ngẫu nhiên hàng chờ.
/queue : Hiển thị danh sách hàng chờ.
"""

HELP_13 = """
<b><u>sᴇᴇᴋ sᴛʀᴇᴀᴍ :</b></u>

/seek [thời lượng tính bằng giây] : Tua tới vị trí chỉ định trong luồng.
/seekback [thời lượng tính bằng giây] : Tua ngược về vị trí được chỉ định.
"""

HELP_14 = """
<b><u>sᴏɴɢ ᴅᴏᴡɴʟᴏᴀᴅ</b></u>

/song [tên bài hát/đường dẫn YouTube] : Tải bất kỳ bản nhạc nào từ YouTube ở định dạng mp3 hoặc mp4.
"""

HELP_15 = """
<b><u>sᴘᴇᴇᴅ ᴄᴏᴍᴍᴀɴᴅs :</b></u>

Bạn có thể điều khiển tốc độ phát lại của luồng hiện tại. [chỉ quản trị viên]

/speed hoặc /playback : Điều chỉnh tốc độ phát âm thanh trong nhóm.
/cspeed hoặc /cplayback : Điều chỉnh tốc độ phát âm thanh trong kênh.
"""
