from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import RSSFeedCache


@admin.register(RSSFeedCache)
class RSSFeedCacheAdmin(admin.ModelAdmin):
    list_display = ("url", "fetched_at", "entry_count", "ok")
    readonly_fields = (
        "url",
        "fetched_at",
        "etag",
        "last_modified",
        "error",
        "data",
    )
    search_fields = ("url",)

    @admin.display(description=_("entries"))
    def entry_count(self, obj):
        return len(obj.entries)

    @admin.display(boolean=True, description=_("ok"))
    def ok(self, obj):
        return not obj.error

    def has_add_permission(self, request):
        return False
