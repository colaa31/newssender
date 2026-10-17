#!/usr/bin/env python3
"""Build a Chinese international news brief from Google News RSS and email it via QQ."""
from __future__ import annotations

import html
import os
import re
import smtplib
import ssl
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import parsedate_to_datetime

UTC = timezone.utc
TOPICS = {
    "🧠 科技圈": [
        "国际科技 人工智能 半导体 网络安全",
        "国际科技 太空 科学 互联网",
    ],
    "🌍 国际政局": [
        "国际政治 外交 地缘政治",
        "国际选举 国际冲突 各国政府",
    ],
}


def fetch_feed(query: str, hours: int, limit: int) -> list[dict[str, str]]:
    days = max(1, (hours + 23) // 24)
    params = urllib.parse.urlencode({
        "q": f"{query} when:{days}d",
        "hl": "zh-CN", "gl": "CN", "ceid": "CN:zh-Hans",
    })
    url = "https://news.google.com/rss/search?" + params
    req = urllib.request.Request(url, headers={"User-Agent": "DailyWorldNews/1.0"})
    with urllib.request.urlopen(req, timeout=25) as response:
        root = ET.fromstring(response.read())
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    items: list[dict[str, str]] = []
    for node in root.findall("./channel/item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        source = (node.findtext("source") or "Google 新闻").strip()
        pub = (node.findtext("pubDate") or "").strip()
        description = node.findtext("description") or ""
        summary = re.sub(r"<[^>]+>", " ", html.unescape(description))
        summary = re.sub(r"\s+", " ", summary).strip()
        try:
            published = parsedate_to_datetime(pub).astimezone(UTC)
        except (TypeError, ValueError, OverflowError):
            continue
        if published < cutoff or not title or not link:
            continue
        # Google News often appends the publisher to the title; show it separately.
        suffix = f" - {source}"
        if title.endswith(suffix):
            title = title[:-len(suffix)].strip()
        items.append({
            "title": title,
            "url": link,
            "source": source,
            "published": published.isoformat(timespec="minutes"),
            "snippet": summary[:600],
        })
        if len(items) >= limit:
            break
    return items


def collect(hours: int, limit: int) -> dict[str, list[dict[str, str]]]:
    digest: dict[str, list[dict[str, str]]] = {}
    for topic, queries in TOPICS.items():
        seen: set[str] = set()
        stories: list[dict[str, str]] = []
        for query in queries:
            try:
                batch = fetch_feed(query, hours, limit)
            except Exception as exc:
                print(f"RSS feed error [{topic}]: {exc}", file=sys.stderr)
                continue
            for item in batch:
                key = re.sub(r"\W+", "", item["title"].lower())
                if key not in seen:
                    seen.add(key)
                    stories.append(item)
        stories.sort(key=lambda item: item["published"], reverse=True)
        digest[topic] = stories[:limit]
    return digest


def render(digest: dict[str, list[dict[str, str]]]) -> str:
    local_now = datetime.now(UTC).astimezone(timezone(timedelta(hours=8)))
    parts = [
        f"<h1 style='font-size:22px;margin:0 0 6px'>🗞️ 每日国际新闻简报</h1>",
        f"<p style='color:#666;margin:0 0 20px'>{local_now:%Y年%m月%d日} · 近30小时</p>",
    ]
    for topic in TOPICS:
        items = digest.get(topic, [])
        parts.append(f"<h2 style='font-size:18px;margin:22px 0 10px'>{topic}</h2>")
        if not items:
            parts.append("<p>暂未检索到相关报道。</p>")
            continue
        for index, item in enumerate(items, 1):
            title = html.escape(item["title"])
            url = html.escape(item["url"], quote=True)
            source = html.escape(item["source"])
            snippet = html.escape(item["snippet"])
            parts.append(
                "<div style='margin:0 0 16px;padding:0 0 14px;border-bottom:1px solid #e8e8e8'>"
                f"<p style='margin:0 0 6px;line-height:1.6'><b>{index}. {topic.split(' ', 1)[1]}里，"
                f"<a href=\"{url}\" style='color:#155eef;text-decoration:none'>{title}</a></b></p>"
                + (f"<p style='margin:4px 0;line-height:1.6;color:#333'>{snippet}</p>" if snippet else "")
                + f"<p style='margin:6px 0 0;color:#777;font-size:12px'>来源：{source} · "
                f"<a href=\"{url}\">阅读原文</a></p></div>"
            )
    parts.append("<p style='color:#888;font-size:12px'>新闻由 Google News RSS 聚合，内容依据媒体标题与摘要整理；请点击原文核实细节。</p>")
    return "\n".join(parts)


def send_email(message: str) -> None:
    address = os.getenv("QQ_EMAIL")
    auth_code = os.getenv("QQ_EMAIL_AUTH_CODE")
    if not address or not auth_code:
        raise RuntimeError("QQ_EMAIL and QQ_EMAIL_AUTH_CODE are required")
    local_now = datetime.now(UTC).astimezone(timezone(timedelta(hours=8)))
    email = EmailMessage()
    email["Subject"] = f"国际新闻简报｜{local_now:%Y-%m-%d}"
    email["From"] = address
    email["To"] = address
    plain = re.sub(r"<a href=\"([^\"]+)\"[^>]*>(.*?)</a>", r"\2 (\1)", message)
    plain = re.sub(r"<br\s*/?>|</p>|</h1>|</h2>|</div>", "\n", plain, flags=re.I)
    plain = html.unescape(re.sub(r"<[^>]+>", "", plain))
    email.set_content(plain)
    email.add_alternative(message, subtype="html")
    with smtplib.SMTP_SSL("smtp.qq.com", 465, context=ssl.create_default_context(), timeout=30) as smtp:
        smtp.login(address, auth_code)
        smtp.send_message(email)


def main() -> None:
    hours = int(os.getenv("NEWS_LOOKBACK_HOURS", "30"))
    limit = int(os.getenv("MAX_ITEMS_PER_TOPIC", "8"))
    message = render(collect(hours, limit))
    print(re.sub(r"<[^>]+>", "", message))
    send_email(message)


if __name__ == "__main__":
    main()
