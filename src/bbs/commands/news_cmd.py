"""
News command for MeshCore BBS.

Fetches and displays news from RSS feeds.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import asyncio
import html
import logging
import re
import urllib.request
from time import time
from typing import List

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry
from .helpers import parse_int

try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False

logger = logging.getLogger(__name__)

# Default RSS feeds
RSS_FEEDS = {
    "ansa": "https://www.ansa.it/sito/ansait_rss.xml",
    "ansa-tech": "https://www.ansa.it/sito/notizie/tecnologia/tecnologia_rss.xml",
    "ansa-scienza": "https://www.ansa.it/sito/notizie/scienza/scienza_rss.xml",
}
DEFAULT_FEED = "ansa"
NEWS_COUNT = 5
NEWS_CACHE_TTL = 300  # 5 minuti
HTTP_TIMEOUT = 5      # secondi per il download del feed
FETCH_TIMEOUT = 8     # secondi totali (download + parsing) lato event loop
MAX_FEED_BYTES = 2 * 1024 * 1024
MAX_SUMMARY_LEN = 400  # bound per !news <n> (radio budget)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean_summary(text: str) -> str:
    """Strip HTML tags/entities and bound the length."""
    text = html.unescape(_TAG_RE.sub("", text or ""))
    text = " ".join(text.split())
    if len(text) > MAX_SUMMARY_LEN:
        text = text[:MAX_SUMMARY_LEN - 3] + "..."
    return text

# Cache: feed_name -> (timestamp, [(title, summary), ...])
_cache = {}

# Ultimo feed consultato per utente (max 100 entries)
_user_last_feed = {}
_USER_FEED_MAX = 100


async def _fetch_news_async(feed_name: str) -> list:
    """Fetch news off the event loop, bounded by FETCH_TIMEOUT."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_fetch_news, feed_name), timeout=FETCH_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.warning(f"Timeout fetch RSS {feed_name}")
        return []


def _fetch_news(feed_name: str) -> list:
    """Fetch and parse an RSS feed with caching."""
    now = time()
    if feed_name in _cache:
        cached_time, cached_entries = _cache[feed_name]
        if now - cached_time < NEWS_CACHE_TTL:
            return cached_entries

    url = RSS_FEEDS.get(feed_name)
    if not url:
        return []

    try:
        # Download with an explicit timeout: feedparser.parse(url) has none
        req = urllib.request.Request(url, headers={"User-Agent": "MeshBBS/1.0"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            raw = resp.read(MAX_FEED_BYTES)
        feed = feedparser.parse(raw)
        entries = [
            (entry.get("title", "").strip(), _clean_summary(entry.get("summary", "")))
            for entry in feed.entries[:NEWS_COUNT]
        ]
        _cache[feed_name] = (now, entries)
        return entries
    except Exception as e:
        logger.error(f"Errore fetch RSS {feed_name}: {e}")
        return []


@CommandRegistry.register
class NewsCommand(BaseCommand):
    """Display news from RSS feeds."""

    name = "news"
    description = "Mostra notizie da feed RSS"
    usage = "!news [feed|numero]\n  !news list - feed disponibili\n  !news <n> - dettaglio notizia"
    aliases = ["notizie"]

    def __init__(self, session: Session):
        self.session = session

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        if not FEEDPARSER_AVAILABLE:
            return CommandResult.fail(
                "[BBS] Modulo feedparser non installato.\n"
                "Installa con: pip install feedparser"
            )

        if not args:
            return await self._headlines(ctx.sender_key, DEFAULT_FEED)

        arg = args[0].lower()

        # !news list — show available feeds
        if arg in ("help", "list"):
            lines = ["[BBS] Feed disponibili:"]
            for name in RSS_FEEDS:
                lines.append(f"  !news {name}")
            lines.append("!news <n> per dettaglio")
            return CommandResult.ok("\n".join(lines))

        # !news <numero> — detail of a specific news item
        index = parse_int(arg)
        if index is not None:
            return await self._detail(ctx.sender_key, index)

        # !news <feed_name> — headlines from a specific feed
        if arg in RSS_FEEDS:
            return await self._headlines(ctx.sender_key, arg)

        return CommandResult.fail(
            f"[BBS] Feed '{arg}' non trovato.\n!news list per i feed disponibili"
        )

    async def _headlines(self, sender_key: str, feed_name: str) -> CommandResult:
        """Fetch and format headlines."""
        entries = await _fetch_news_async(feed_name)
        if not entries:
            return CommandResult.fail("[BBS] Notizie non disponibili")

        _user_last_feed[sender_key] = feed_name
        # Evict oldest entries if over limit
        while len(_user_last_feed) > _USER_FEED_MAX:
            oldest = next(iter(_user_last_feed))
            del _user_last_feed[oldest]

        lines = [f"[BBS] News ({feed_name}):"]
        for i, (title, _) in enumerate(entries, 1):
            truncated = title[:120] + ("..." if len(title) > 120 else "")
            lines.append(f"{i}. {truncated}")
        lines.append("!news <n> per dettaglio")

        return CommandResult.ok("\n".join(lines))

    async def _detail(self, sender_key: str, index: int) -> CommandResult:
        """Get full detail for a specific news item (no title, full summary)."""
        feed_name = _user_last_feed.get(sender_key, DEFAULT_FEED)
        entries = await _fetch_news_async(feed_name)

        if not entries:
            return CommandResult.fail("[BBS] Notizie non disponibili")

        if index < 1 or index > len(entries):
            return CommandResult.fail(
                f"[BBS] Notizia {index} non trovata (1-{len(entries)})"
            )

        title, summary = entries[index - 1]

        if not summary:
            return CommandResult.ok(f"[BBS] {title}")

        # Send only the summary (user already read the title)
        # The core chunker will split into multiple messages if needed
        return CommandResult.ok(f"[{index}] {summary}")
