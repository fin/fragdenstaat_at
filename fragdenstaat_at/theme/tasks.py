from django.conf import settings

from froide.celery import app as celery_app


def _legal_backup_configured():
    """Legal backup needs a WebDAV target; without one there is nothing to do.

    DE's legal_backup.get_webdav() returns None when unconfigured but its callers
    unpack the result immediately, so an unconfigured install raises TypeError.
    Guard here rather than in legal_backup.py, so that module stays identical to
    DE's and can keep being pulled from it.
    """
    return bool(
        getattr(settings, "FDS_LEGAL_BACKUP_URL", None)
        and getattr(settings, "FDS_LEGAL_BACKUP_CREDENTIALS", None)
    )


@celery_app.task(name="fragdenstaat_at.theme.make_legal_backup")
def make_legal_backup(user_id):
    from froide.account.models import User

    from .legal_backup import make_legal_backup_for_user

    if not _legal_backup_configured():
        return

    try:
        user = User.objects.get(
            id=user_id,
        )
    except User.DoesNotExist:
        return
    make_legal_backup_for_user(user)


@celery_app.task(name="fragdenstaat_at.theme.cleanup_legal_backups_task")
def cleanup_legal_backups_task():
    from .legal_backup import cleanup_legal_backups

    if not _legal_backup_configured():
        return

    cleanup_legal_backups()


# The update_amenities task and theme/amenity_updater.py are gone: they ingested
# OSM amenities for froide_food / froide_campaign, neither of which AT installs,
# and django-amenities was dropped in D6. Nothing called the task.
