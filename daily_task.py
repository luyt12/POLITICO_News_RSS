"""
POLITICO 每日任务入口脚本
用于 GitHub Actions 环境
"""
import os
import sys
import glob
import re
from datetime import datetime
import pytz

tz_est = pytz.timezone("America/New_York")
today = datetime.now(tz_est).strftime("%Y%m%d")

# Step 1: 抓取新闻
print("Step 1: 抓取新闻...")
import rss_parser
rss_parser.main()

# Step 2: 仅翻译今日的文章
print("Step 2: 仅翻译今日文章...")
dailynews_file = os.path.join("dailynews", today + ".md")

import translate_news
if os.path.exists(dailynews_file):
    print("Found today: " + dailynews_file)
    ok = translate_news.translate_file(dailynews_file)
    if not ok:
        print("Translation failed, check logs")
else:
    print("No today file: " + dailynews_file)
    files = glob.glob("dailynews/*.md")
    print("Available: " + str(sorted(files)[-5:]))

# Step 3: 发送今日的翻译邮件
print("Step 3: 发送今日邮件...")
translate_file = os.path.join("translate", today + ".md")

if not os.path.exists(translate_file):
    t_files = glob.glob("translate/*.md")
    if t_files:
        translate_file = sorted(t_files)[-1]
        print("Using latest translate: " + translate_file)
    else:
        print("No translate files found, skip email")
        translate_file = None

if translate_file and os.path.exists(translate_file):
    print("Sending: " + translate_file)
    import send_email
    send_email.main(translate_file)
else:
    print("No file to send")

print("Done!")
