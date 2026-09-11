import logging

from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext_lazy as _

from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool

from .forms import RSSFeedPluginForm
from .models import RSSFeedCache, RSSFeedCMSPlugin
from .tasks import refresh_rss_feed

logger = logging.getLogger(__name__)


@plugin_pool.register_plugin
class RSSFeedPlugin(CMSPluginBase):
    model = RSSFeedCMSPlugin
    form = RSSFeedPluginForm
    module = _("FragDenStaat")
    name = _("RSS feed")
    render_template = "fds_cms_at/rss_feed.html"
    # Content is refreshed out of band by a Celery task; a single indexed
    # lookup per request is cheaper than reasoning about plugin-cache busting.
    cache = False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self.prime_feed_cache(obj.url, force=form.cleaned_data.get("refresh_now"))

    @staticmethod
    def prime_feed_cache(url, force=False):
        """Populate the shared cache right away so the editor sees entries
        without waiting for the periodic Celery task. Only the first plugin to
        point at a URL pays the fetch; later ones reuse the cache row — unless
        `force` (the form's "refresh now" checkbox), which always re-fetches.
        """
        if not url:
            return
        already_fetched = RSSFeedCache.objects.filter(
            url=url, fetched_at__isnull=False
        ).exists()
        if already_fetched and not force:
            return
        try:
            refresh_rss_feed(url, force=force)
        except Exception:
            logger.exception("Initial RSS fetch failed for %s", url)

    def render(self, context, instance, placeholder):
        context = super().render(context, instance, placeholder)

        cache = RSSFeedCache.objects.filter(url=instance.url).first()
        entries = list(cache.entries) if cache else []
        for entry in entries:
            entry["published_dt"] = (
                parse_datetime(entry["published"]) if entry.get("published") else None
            )

        feed_title = ""
        if instance.show_title:
            feed_title = instance.title or (cache.feed_title if cache else "")

        context.update(
            {
                "feed": cache,
                "feed_title": feed_title,
                "entries": entries[: instance.count or 1],
            }
        )
        return context
