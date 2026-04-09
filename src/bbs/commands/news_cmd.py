# modules/news.py — Notizie da feed RSS
import logging
from time import time

import feedparser

from dispatcher import command
from config import RSS_FEEDS, DEFAULT_FEED, NEWS_COUNT, NEWS_CACHE_TTL, NEWS_CACHE_MAX

log = logging.getLogger(__name__)

# Cache: feed_name -> (timestamp, [(title, summary), ...])
_cache: dict[str, tuple[float, list[tuple[str, str]]]] = {}

# Ultimo feed consultato per utente (per !news <numero>)
# Limitato a NEWS_CACHE_MAX entry — se supera, rimuove i piu' vecchi
_user_last_feed: dict[str, str] = {}


def _fetch_news(feed_name: str) -> list[tuple[str, str]]:
    """Scarica e parsa un feed RSS, restituisce lista di (titolo, sommario)."""
    now = time()
    if feed_name in _cache:
        cached_time, cached_entries = _cache[feed_name]
        if now - cached_time < NEWS_CACHE_TTL:
            return cached_entries

    url = RSS_FEEDS.get(feed_name)
    if not url:
        return []

    try:
        feed = feedparser.parse(url)
        entries = [
            (entry.title.strip(), entry.get("summary", "").strip())
            for entry in feed.entries[:NEWS_COUNT]
        ]
        # Evict cache scadute prima di inserire
        expired = [k for k, (ts, _) in _cache.items() if now - ts > NEWS_CACHE_TTL]
        for k in expired:
            del _cache[k]
        _cache[feed_name] = (now, entries)
        return entries
    except Exception as e:
        log.error("Errore fetch RSS %s: %s", feed_name, e)
        return []


@command("!news")
async def cmd_news(from_pubkey, args, db) -> str | list[str]:
    if not args:
        return await _send_headlines(from_pubkey, DEFAULT_FEED)

    arg = args[0].lower()

    if arg in ("help", "list"):
        lines = [f"  {name}" for name in RSS_FEEDS]
        return (
            "Feed disponibili:\n" + "\n".join(lines)
            + "\n!news [feed] | !news <n>"
        )

    # !news <numero> — dettaglio notizia
    if arg.isdigit():
        return _get_detail(from_pubkey, int(arg))

    # !news <feed_name> — titoli di un feed specifico
    if arg in RSS_FEEDS:
        return await _send_headlines(from_pubkey, arg)

    return f"Feed '{arg}' non trovato.\n!news list"


async def _send_headlines(from_pubkey: str, feed_name: str) -> list[str]:
    """Invia i titoli come messaggi separati."""
    entries = _fetch_news(feed_name)
    if not entries:
        return ["Notizie non disponibili"]

    _user_last_feed[from_pubkey] = feed_name
    # Evict utenti vecchi se troppi
    while len(_user_last_feed) > NEWS_CACHE_MAX:
        oldest_key = next(iter(_user_last_feed))
        del _user_last_feed[oldest_key]

    messages = []
    for i, (title, _summary) in enumerate(entries, 1):
        truncated = title[:160] + ("..." if len(title) > 160 else "")
        messages.append(f"[{i}/{len(entries)}] {truncated}")

    messages.append("!news <n> per dettaglio")
    return messages


def _get_detail(from_pubkey: str, index: int) -> str | list[str]:
    """Restituisce titolo + sommario della notizia N."""
    feed_name = _user_last_feed.get(from_pubkey, DEFAULT_FEED)
    entries = _fetch_news(feed_name)

    if not entries:
        return "Notizie non disponibili"

    if index < 1 or index > len(entries):
        return f"Notizia {index} non trovata (1-{len(entries)})"

    title, summary = entries[index - 1]

    if not summary:
        return title[:175]

    # Titolo + sommario, spezzati in messaggi se necessario
    messages = [title[:175]]
    # Spezza il summary in chunk da ~170 chars
    remaining = summary
    while remaining:
        chunk = remaining[:170]
        remaining = remaining[170:]
        messages.append(chunk)

    return messages
