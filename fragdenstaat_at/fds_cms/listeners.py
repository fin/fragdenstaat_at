from django.dispatch.dispatcher import receiver

from djangocms_versioning.constants import OPERATION_PUBLISH, OPERATION_UNPUBLISH
from djangocms_versioning.signals import post_version_operation

from froide.helper.tasks import search_instance_delete, search_instance_save

from .models import FdsPageExtension


@receiver(post_version_operation, dispatch_uid="publish_cms_page")
def handle(sender, operation, obj, **kwargs):
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
