import logging
from io import BytesIO

from django.apps import AppConfig
from django.core.files.base import ContentFile
from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext_lazy as _

from PIL import Image

try:
    import pillow_avif  # noqa
except ImportError:
    pillow_avif = None

logger = logging.getLogger(__name__)


class FdsCmsConfig(AppConfig):
    name = "fragdenstaat_at.fds_cms"
    verbose_name = "FragDenStaat CMS"

    def ready(self):
        from froide.account import account_merged
        from froide.helper.search import search_registry

        from . import listeners  # noqa

        account_merged.connect(merge_user)
        search_registry.register(add_search)

        if pillow_avif is not None:
            from easy_thumbnails.signals import thumbnail_created

            thumbnail_created.connect(store_as_avif)


def merge_user(sender, old_user=None, new_user=None, **kwargs):
    from .models import FoiRequestListCMSPlugin

    FoiRequestListCMSPlugin.objects.filter(user=old_user).update(user=new_user)


def add_search(request):
    try:
        return {
            "title": _("Help pages"),
            "name": "cms",
            "url": reverse("fds_cms:fds_cms-search"),
        }
    except NoReverseMatch:
        return


def store_as_avif(sender, **kwargs):
    if not sender.name.endswith((".png", ".jpg", ".jpeg")):
        return
    logger.info("Converting %s to avif", sender.name)
    avif_name = ".".join([sender.name, "avif"])
    img_file = sender.storage.open(sender.name, "rb")
    im = Image.open(img_file)
    out_file = BytesIO()
    im.save(out_file, format="avif", quality=80)
    out_file.seek(0)
    sender.storage.save(avif_name, ContentFile(out_file.read()))
    logger.info("Done converting %s to avif", sender.name)
