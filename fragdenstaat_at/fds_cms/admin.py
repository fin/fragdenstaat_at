from django.contrib import admin

from cms.extensions import PageExtensionAdmin

from .models import FdsPageExtension


class FdsPageExtensionAdmin(PageExtensionAdmin):
    pass


admin.site.register(FdsPageExtension, FdsPageExtensionAdmin)

# The CustomStaticPlaceholderAdmin that used to live here is gone: django-cms
# 5.1 removed StaticPlaceholder (see fds_cms/migrations/0006). Static content is
# now djangocms-alias Aliases, which ship their own admin.
