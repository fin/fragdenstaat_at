from django.conf.urls import include
from django.urls import URLResolver, path

from fragdenstaat_at.theme.urls import urlpatterns as base_urlpatterns


def _is_donation_mount(pattern):
    return isinstance(pattern, URLResolver) and pattern.namespace == "fds_donation"


# fds_donation is served only through its CMS apphook here (FdsDonationApp on
# the "spenden/spende" page in tests/fixtures/cms.json), as on DE. theme/urls.py
# also mounts it at spenden/ under the same namespace, and that mount comes
# before the cms.urls catch-all, so reverse() would always pick it -- drop it so
# the tests see the apphook's /spenden/spende/... paths.
urlpatterns = [
    # path("blog/", include("fragdenstaat_at.fds_blog.urls", namespace="blog")),
    path("cms/search/", include("fragdenstaat_at.fds_cms.urls", namespace="fds_cms")),
    # path(
    # "cms/contact/",
    # include("fragdenstaat_at.fds_cms.contact", namespace="fds_cms_contact"),
    # ),
    # path("crowdfunding/", include("froide_crowdfunding.urls")),
    # path("food/", include("froide_food.urls")),
    # path("exam/", include("froide_exam.urls")),
] + [p for p in base_urlpatterns if not _is_donation_mount(p)]
