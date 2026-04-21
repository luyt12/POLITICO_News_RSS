"""
POLITICO EU RSS Parser
抓取 https://www.politico.eu/feed/ 并按日期保存为 Markdown。
去重：通过 processed_urls.json 记录已发送的 URL。
"""
import feedparser
import html2text
import os
import json
from datetime import datetime, timezone
import pytz

# 配置项
RSS_URL = "https://www.politico.eu/feed/"
OUTPUT_DIR = "dailynews"      # 原始文章输出目录
PROCESSED_FILE = "processed_urls.json"  # {"url": {"title": "...", "sent": bool, "date": "YYYY-MM-DD"}}
MAX_DAILY = 10               # 每天最多处理10篇

# 欧洲时区（用于判断"今天"）
TZ_EU = pytz.timezone("Europe/Brussels")


def load_processed():
    """加载已处理记录"""
    if os.path.exists(PROCESSED_FILE):
        try:
            with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"警告: 无法加载 {PROCESSED_FILE}: {e}")
    return {}


def save_processed(data):
    """保存已处理记录"""
    with open(PROCESSED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"已保存 {len(data)} 条记录到 {PROCESSED_FILE}")


def is_today_eu(dt, today_str):
    """判断文章日期是否为今日（欧洲时间）"""
    try:
        eu_tz = pytz.timezone("Europe/Brussels")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        eu_dt = dt.astimezone(eu_tz)
        return eu_dt.strftime("%Y-%m-%d") == today_str
    except Exception:
        return False


def fetch_rss():
    """
    抓取 politico.eu RSS，按日期保存 Markdown。
    仅保留今天（欧洲时间）的文章，且不超过 MAX_DAILY 篇。
    去重：不重复抓取 processed_urls.json 中已存在的 URL。
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    processed = load_processed()

    print(f"正在抓取: {RSS_URL}")
    feed = feedparser.parse(RSS_URL)

    if feed.bozo:
        print(f"警告: RSS 格式可能有问题. 错误: {feed.bozo_exception}")

    if not feed.entries:
        print("警告: RSS 条目为空")
        return []

    # 计算欧洲"今天"
    now_eu = datetime.now(TZ_EU)
    today_str = now_eu.strftime("%Y-%m-%d")
    today_file = os.path.join(OUTPUT_DIR, today_str + ".md")

    # 收集今日未处理的文章
    candidates = []
    for entry in feed.entries:
        link = entry.get("link", "")
        title = entry.get("title", "无标题")

        if not link:
            continue

        # 去重：已处理过（含已发送）的跳过
        if link in processed:
            print(f"跳过已记录: {title[:50]}")
            continue

        # 获取发布日期
        pub_dt = None
        try:
            pub_struct = entry.get("published_parsed")
            if pub_struct:
                pub_dt = datetime(*pub_struct[:6], tzinfo=timezone.utc)
        except Exception:
            pass

        # 筛选今日（欧洲时间）的文章
        if pub_dt and not is_today_eu(pub_dt, today_str):
            continue

        candidates.append(entry)

    print(f"今日（欧洲时间 {today_str}）新文章: {len(candidates)} 篇")

    if not candidates:
        print("今日无新文章，跳过写入")
        return []

    # 限制数量
    selected = candidates[:MAX_DAILY]
    print(f"选取前 {len(selected)} 篇")

    html_converter = html2text.HTML2Text()
    html_converter.body_width = 0

    saved = []
    for entry in selected:
        title = entry.get("title", "无标题")
        link = entry.get("link", "")

        # 提取正文
        content_html = ""
        if hasattr(entry, "content") and entry.content:
            content_html = entry.content[0].get("value", "")
        if not content_html and hasattr(entry, "summary"):
            content_html = entry.summary

        content_md = html_converter.handle(content_html).strip() if content_html else "（无正文）"

        # 写入 Markdown
        item = f"## {title}\n\n链接：{link}\n\n{content_md}\n\n---\n\n"

        mode = "a" if os.path.exists(today_file) else "w"
        with open(today_file, mode, encoding="utf-8") as f:
            f.write(item)

        # 记录到 processed_urls.json
        pub_str = ""
        if pub_dt:
            try:
                pub_str = pub_dt.astimezone(TZ_EU).strftime("%Y-%m-%d")
            except Exception:
                pub_str = today_str

        processed[link] = {"title": title, "sent": False, "date": pub_str or today_str}
        saved.append(link)
        print(f"  已保存: {title[:60]}")

    # 更新 processed_urls.json
    save_processed(processed)
    print(f"本次新增 {len(saved)} 篇，文件: {today_file}")
    return saved


def mark_sent(urls):
    """标记指定 URL 为已发送"""
    processed = load_processed()
    for url in urls:
        if url in processed:
            processed[url]["sent"] = True
    save_processed(processed)


def main():
    saved = fetch_rss()
    print(f"\n完成: 抓取 {len(saved)} 篇新文章")


if __name__ == "__main__":
    main()
