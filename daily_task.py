"""
POLITICO EU Daily Task
1. Fetch today's articles from RSS (deduped via processed_urls.json)
   - mode=normal: only today + unprocessed
   - mode=backfill: recent days + un-sent articles
2. Translate via Kimi (with Baidu fallback)
3. Send email
4. Mark URLs as sent
"""
import os
import sys
import glob

mode = os.getenv("MODE", "normal")
print(f"Mode: {mode}")

# Step 1: 抓取 RSS
print("Step 1: 抓取 RSS...")
import rss_parser
saved = rss_parser.fetch_rss(force_backfill=(mode == "backfill"))
if not saved:
    print("无新文章，结束")
    sys.exit(0)
print(f"抓取完成: {len(saved)} 篇")

# Step 2: 翻译今日文件（按修改时间选最新）
print("Step 2: 翻译文章...")
md_files = glob.glob(os.path.join("dailynews", "*.md"))
if not md_files:
    print("无 MD 文件，跳过翻译")
    sys.exit(1)

# 选最新的文件（按修改时间）
today_file = sorted(md_files, key=os.path.getmtime)[-1]
print(f"翻译文件: {today_file}")

import translate_news
result = translate_news.translate_article(today_file)
if not result:
    print("翻译失败，退出")
    sys.exit(1)
print(f"翻译完成: {len(result)} 字符")

# Step 3: 发送邮件
print("Step 3: 发送邮件...")
translate_file = os.path.join("translate", os.path.basename(today_file))
import send_email
send_email.send_email(translate_file)

# Step 4: 标记已发送
print("Step 4: 标记已发送...")
rss_parser.mark_sent(saved)
print("完成!")
