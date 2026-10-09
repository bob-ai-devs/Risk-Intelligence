"""News fetching, publisher classification and demo data."""
from __future__ import annotations

import hashlib
import random
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Iterable
from urllib.parse import quote_plus, urlparse

import pandas as pd
import requests

IST = timezone(timedelta(hours=5, minutes=30))
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BankRiskNewsApp/1.0)"}

# Publisher types
T_TRUSTED = "Trusted"
T_PRESS = "Press release"
T_BLOG = "Blog / social"
T_OTHER = "Other"
TYPE_ICON = {T_TRUSTED: "✅", T_PRESS: "📄", T_BLOG: "✍️", T_OTHER: "📰"}

TRUSTED_KEYWORDS = [
    "reuters", "bloomberg", "economic times", "economictimes", "et bfsi", "et now", "livemint", "mint",
    "business standard", "hindu businessline", "businessline", "the hindu", "moneycontrol",
    "financial express", "financialexpress", "cnbc", "cnbctv18", "ndtv profit", "ndtv", "times of india",
    "hindustan times", "indian express", "press trust of india", "pti", "ani", "bq prime", "bqprime",
    "business today", "india today", "zee business", "news18", "forbes india", "fortune india",
    "financial times", "wall street journal", "the print", "theprint", "scroll", "deccan herald",
    "telegraph india", "the tribune", "tribune india", "outlook business", "outlook india",
    "pib", "rbi", "bse", "nse", "business insider", "the new indian express",
]
PRESS_KEYWORDS = [
    "pr newswire", "prnewswire", "business wire", "businesswire", "globenewswire", "globe newswire",
    "accesswire", "einpresswire", "press release", "newsfile", "cision", "pr.com", "openpr",
]
BLOG_KEYWORDS = [
    "medium", "blogspot", "wordpress", "substack", "quora", "reddit", "youtube", "facebook", "linkedin",
    "twitter", "x.com", "tumblr", "telegram", "seeking alpha", "stocktwits", "tradingview", "scribd",
    "slideshare", "blog", "pinterest", "instagram", "whatsapp", "vocal media", "hubpages", "wattpad",
    "benzinga contributor", "motley fool", "yahoo finance community", "ghost.io", "newsbreak",
]


