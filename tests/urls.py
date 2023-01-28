from django.conf.urls import include
from django.urls import path

from fragdenstaat_at.theme.urls import urlpatterns as base_urlpatterns

urlpatterns = [
    # path("blog/", include("fragdenstaat_at.fds_blog.urls", namespace="blog")),
    path("cms/search/", include("fragdenstaat_at.fds_cms.urls", namespace="fds_cms")),
    # path(
    # "cms/contact/",
    # include("fragdenstaat_at.fds_cms.contact", namespace="fds_cms_contact"),
    # ),
    path(
        "spenden/spende/",
        include("fragdenstaat_at.fds_donation.urls", namespace="fds_donation"),
    ),
    # path("crowdfunding/", include("froide_crowdfunding.urls")),
    # path("food/", include("froide_food.urls")),
    # path("exam/", include("froide_exam.urls")),
] + base_urlpatterns
