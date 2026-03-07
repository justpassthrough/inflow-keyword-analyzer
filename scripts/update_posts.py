#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RSS + 모바일 스크래핑으로 내 블로그 글 목록을 수집하여 my_posts.json에 저장
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# Windows cp949 인코딩 문제 방지
if sys.stdout.encoding != "utf-8":
    sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)
    sys.stderr = open(sys.stderr.fileno(), mode="w", encoding="utf-8", buffering=1)

import feedparser
import requests
from bs4 import BeautifulSoup

BLOG_ID = os.environ.get("BLOG_ID", "biopharmblog")
RSS_URL = f"https://rss.blog.naver.com/{BLOG_ID}.xml"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
POSTS_FILE = DATA_DIR / "my_posts.json"

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
)

PARTICLES = {"은", "는", "이", "가", "을", "를", "의", "에", "에서", "으로", "과", "와", "도", "만", "하고", "하면", "하는"}


def load_posts():
    if POSTS_FILE.exists():
        with open(POSTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"blog_id": BLOG_ID, "last_updated": "", "posts": []}


def save_posts(data):
    data["last_updated"] = datetime.now().isoformat(timespec="seconds")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(POSTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(data['posts'])} posts to {POSTS_FILE}")


def parse_rss():
    print(f"Fetching RSS: {RSS_URL}")
    feed = feedparser.parse(RSS_URL)
    posts = []
    for entry in feed.entries:
        url = entry.get("link", "")
        title = entry.get("title", "")
        summary = BeautifulSoup(entry.get("summary", ""), "html.parser").get_text(strip=True)
        date = ""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            date = time.strftime("%Y-%m-%d", entry.published_parsed)
        posts.append({"title": title, "url": url, "date": date, "summary": summary})
    print(f"RSS: {len(posts)} posts found")
    return posts


def convert_to_mobile(url):
    """blog.naver.com URL -> m.blog.naver.com URL"""
    return re.sub(r"https?://blog\.naver\.com/", "https://m.blog.naver.com/", url)


def scrape_mobile(url):
    mobile_url = convert_to_mobile(url)
    try:
        resp = requests.get(mobile_url, headers={"User-Agent": MOBILE_UA}, timeout=10)
        if resp.status_code != 200:
            print(f"  Scrape failed ({resp.status_code}): {mobile_url}")
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        content = soup.select_one(".se-main-container") or soup.select_one("#postViewArea")
        if content:
            return content.get_text(separator=" ", strip=True)
        print(f"  No content found: {mobile_url}")
        return None
    except Exception as e:
        print(f"  Scrape error: {e}")
        return None


def extract_keywords(text):
    if not text:
        return []
    # 한글 단어 + 영문/숫자 단어 추출
    words = re.findall(r"[가-힣]{2,}|[a-zA-Z0-9]{2,}", text)
    # 조사 제거 + 중복 제거 + 순서 유지
    seen = set()
    result = []
    for w in words:
        wl = w.lower()
        if wl in PARTICLES or wl in seen:
            continue
        seen.add(wl)
        result.append(w)
    return result


def main():
    data = load_posts()
    existing_urls = {p["url"] for p in data["posts"]}
    rss_posts = parse_rss()

    new_count = 0
    for post in rss_posts:
        if post["url"] in existing_urls:
            continue

        print(f"  New: {post['title']}")

        # 모바일 스크래핑 시도
        body_text = scrape_mobile(post["url"])
        time.sleep(2)  # 네이버 차단 방지

        if body_text:
            body_keywords = extract_keywords(body_text)
        else:
            body_keywords = extract_keywords(post["summary"])

        data["posts"].append({
            "title": post["title"],
            "url": post["url"],
            "date": post["date"],
            "summary": post["summary"][:200],
            "body_keywords": body_keywords[:50],
            "target_keywords_manual": []
        })
        new_count += 1

    print(f"New posts added: {new_count}")
    save_posts(data)


if __name__ == "__main__":
    main()
