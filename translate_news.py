"""
POLITICO EU News Translator
Primary: Kimi K2.5 (summarize + translate + style)
Fallback: Baidu AI Translation (translate only, on Kimi failure)
"""
import os
import sys
import glob
import logging
import requests
import time

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

KIMI_API_KEY = os.getenv("kimi_API_KEY")
KIMI_MODEL   = os.getenv("KIMI_MODEL", "moonshotai/kimi-k2.5")
KIMI_API_URL = os.getenv("KIMI_API_URL",
                          "https://integrate.api.nvidia.com/v1/chat/completions")
BAIDU_API_KEY = os.getenv("BAIDU_API_KEY", "")

INPUT_DIR  = "dailynews"
OUTPUT_DIR = "translate"

PROMPT = """你是一位专业的英语媒体编辑。请完成以下两个任务：

## Task 1: 提取要点
仔细阅读原文，提取最重要的信息：
- 核心话题或论点是什么？
- 有哪些关键引语、数据或数字？
- 主要结论是什么？
- 对读者最重要的收获是什么？

## Task 2: 翻译与摘要
将提取的要点翻译为简体中文，并遵循以下要求：
1. 输出 300-600 字符的中文摘要
2. 使用 Markdown 格式，文章标题用二级标题（##）
3. 标题下方注明原文链接
4. 准确性：忠实于原文，保留关键引语和数据
5. 流畅性：自然现代的中文，避免翻译腔
6. 简洁性：拆分长句，用词精准
7. 至少包含一句原文中的精彩引语

## 输出格式
直接输出中文摘要，无需任何引导性语句。"""


def kimi_translate(content):
    """Primary: summarize + translate via Kimi LLM."""
    if not KIMI_API_KEY:
        logging.error("kimi_API_KEY not set")
        return None

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {KIMI_API_KEY}"
    }
    payload = {
        "model": KIMI_MODEL,
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user",   "content": content}
        ],
        "temperature": 0.7,
        "max_tokens": 2000
    }

    for attempt in range(5):
        try:
            logging.info(f"[KIMI] Submitting (attempt {attempt + 1}/5)...")
            resp = requests.post(
                KIMI_API_URL,
                headers=headers,
                json=payload,
                timeout=300
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get("choices") and result["choices"][0]:
                text = result["choices"][0]["message"]["content"]
                logging.info(f"[KIMI] OK: {len(text)} chars")
                return text
            else:
                logging.error(f"[KIMI] Unexpected: {result}")
            if attempt < 4:
                time.sleep(30 * (2 ** attempt))
        except Exception as e:
            logging.error(f"[KIMI] Failed: {e}")
            if attempt < 4:
                time.sleep(30 * (2 ** attempt))
    return None


def baidu_fallback(text):
    """Fallback: translate via Baidu AI Translation (Bearer Token auth)."""
    if not BAIDU_API_KEY:
        logging.error("[BAIDU] Missing BAIDU_API_KEY env var")
        return None

    # Strip markdown headings for cleaner translation
    lines = text.split("\n")
    title_line = ""
    body_lines = []
    for line in lines:
        if line.startswith("## "):
            title_line = line
        else:
            body_lines.append(line)
    body = "\n".join(body_lines)

    # Truncate to 2800 chars
    body = body[:2800]

    endpoint = "https://fanyi-api.baidu.com/ait/api/aiTextTranslate"
    for attempt in range(3):
        try:
            logging.info(f"[BAIDU] Translating (attempt {attempt + 1}/3)...")
            resp = requests.post(
                endpoint,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {BAIDU_API_KEY}"
                },
                json={"q": body, "from": "en", "to": "zh"},
                timeout=30
            )
            data = resp.json()
            if data.get("error_code"):
                logging.error(f"[BAIDU] API error: {data.get('error_code')} - {data.get('error_msg', '')}")
                if attempt < 2:
                    time.sleep(5)
                continue
            if "data" in data and data["data"]:
                result = data["data"].get("trans_result", "")
                if result:
                    logging.info(f"[BAIDU] OK: {len(result)} chars")
                    final = (title_line + "\n\n" + result) if title_line else result
                    return final
            logging.error(f"[BAIDU] Unexpected response: {data}")
            return None
        except Exception as e:
            logging.error(f"[BAIDU] Request failed: {e}")
            if attempt < 2:
                time.sleep(5)
    return None


def translate_article(filepath):
    """翻译单篇文章"""
    if not os.path.exists(filepath):
        logging.error(f"File not found: {filepath}")
        return None

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    outpath = os.path.join(OUTPUT_DIR, os.path.basename(filepath))

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    logging.info(f"Translating: {filepath} ({len(content)} chars)")

    # Step 1: Try Kimi
    result = kimi_translate(content)

    if result is None:
        # Step 2: Baidu fallback
        logging.warning("[FALLBACK] Kimi failed — using Baidu translation...")
        result = baidu_fallback(content)
        if result is None:
            logging.error("[FALLBACK] Baidu also failed — skipped")
            return None

    with open(outpath, "w", encoding="utf-8") as f:
        f.write(result)
    logging.info(f"Done: {outpath} ({len(result)} chars)")
    return result


def main():
    """处理所有今日未翻译的文章"""
    md_files = sorted(glob.glob(os.path.join(INPUT_DIR, "*.md")),
                      key=os.path.getmtime, reverse=True)
    if not md_files:
        logging.error("No .md files found in " + INPUT_DIR)
        return

    # 找最新日期的文件
    latest = md_files[0]
    logging.info(f"Processing: {latest}")

    ok = translate_article(latest)
    if ok:
        logging.info("Translation done")
    else:
        logging.error("Translation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
