"""Collect headlines and summaries from financial news RSS feeds (WSJ, MarketWatch, ...).

Only public, publisher-provided feeds are read. Full article text is NOT
fetched: WSJ articles are paywalled and its terms prohibit automated
scraping. For full text use a licensed source (Dow Jones Factiva / API).

Usage:
    python scraper.py                      # all feeds -> data/articles.jsonl
    python scraper.py --feeds wsj_markets  # selected feeds
    python scraper.py --csv data/out.csv
"""
import argparse
import csv
import json
import time
from dataclasses import asdict, dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

FEEDS = {
    "wsj_markets": "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",
    "wsj_world": "https://feeds.content.dowjones.io/public/rss/RSSWorldNews",
    "wsj_business": "https://feeds.content.dowjones.io/public/rss/WSJcomUSBusiness",
    "wsj_technology": "https://feeds.content.dowjones.io/public/rss/RSSWSJD",
    "marketwatch_top": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
}

USER_AGENT = "financial-feed-collector/0.1 (research; contact: ptrodriguez@uchicago.edu)"
REQUEST_DELAY = 2.0  # seconds between requests


@dataclass
class Article:
    source: str
    title: str
    link: str
    published: str  # ISO 8601, or "" if unparseable
    summary: str
    guid: str


def allowed_by_robots(url: str, cache: dict) -> bool:
    parts = urlparse(url)
    root = f"{parts.scheme}://{parts.netloc}"
    if root not in cache:
        rp = robotparser.RobotFileParser(f"{root}/robots.txt")
        try:
            resp = requests.get(f"{root}/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=15)
            rp.parse(resp.text.splitlines() if resp.ok else [])
        except requests.RequestException:
            rp.parse([])
        cache[root] = rp
    return cache[root].can_fetch(USER_AGENT, url)


def parse_feed(xml: str, source: str) -> list[Article]:
    soup = BeautifulSoup(xml, "xml")
    articles = []
    for item in soup.find_all("item"):
        text = lambda tag: (item.find(tag).get_text(strip=True) if item.find(tag) else "")
        pub = text("pubDate")
        try:
            pub = parsedate_to_datetime(pub).isoformat()
        except (TypeError, ValueError):
            pub = ""
        link = text("link")
        articles.append(Article(
            source=source,
            title=text("title"),
            link=link,
            published=pub,
            summary=BeautifulSoup(text("description"), "html.parser").get_text(" ", strip=True),
            guid=text("guid") or link,
        ))
    return articles


def fetch_feed(name: str, url: str, robots_cache: dict) -> list[Article]:
    if not allowed_by_robots(url, robots_cache):
        print(f"[skip] {name}: disallowed by robots.txt")
        return []
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return parse_feed(resp.text, name)


def load_seen(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open() as f:
        return {json.loads(line)["guid"] for line in f if line.strip()}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--feeds", nargs="*", choices=FEEDS, default=list(FEEDS))
    ap.add_argument("--out", default="data/articles.jsonl")
    ap.add_argument("--csv", help="also write all collected articles to this CSV")
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    seen = load_seen(out)
    robots_cache: dict = {}
    collected: list[Article] = []

    for i, name in enumerate(args.feeds):
        if i:
            time.sleep(REQUEST_DELAY)
        try:
            collected += fetch_feed(name, FEEDS[name], robots_cache)
        except requests.RequestException as e:
            print(f"[error] {name}: {e}")

    new = [a for a in collected if a.guid not in seen]
    with out.open("a") as f:
        for a in new:
            f.write(json.dumps(asdict(a)) + "\n")
    print(f"{len(collected)} fetched, {len(new)} new -> {out}")

    if args.csv and collected:
        with open(args.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(asdict(collected[0])))
            w.writeheader()
            w.writerows(asdict(a) for a in collected)


if __name__ == "__main__":
    main()
