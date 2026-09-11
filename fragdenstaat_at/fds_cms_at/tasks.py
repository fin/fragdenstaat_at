import logging
import re
from datetime import datetime
from datetime import timezone as dt_timezone
from urllib.parse import urljoin

from django.utils import timezone
from django.utils.html import strip_tags

import requests

from froide.celery import app as celery_app

from .models import MAX_STORED_ENTRIES, RSSFeedCache, RSSFeedCMSPlugin

logger = logging.getLogger(__name__)

FETCH_TIMEOUT = 15
USER_AGENT = "FragDenStaat RSS fetcher (+https://fragdenstaat.at)"
SUMMARY_MAX_CHARS = 600

IMG_SRC_RE = re.compile(r"""<img\b[^>]*?\bsrc\s*=\s*["']([^"']+)["']""", re.IGNORECASE)


@celery_app.task(name="fragdenstaat_at.fds_cms_at.refresh_rss_feeds")
def refresh_rss_feeds():
    """Fan out one refresh task per distinct feed URL in use."""
    urls = set(RSSFeedCMSPlugin.objects.exclude(url="").values_list("url", flat=True))
    for url in urls:
        refresh_rss_feed.delay(url)
    return len(urls)


@celery_app.task(name="fragdenstaat_at.fds_cms_at.refresh_rss_feed")
def refresh_rss_feed(url, force=False):
    """Fetch `url` into its RSSFeedCache row. With `force`, the conditional
    request headers are left out so the server can't answer 304 and the
    cached data is rebuilt even if the feed itself is unchanged.
    """
    import feedparser

    cache, _ = RSSFeedCache.objects.get_or_create(url=url)

    headers = {"User-Agent": USER_AGENT}
    if cache.etag and not force:
        headers["If-None-Match"] = cache.etag
    if cache.last_modified and not force:
        headers["If-Modified-Since"] = cache.last_modified

    try:
        response = requests.get(url, headers=headers, timeout=FETCH_TIMEOUT)
    except requests.RequestException as exc:
        return _store_error(cache, str(exc))

    if response.status_code == 304:
        cache.error = ""
        cache.fetched_at = timezone.now()
        cache.save(update_fields=["error", "fetched_at"])
        return "not-modified"

    if response.status_code != 200:
        return _store_error(cache, f"HTTP {response.status_code}")

    parsed = feedparser.parse(response.content)
    entries = [_entry(e) for e in parsed.entries[:MAX_STORED_ENTRIES]]
    if not entries and parsed.bozo:
        return _store_error(cache, str(parsed.bozo_exception))

    cache.data = {
        "feed_title": parsed.feed.get("title", ""),
        "entries": entries,
    }
    cache.etag = (response.headers.get("ETag") or "")[:512]
    cache.last_modified = (response.headers.get("Last-Modified") or "")[:128]
    cache.error = ""
    cache.fetched_at = timezone.now()
    cache.save()
    return len(entries)


def _entry(entry):
    published = None
    parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed_time:
        published = datetime(*parsed_time[:6], tzinfo=dt_timezone.utc).isoformat()
    summary = strip_tags(entry.get("summary", "") or "").strip()
    return {
        "title": (entry.get("title", "") or "").strip(),
        "link": entry.get("link", "") or "",
        "summary": summary[:SUMMARY_MAX_CHARS],
        "published": published,
        "image": _entry_image(entry),
    }


def _entry_image(entry):
    """Best-effort image URL for an entry, or "".

    Checks the usual explicit carriers first (Media RSS thumbnail/content,
    image enclosures), then falls back to the first <img> in the entry's
    HTML body. Relative URLs are resolved against the entry link.
    """
    candidates = []
    for thumb in entry.get("media_thumbnail") or []:
        candidates.append(thumb.get("url"))
    for media in entry.get("media_content") or []:
        mime = media.get("type") or ""
        if media.get("medium") == "image" or mime.startswith("image/"):
            candidates.append(media.get("url"))
    for enclosure in entry.get("enclosures") or []:
        if (enclosure.get("type") or "").startswith("image/"):
            candidates.append(enclosure.get("href"))
    for content in entry.get("content") or []:
        html = content.get("value") or ""
        match = IMG_SRC_RE.search(html)
        if match:
            candidates.append(match.group(1))
    match = IMG_SRC_RE.search(entry.get("summary", "") or "")
    if match:
        candidates.append(match.group(1))

    link = entry.get("link", "") or ""
    for url in candidates:
        if not url:
            continue
        url = urljoin(link, url.strip())
        if url.startswith(("http://", "https://")):
            return url
    return ""


def _store_error(cache, message):
    logger.warning("RSS feed %s: %s", cache.url, message)
    cache.error = message[:1000]
    cache.fetched_at = timezone.now()
    cache.save(update_fields=["error", "fetched_at"])
    return "error"
