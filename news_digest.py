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
    "🇺🇸 美国 AI 进展": {
        "queries": [
            'OpenAI GPT model research technical report benchmark API product launch agent',
            'Anthropic Claude model research benchmark release coding agent enterprise deployment',
            'Google DeepMind research paper benchmark Gemini model product launch',
            'Meta AI model research release Muse product AI glasses agent',
            'Microsoft Copilot AI agent enterprise rollout customer case study',
            'NVIDIA AI research model platform product release enterprise deployment',
            'AI agent deployment healthcare finance software coding measurable results case study',
            'generative AI production deployment customer service education science industry case study',
        ],
        # Use the US English edition and searches centered on US labs and products.
        "hl": "en-US", "gl": "US", "ceid": "US:en",
    },
    "🇨🇳 中国 AI 进展与应用": {
        "queries": [
            'DeepSeek 新模型 技术报告 评测 开源 发布 应用',
            '阿里 通义千问 Qwen 模型 技术报告 评测 开源 企业部署',
            '字节 豆包 Seed AI 模型 发布 产品 企业应用 案例',
            '百度 文心大模型 产品 发布 行业部署 案例',
            '腾讯 混元大模型 产品 发布 企业应用 案例',
            '华为 盘古大模型 行业部署 应用效果 案例',
            '中国 大模型 企业部署 行业应用 实际案例 效果',
            '中国 AI 智能体 产品 发布 企业落地 实际应用',
        ],
        "hl": "zh-CN", "gl": "CN", "ceid": "CN:zh-Hans",
    },
    "🌍 国际政局": {
        "queries": ["国际政治 外交 地缘政治", "国际选举 国际冲突 各国政府"],
        "hl": "zh-CN", "gl": "CN", "ceid": "CN:zh-Hans",
    },
}


def fetch_feed(query: str, hours: int, limit: int, locale: dict[str, str]) -> list[dict[str, str]]:
    days = max(1, (hours + 23) // 24)
    params = urllib.parse.urlencode({
        "q": f"{query} when:{days}d",
        **locale,
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
            "snippet": summary[:2000],
        })
        if len(items) >= limit:
            break
    return items


def collect(hours: int, tech_limit: int, politics_limit: int) -> dict[str, list[dict[str, str]]]:
    digest: dict[str, list[dict[str, str]]] = {}
    for topic, config in TOPICS.items():
        queries = config["queries"]
        locale = {key: config[key] for key in ("hl", "gl", "ceid")}
        limit = tech_limit if topic.startswith(("🇺🇸", "🇨🇳")) else politics_limit
        seen: set[str] = set()
        stories: list[dict[str, str]] = []
        for query in queries:
            try:
                batch = fetch_feed(query, hours, limit, locale)
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


def render(digest: dict[str, list[dict[str, str]]], hours: int) -> str:
    local_now = datetime.now(UTC).astimezone(timezone(timedelta(hours=8)))
    parts = [
        f"<h1 style='font-size:22px;margin:0 0 6px'>🗞️ 每日国际新闻简报</h1>",
        f"<p style='color:#666;margin:0 0 20px'>{local_now:%Y年%m月%d日} · 近{hours}小时</p>",
    ]
    for topic in TOPICS:
        items = digest.get(topic, [])
        parts.append(f"<h2 style='font-size:18px;margin:22px 0 10px'>{topic}</h2>")
        if not items:
            parts.append("<p>暂未检索到相关报道。</p>")
            continue
        for index, item in enumerate(items, 1):
            title = html.escape(item["title"])
            source = html.escape(item["source"])
            snippet = html.escape(item["snippet"])
            parts.append(
                "<div style='margin:0 0 16px;padding:0 0 14px;border-bottom:1px solid #e8e8e8'>"
                f"<p style='margin:0 0 6px;line-height:1.6'><b>{index}. {title}</b></p>"
                + (f"<p style='margin:4px 0;line-height:1.6;color:#333'>{snippet}</p>" if snippet else "")
                + f"<p style='margin:6px 0 0;color:#777;font-size:12px'>来源：{source}</p></div>"
            )
    parts.append("<p style='color:#888;font-size:12px'>美国 AI 新闻聚焦头部实验室、模型研究、产品发布与实际部署；中国 AI 新闻聚焦模型进展及行业应用。内容来自 Google News RSS 和媒体摘要，摘要详略取决于来源提供的内容。</p>")
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
    plain = re.sub(r"<br\s*/?>|</p>|</h1>|</h2>|</div>", "\n", message, flags=re.I)
    plain = html.unescape(re.sub(r"<[^>]+>", "", plain))
    email.set_content(plain)
    email.add_alternative(message, subtype="html")
    with smtplib.SMTP_SSL("smtp.qq.com", 465, context=ssl.create_default_context(), timeout=30) as smtp:
        smtp.login(address, auth_code)
        smtp.send_message(email)


def main() -> None:
    hours = int(os.getenv("NEWS_LOOKBACK_HOURS", "14"))
    tech_limit = int(os.getenv("MAX_TECH_ITEMS", "12"))
    politics_limit = int(os.getenv("MAX_POLITICS_ITEMS", "8"))
    message = render(collect(hours, tech_limit, politics_limit), hours)
    print(re.sub(r"<[^>]+>", "", message))
    send_email(message)


if __name__ == "__main__":
    main()

