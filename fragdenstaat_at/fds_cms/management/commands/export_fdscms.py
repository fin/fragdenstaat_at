from django.core.management.commands.dumpdata import Command as DumpataCommand


class Command(DumpataCommand):
    """
    Dumpdata for all CMS apps
    """

    help = "load shapefiles to georegion"

    def handle(self, *args, **options):
        super(Command, self).handle(
            *[
                "cms",
                "fds_cms",
                "djangocms_text_ckeditor",
                "djangocms_picture",
                "djangocms_video",
            ],
            **options
        )
