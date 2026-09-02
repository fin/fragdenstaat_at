import logging
from datetime import datetime
from datetime import timezone as dt_timezone

from django.utils import timezone
from django.utils.html import strip_tags

import requests

from froide.celery import app as celery_app

from .models import MAX_STORED_ENTRIES, RSSFeedCache, RSSFeedCMSPlugin

logger = logging.getLogger(__name__)

FETCH_TIMEOUT = 15
USER_AGENT = "FragDenStaat RSS fetcher (+https://fragdenstaat.at)"
SUMMARY_MAX_CHARS = 600


@celery_app.task(name="fragdenstaat_at.fds_cms_at.refresh_rss_feeds")
def refresh_rss_feeds():
    """Fan out one refresh task per distinct feed URL in use."""
    urls = set(RSSFeedCMSPlugin.objects.exclude(url="").values_list("url", flat=True))
    for url in urls:
        refresh_rss_feed.delay(url)
    return len(urls)


@celery_app.task(name="fragdenstaat_at.fds_cms_at.refresh_rss_feed")
def refresh_rss_feed(url):
    import feedparser

    cache, _ = RSSFeedCache.objects.get_or_create(url=url)

    headers = {"User-Agent": USER_AGENT}
    if cache.etag:
        headers["If-None-Match"] = cache.etag
    if cache.last_modified:
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
    }


def _store_error(cache, message):
    logger.warning("RSS feed %s: %s", cache.url, message)
    cache.error = message[:1000]
    cache.fetched_at = timezone.now()
    cache.save(update_fields=["error", "fetched_at"])
    return "error"