def _has_kw(text: str, kws: Iterable[str]) -> bool:
    t = text.lower()
    for k in kws:
        if re.search(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", t):
            return True
    return False


def classify_publisher(name: str, domain: str = "") -> str:
    blob = f"{name} {domain}".strip()
    if _has_kw(blob, BLOG_KEYWORDS):
        return T_BLOG
    if _has_kw(blob, PRESS_KEYWORDS):
        return T_PRESS
    if _has_kw(name, TRUSTED_KEYWORDS) or _has_kw(domain, [k.replace(" ", "") for k in TRUSTED_KEYWORDS]):
        return T_TRUSTED
    return T_OTHER


def _domain(url: str) -> str:
    try:
        host = (urlparse(url).netloc or "").lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def _strip_publisher_suffix(title: str, publisher: str) -> str:
    title = title.strip()
    for sep in (" - ", " | ", " – ", " — "):
        suffix = f"{sep}{publisher}"
        if publisher and title.lower().endswith(suffix.lower()):
            return title[: -len(suffix)].strip()
    return title


# ----------------------------------------------------------------- parsers
def parse_google_rss(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    out = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        src_el = item.find("source")
        publisher = (src_el.text or "").strip() if src_el is not None and src_el.text else ""
        src_url = src_el.get("url", "") if src_el is not None else ""
        if not publisher and " - " in title:
            title, publisher = title.rsplit(" - ", 1)
        title = _strip_publisher_suffix(title, publisher)
        try:
            dt = parsedate_to_datetime(pub).astimezone(IST)
        except Exception:
            dt = None
        out.append({"title": title, "publisher": publisher or "Unknown", "url": link,
                    "published": dt, "domain": _domain(src_url)})
    return out


def parse_newsapi(payload: dict) -> list[dict]:
    out = []
    for a in payload.get("articles", []):
        publisher = ((a.get("source") or {}).get("name") or "").strip() or "Unknown"
        title = _strip_publisher_suffix((a.get("title") or "").strip(), publisher)
        try:
            dt = datetime.fromisoformat((a.get("publishedAt") or "").replace("Z", "+00:00")).astimezone(IST)
        except Exception:
            dt = None
        url = a.get("url") or ""
        out.append({"title": title, "publisher": publisher, "url": url, "published": dt, "domain": _domain(url)})
    return out


def build_df(records: list[dict], days: int, max_items: int) -> pd.DataFrame:
    cutoff = datetime.now(IST) - timedelta(days=days)
    seen, rows = set(), []
    for r in records:
        key = _norm_title(r["title"])
        if not key or key in seen:
            continue
        if r["published"] is not None and r["published"] < cutoff:
            continue
        seen.add(key)
        rows.append(r)
        if len(rows) >= max_items:
            break
    cols = ["id", "title", "publisher", "publisher_type", "published", "url"]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    df["publisher_type"] = [classify_publisher(p, d) for p, d in zip(df.publisher, df.domain)]
    df["id"] = [hashlib.md5(f"{t}|{p}".encode()).hexdigest()[:10] for t, p in zip(df.title, df.publisher)]
    df["published"] = pd.to_datetime(df["published"], utc=True).dt.tz_convert(IST)
    df = df.sort_values("published", ascending=False, na_position="last").reset_index(drop=True)
    return df[cols]


# ----------------------------------------------------------------- fetchers
def fetch_google_news(company: str, days: int, max_items: int) -> pd.DataFrame:
    q = f'"{company}" when:{int(days)}d'
    url = f"https://news.google.com/rss/search?q={quote_plus(q)}&hl=en-IN&gl=IN&ceid=IN:en"
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    return build_df(parse_google_rss(r.text), days, max_items)


def fetch_newsapi(company: str, days: int, max_items: int, api_key: str) -> pd.DataFrame:
    if not api_key:
        raise ValueError("A NewsAPI key is required for this provider.")
    params = {
        "q": f'"{company}"',
        "from": (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d"),
        "sortBy": "relevancy", "language": "en", "pageSize": min(int(max_items) + 20, 100),
        "apiKey": api_key,
    }
    r = requests.get("https://newsapi.org/v2/everything", params=params, headers=HEADERS, timeout=25)
    data = r.json()
    if data.get("status") != "ok":
        raise RuntimeError(data.get("message", "NewsAPI returned an error."))
    return build_df(parse_newsapi(data), days, max_items)


def mentions_company(text: str, terms: Iterable[str]) -> bool:
    t = text.lower()
    return any(x.strip().lower() in t for x in terms if x and x.strip())


# --------------------------------------------------------------- demo data
_DEMO_TEMPLATES = [
    ("{c} reports strong quarterly profit as net interest margin improves", "Demo Business Daily"),
    ("{c} raises ₹5,000 crore through Tier 2 bonds to strengthen capital base", "Demo Markets Wire"),
    ("Rating agency upgrades {c} citing better asset quality and stable liquidity", "Demo Financial Times India"),
    ("{c} gross NPA falls to multi-year low as slippages ease", "Demo Business Daily"),
    ("{c} loan book grows 14% year on year led by retail and MSME demand", "Demo Mint Review"),
    ("{c} launches digital onboarding platform to cut operating costs", "Demo Tech Banker"),
    ("{c} board approves higher dividend after record annual earnings", "Demo Markets Wire"),
    ("Deposits at {c} rise as CASA ratio improves for third straight quarter", "Demo Business Daily"),
    ("RBI imposes monetary penalty on {c} for non-compliance with KYC norms", "Demo Financial Times India"),
    ("{c} flags fraud in large corporate account, sets aside additional provisions", "Demo Mint Review"),
    ("{c} shares slide after analysts flag rising slippages in the SME book", "Demo Markets Wire"),
    ("Cyber outage hits {c} mobile banking for several hours", "Demo Tech Banker"),
    ("Probe launched into alleged irregularities in loan sanctions at {c}", "Demo Business Daily"),
    ("Senior executive at {c} resigns amid governance concerns", "Demo Financial Times India"),
    ("{c} faces pressure on margins as deposit costs climb", "Demo Mint Review"),
    ("RBI restricts new customer onboarding at a mid-sized lender, banks on watch", "Demo Markets Wire"),
    ("RBI keeps repo rate unchanged; banks may see margin pressure ahead", "Demo Business Daily"),
    ("{c} board to meet next week to consider fund-raising proposal", "Demo Mint Review"),
    ("Banking stocks mixed as investors await inflation data", "Demo Markets Wire"),
    ("{c} announces date for quarterly results", "Demo Business Daily"),
    ("Analyst says {c} valuations look reasonable after recent rally", "Demo Tech Banker"),
    ("{c} to open 50 new branches in the next fiscal year", "Demo Financial Times India"),
    ("Why {c} stock could double by next year, claims blogger", "Demo Stock Blog (blogspot)"),
    ("My take: {c} is a screaming buy right now", "Demo Investor Blog (medium)"),
    ("{c} announces new credit card partnership (press release)", "Demo PR Newswire"),
    ("{c} signs MoU with fintech for supply-chain finance", "Demo PR Newswire"),
    ("Rumour mill: {c} to merge with a peer, say social posts", "Demo Social Chatter (reddit)"),
    ("Global bank failures raise questions on Indian lenders' bond portfolios", "Demo Financial Times India"),
    ("Rising crude prices could weigh on bank credit costs, economists warn", "Demo Business Daily"),
    ("{c} CEO says asset quality outlook remains stable", "Demo Mint Review"),
]


def demo_df(company: str, days: int = 7) -> pd.DataFrame:
    rng = random.Random(42)
    now = datetime.now(IST)
    rows = []
    for i in range(48):
        tpl, pub = _DEMO_TEMPLATES[i % len(_DEMO_TEMPLATES)]
        title = tpl.format(c=company or "the bank")
        if i >= len(_DEMO_TEMPLATES):
            title = f"{title} [update {i // len(_DEMO_TEMPLATES) + 1}]"
        dt = now - timedelta(hours=rng.uniform(1, days * 24 - 1))
        rows.append({"title": title, "publisher": pub, "url": "https://example.com/demo",
                     "published": dt, "domain": ""})
    df = build_df(rows, days + 1, 100)
    demo_trusted = {"Demo Business Daily", "Demo Financial Times India", "Demo Mint Review", "Demo Markets Wire"}
    df.loc[df.publisher.isin(demo_trusted), "publisher_type"] = T_TRUSTED
    return df
