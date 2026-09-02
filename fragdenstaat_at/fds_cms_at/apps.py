from django.apps import AppConfig


class FdsCmsAtConfig(AppConfig):
    """AT-only CMS plugins.

    Kept out of fds_cms (which is synced from fragdenstaat_de) so Austria-
    specific additions do not complicate that merge.
    """

    name = "fragdenstaat_at.fds_cms_at"
    verbose_name = "FragDenStaat AT CMS"
