from django.dispatch.dispatcher import receiver

from cms.signals import post_publish, post_unpublish

from .models import FdsPageExtension
from djangocms_versioning.constants import OPERATION_PUBLISH, OPERATION_UNPUBLISH
from djangocms_versioning.signals import post_version_operation

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


@receiver(saved_file)
def generate_thumbnails_async(sender, fieldfile, **kwargs):
    if sender == Image:
        generate_thumbnails.delay(
            model=sender, pk=fieldfile.instance.pk, field=fieldfile.field.name
        )