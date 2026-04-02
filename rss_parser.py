import feedparser
import html2text
import os
import json
from datetime import datetime

# 配置项
RSS_FEEDS = [
    "https://rss.politico.com/politics-news.xml",
    "https://rss.politico.com/congress.xml"
]
OUTPUT_DIR = "dailynews" # 输出文件夹名称
PROCESSED_URLS_FILE = "processed_urls.json"  # 已处理文章URL记录

def load_processed_urls():
    """加载已处理的文章URL列表"""
    if os.path.exists(PROCESSED_URLS_FILE):
        try:
            with open(PROCESSED_URLS_FILE, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except Exception as e:
            print(f"警告: 无法加载已处理URL记录: {e}")
    return set()

def save_processed_urls(urls):
    """保存已处理的文章URL列表"""
    try:
        with open(PROCESSED_URLS_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(urls), f, ensure_ascii=False, indent=2)
        print(f"已保存 {len(urls)} 个已处理URL到 {PROCESSED_URLS_FILE}")
    except Exception as e:
        print(f"警告: 无法保存已处理URL记录: {e}")

def fetch_and_save_rss_news():
    """
    抓取RSS源，解析新闻条目，并按日期保存为Markdown文件。
    使用 processed_urls.json 去重，避免重复处理相同文章。
    """
    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 加载已处理的URL
    processed_urls = load_processed_urls()
    print(f"已加载 {len(processed_urls)} 个已处理URL")

    # 初始化HTML到Markdown转换器
    html_converter = html2text.HTML2Text()
    html_converter.body_width = 0  # 设置为0以避免自动换行，保持原始内容的换行

    # 用于存储按日期分组的新闻条目
    # 结构: {"YYYYMMDD": ["markdown_formatted_news_item_1", "markdown_formatted_news_item_2"]}
    news_by_date = {}
    new_urls = set()  # 本次新处理的文章URL

    print("开始处理RSS源...")
    for feed_url in RSS_FEEDS:
        print(f"正在抓取和解析: {feed_url}")
        
        # 解析RSS源
        feed = feedparser.parse(feed_url)

        # 检查解析是否成功（bozo位通常表示格式不佳的源）
        if feed.bozo:
            print(f"警告: RSS源 '{feed_url}' 可能存在格式问题. "
                  f"错误类型: {feed.bozo_exception.__class__.__name__}, "
                  f"原因: {feed.bozo_exception}")

        for entry in feed.entries:
            title = entry.get("title", "无标题")
            link = entry.get("link", "无链接")
            
            # 去重检查：跳过已处理的文章
            if link in processed_urls:
                print(f"跳过已处理文章: {title[:50]}...")
                continue
            
            # 获取并解析发布日期
            published_time_struct = entry.get("published_parsed")
            if not published_time_struct:
                print(f"警告: 条目 '{title}' ({link}) 缺少发布日期，将跳过。")
                continue
            
            try:
                # time.struct_time -> datetime object -> "YYYYMMDD" string
                dt_object = datetime(*published_time_struct[:6])
                date_str_for_filename = dt_object.strftime("%Y%m%d")
            except ValueError as e:
                print(f"警告: 无法解析条目 '{title}' ({link}) 的发布日期 '{published_time_struct}', "
                      f"错误: {e}，将跳过。")
                continue

            # 提取 <content:encoded> (首选) 或 summary (备选)
            content_html = ""
            if hasattr(entry, 'content') and entry.content:
                # entry.content 是一个列表，通常包含一个字典，其 'value' 键对应 <content:encoded>
                content_html = entry.content[0].get('value', '')
            
            if not content_html and hasattr(entry, 'summary'):
                content_html = entry.summary
            
            if not content_html:
                print(f"警告: 条目 '{title}' ({link}) 既无 <content:encoded> 内容也无 summary，内容将为空。")
            
            # 将HTML内容转换为Markdown
            content_md = html_converter.handle(content_html) if content_html else "无内容"

            # 格式化单个新闻条目的Markdown文本
            news_item_markdown = f"标题：{title}\n链接：{link}\n\n{content_md.strip()}\n\n---\n"

            # 按日期分组
            if date_str_for_filename not in news_by_date:
                news_by_date[date_str_for_filename] = []
            news_by_date[date_str_for_filename].append(news_item_markdown)
            
            # 记录新处理的URL
            new_urls.add(link)
            processed_urls.add(link)

    print("\n开始写入新闻到Markdown文件...")
    # 将分组后的新闻写入对应的Markdown文件
    for date_str, items_markdown_list in news_by_date.items():
        filepath = os.path.join(OUTPUT_DIR, f"{date_str}.md")
        print(f"正在写入 {len(items_markdown_list)} 条新闻到: {filepath}")
        try:
            # 使用 "a" 追加模式，保留之前的内容，避免覆盖
            # 这样即使RSS源有延迟，也不会丢失之前抓取的文章
            with open(filepath, "a", encoding="utf-8") as f:
                for item_md in items_markdown_list:
                    f.write(item_md)
            print(f"成功写入到 {filepath}")
        except IOError as e:
            print(f"错误: 无法写入文件 {filepath}. 原因: {e}")
    
    # 保存已处理的URL
    if new_urls:
        save_processed_urls(processed_urls)
        print(f"本次新处理 {len(new_urls)} 篇文章")

def main():
    """主函数，用于被其他模块调用"""
    fetch_and_save_rss_news()

if __name__ == "__main__":
    main()
    print("\n所有RSS源处理完毕。")