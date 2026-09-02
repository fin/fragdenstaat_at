from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext_lazy as _

from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool

from .models import RSSFeedCache, RSSFeedCMSPlugin


@plugin_pool.register_plugin
class RSSFeedPlugin(CMSPluginBase):
    model = RSSFeedCMSPlugin
    module = _("FragDenStaat")
    name = _("RSS feed")
    render_template = "fds_cms_at/rss_feed.html"
    # Content is refreshed out of band by a Celery task; a single indexed
    # lookup per request is cheaper than reasoning about plugin-cache busting.
    cache = False

    def render(self, context, instance, placeholder):
        context = super().render(context, instance, placeholder)

        cache = RSSFeedCache.objects.filter(url=instance.url).first()
        entries = list(cache.entries) if cache else []
        for entry in entries:
            entry["published_dt"] = (
                parse_datetime(entry["published"]) if entry.get("published") else None
            )

        context.update(
            {
                "feed": cache,
                "feed_title": instance.title or (cache.feed_title if cache else ""),
                "entries": entries[: instance.count or 1],
            }
        )
        return context
