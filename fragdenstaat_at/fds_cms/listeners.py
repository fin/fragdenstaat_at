from django.dispatch import receiver

from djangocms_versioning.constants import OPERATION_PUBLISH, OPERATION_UNPUBLISH
from djangocms_versioning.signals import post_version_operation

from froide.helper.tasks import search_instance_delete, search_instance_save

from .models import FdsPageExtension


@receiver(post_version_operation, dispatch_uid="publish_cms_page")
def handle(sender, operation, obj, **kwargs):
    """Keep the search index in step with djangocms-versioning publish state.

    Replaces the django-cms 3 ``post_publish`` / ``post_unpublish`` signals,
    which no longer exist under versioning.
    """
    instance = obj.content
    if operation == OPERATION_PUBLISH:
        try:
            page = instance.page
        except AttributeError:
            return
        try:
            search_index = page.fdspageextension.search_index
        except FdsPageExtension.DoesNotExist:
            # In case page extension does not exist yet, assume indexing is OK
            search_index = True
        if search_index:
            search_instance_save.delay(instance._meta.label_lower, instance.pk)
        else:
            search_instance_delete.delay(instance._meta.label_lower, instance.pk)
    elif operation == OPERATION_UNPUBLISH:
        search_instance_delete.delay(instance._meta.label_lower, instance.pk)


# NOTE: DE also registers an easy-thumbnails `saved_file` receiver here that
# defers thumbnail generation to `fds_cms.tasks.generate_thumbnails`. AT has no
# `fds_cms/tasks.py` and has not enabled async thumbnailing, so that receiver is
# deliberately not ported -- it is what made this module un-importable.
