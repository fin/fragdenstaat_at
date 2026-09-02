from django.db import models
from django.utils.translation import gettext_lazy as _

from cms.models.pluginmodel import CMSPlugin

# How many entries the fetch task keeps per feed. The plugin's `count` slices
# into this, so raising a plugin's count later needs no re-fetch up to here.
MAX_STORED_ENTRIES = 10


class RSSFeedCache(models.Model):
    """One fetched feed, keyed by URL and shared by every plugin that points at
    it (a draft and its published copy included). The Celery task writes here;
    plugins only read.
    """

    url = models.URLField(_("feed URL"), unique=True)
    data = models.JSONField(_("cached feed"), default=dict, blank=True)
    fetched_at = models.DateTimeField(_("last fetched"), null=True, blank=True)
    etag = models.CharField(max_length=512, blank=True)
    last_modified = models.CharField(max_length=128, blank=True)
    error = models.TextField(_("last error"), blank=True)

    class Meta:
        verbose_name = _("RSS feed cache")
        verbose_name_plural = _("RSS feed caches")

    def __str__(self):
        return self.url

    @property
    def entries(self):
        return self.data.get("entries", []) if isinstance(self.data, dict) else []

    @property
    def feed_title(self):
        return self.data.get("feed_title", "") if isinstance(self.data, dict) else ""


class RSSFeedCMSPlugin(CMSPlugin):
    url = models.URLField(_("feed URL"))
    title = models.CharField(
        _("heading"),
        max_length=255,
        blank=True,
        help_text=_("Leave blank to use the feed's own title."),
    )
    count = models.PositiveSmallIntegerField(_("entries to show"), default=1)
    show_summary = models.BooleanField(_("show summary text"), default=True)

    def __str__(self):
        return self.title or self.url
