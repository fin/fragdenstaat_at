"""fds_cms_at RSS feed plugin: the Celery fetch task and the plugin render.

The task fetches each distinct feed URL and caches up to MAX_STORED_ENTRIES
entries in RSSFeedCache; the plugin only reads that cache and slices `count`
off the front.
"""

from django.template.loader import render_to_string

import pytest

from fragdenstaat_at.fds_cms_at import tasks
from fragdenstaat_at.fds_cms_at.cms_plugins import RSSFeedPlugin
from fragdenstaat_at.fds_cms_at.models import RSSFeedCache, RSSFeedCMSPlugin

pytestmark = pytest.mark.django_db

FEED_URL = "https://example.org/feed.xml"

RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Example Blog</title>
  <item>
    <title>Newest post</title>
    <link>https://example.org/2</link>
    <description>&lt;p&gt;Second &lt;b&gt;body&lt;/b&gt;.&lt;/p&gt;</description>
    <pubDate>Tue, 02 Sep 2026 10:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Older post</title>
    <link>https://example.org/1</link>
    <description>First body.</description>
    <pubDate>Mon, 01 Sep 2026 10:00:00 GMT</pubDate>
  </item>
</channel></rss>
"""


class FakeResponse:
    def __init__(self, status_code=200, content=b"", headers=None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}


def _fake_get(response):
    def get(url, headers=None, timeout=None):
        return response

    return get


def test_task_populates_the_cache(monkeypatch):
    monkeypatch.setattr(
        tasks.requests,
        "get",
        _fake_get(FakeResponse(content=RSS, headers={"ETag": '"abc"'})),
    )

    stored = tasks.refresh_rss_feed(FEED_URL)

    assert stored == 2
    cache = RSSFeedCache.objects.get(url=FEED_URL)
    assert cache.feed_title == "Example Blog"
    assert cache.error == ""
    assert cache.etag == '"abc"'
    assert cache.fetched_at is not None
    assert [e["title"] for e in cache.entries] == ["Newest post", "Older post"]
    # HTML in the description is stripped to plain text.
    assert cache.entries[0]["summary"] == "Second body."
    assert cache.entries[0]["link"] == "https://example.org/2"
    assert cache.entries[0]["published"].startswith("2026-09-02T10:00:00")


def test_task_records_a_network_error(monkeypatch):
    def boom(url, headers=None, timeout=None):
        raise tasks.requests.RequestException("connection refused")

    monkeypatch.setattr(tasks.requests, "get", boom)

    result = tasks.refresh_rss_feed(FEED_URL)

    assert result == "error"
    cache = RSSFeedCache.objects.get(url=FEED_URL)
    assert "connection refused" in cache.error
    assert cache.entries == []


def test_task_keeps_data_on_304(monkeypatch):
    RSSFeedCache.objects.create(
        url=FEED_URL,
        data={"feed_title": "Example Blog", "entries": [{"title": "kept"}]},
        etag='"abc"',
        error="stale error",
    )
    monkeypatch.setattr(tasks.requests, "get", _fake_get(FakeResponse(status_code=304)))

    result = tasks.refresh_rss_feed(FEED_URL)

    assert result == "not-modified"
    cache = RSSFeedCache.objects.get(url=FEED_URL)
    assert [e["title"] for e in cache.entries] == ["kept"]
    assert cache.error == ""


def test_task_records_a_bad_http_status(monkeypatch):
    monkeypatch.setattr(tasks.requests, "get", _fake_get(FakeResponse(status_code=503)))

    tasks.refresh_rss_feed(FEED_URL)

    assert RSSFeedCache.objects.get(url=FEED_URL).error == "HTTP 503"


def test_refresh_all_fans_out_over_distinct_urls(monkeypatch):
    other = "https://example.net/rss"
    RSSFeedCMSPlugin.objects.create(url=FEED_URL, placeholder_id=None)
    RSSFeedCMSPlugin.objects.create(url=FEED_URL, placeholder_id=None)
    RSSFeedCMSPlugin.objects.create(url=other, placeholder_id=None)

    called = []
    monkeypatch.setattr(tasks.refresh_rss_feed, "delay", lambda url: called.append(url))

    count = tasks.refresh_rss_feeds()

    assert count == 2
    assert sorted(called) == sorted([FEED_URL, other])


def _render(instance):
    context = RSSFeedPlugin().render({"instance": instance}, instance, None)
    return render_to_string("fds_cms_at/rss_feed.html", context)


def test_plugin_shows_the_most_recent_entry():
    RSSFeedCache.objects.create(
        url=FEED_URL,
        data={
            "feed_title": "Example Blog",
            "entries": [
                {
                    "title": "Newest post",
                    "link": "https://example.org/2",
                    "summary": "Second body.",
                    "published": "2026-09-02T10:00:00+00:00",
                },
                {
                    "title": "Older post",
                    "link": "https://example.org/1",
                    "summary": "First body.",
                    "published": "2026-09-01T10:00:00+00:00",
                },
            ],
        },
    )
    instance = RSSFeedCMSPlugin(url=FEED_URL, count=1, show_summary=True)

    html = _render(instance)

    assert "Newest post" in html
    assert "https://example.org/2" in html
    assert "Second body." in html
    assert "Older post" not in html  # count=1


def test_plugin_count_and_summary_toggle():
    RSSFeedCache.objects.create(
        url=FEED_URL,
        data={
            "feed_title": "Example Blog",
            "entries": [
                {"title": "A", "link": "/a", "summary": "sa", "published": None},
                {"title": "B", "link": "/b", "summary": "sb", "published": None},
            ],
        },
    )
    html = _render(RSSFeedCMSPlugin(url=FEED_URL, count=2, show_summary=False))

    assert "A" in html and "B" in html
    assert "sa" not in html and "sb" not in html


def test_plugin_title_override_and_empty_cache():
    # No cache row at all -> nothing rendered (outside edit mode).
    assert _render(RSSFeedCMSPlugin(url=FEED_URL, count=1)).strip() == ""

    RSSFeedCache.objects.create(
        url=FEED_URL,
        data={"feed_title": "Feed name", "entries": [{"title": "x", "link": "/x"}]},
    )
    html = _render(RSSFeedCMSPlugin(url=FEED_URL, count=1, title="My heading"))
    assert "My heading" in html
    assert "Feed name" not in html
