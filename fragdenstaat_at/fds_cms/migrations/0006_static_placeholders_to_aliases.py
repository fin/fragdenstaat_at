"""Convert cms StaticPlaceholders into djangocms-alias static Aliases.

django-cms 5.1 deletes the ``StaticPlaceholder`` model outright (``cms.0042``).
AT's live footer, top banner, dropdown banner and help footer are all static
placeholders, so their content has to be moved before that migration runs.

This is a data migration rather than a management command on purpose: it must
run automatically, in the right order, on every database -- including
production, which nobody can rehearse against beforehand. The development
extract is *not* faithful here: ``export_dev_db.py`` writes ``public_id`` into
both the draft and public FKs, so draft/public divergence cannot be exercised
locally. The code below therefore treats that divergence as the normal case.

Ordering is what makes this work: it depends on ``cms.0041`` (the last state in
which ``StaticPlaceholder`` still exists) and declares ``run_before`` on
``cms.0042`` (which deletes it), so the historical model is available regardless
of which django-cms version is installed.

⚠️ Not reversible. Reversing leaves the Aliases in place and does not restore
StaticPlaceholders -- rolling back past this point needs a database restore.
"""

from django.db import migrations

# djangocms_alias.constants.DEFAULT_STATIC_ALIAS_CATEGORY_NAME -- inlined, since
# migrations must not import application code that may change.
DEFAULT_STATIC_ALIAS_CATEGORY_NAME = "Static Alias"
PUBLISHED = "published"


def get_migration_user(apps, schema_editor):
    """A user to attribute the created versions to.

    Prefers ``settings.CMS_MIGRATION_USER_ID`` (AT sets it), then any superuser,
    then any user at all. Returns None if the table is empty, which is valid --
    ``Version.created_by`` is nullable.
    """
    from django.conf import settings

    User = apps.get_model(settings.AUTH_USER_MODEL)
    user_id = getattr(settings, "CMS_MIGRATION_USER_ID", None)
    if user_id:
        user = User.objects.filter(pk=user_id).first()
        if user:
            return user
    return (
        User.objects.filter(is_superuser=True).order_by("pk").first()
        or User.objects.order_by("pk").first()
    )


def static_placeholders_to_aliases(apps, schema_editor):
    from django.conf import settings

    StaticPlaceholder = apps.get_model("cms", "StaticPlaceholder")
    CMSPlugin = apps.get_model("cms", "CMSPlugin")
    Placeholder = apps.get_model("cms", "Placeholder")
    Alias = apps.get_model("djangocms_alias", "Alias")
    AliasContent = apps.get_model("djangocms_alias", "AliasContent")
    Category = apps.get_model("djangocms_alias", "Category")
    Version = apps.get_model("djangocms_versioning", "Version")
    ContentType = apps.get_model("contenttypes", "ContentType")

    static_placeholders = list(StaticPlaceholder.objects.all())
    if not static_placeholders:
        return

    user = get_migration_user(apps, schema_editor)
    alias_content_ct = ContentType.objects.get_for_model(AliasContent)

    category = Category.objects.filter(
        translations__name=DEFAULT_STATIC_ALIAS_CATEGORY_NAME
    ).first()
    if category is None:
        # `Category` is a parler TranslatableModel whose `save()` walks
        # `_parler_meta`, which historical models do not have. `bulk_create`
        # skips `save()`, so it is the way to insert one from a migration.
        CategoryTranslation = apps.get_model("djangocms_alias", "CategoryTranslation")
        category = Category.objects.bulk_create([Category()])[0]
        CategoryTranslation.objects.bulk_create(
            [
                CategoryTranslation(
                    master=category,
                    language_code=language,
                    name=DEFAULT_STATIC_ALIAS_CATEGORY_NAME,
                )
                for language in {settings.LANGUAGE_CODE, "en"}
            ]
        )

    for static_placeholder in static_placeholders:
        code = static_placeholder.code
        if not code:
            continue

        # Idempotent: an Alias for this code means the conversion already ran.
        if Alias.objects.filter(
            static_code=code, site_id=static_placeholder.site_id
        ).exists():
            continue

        # The public placeholder is what visitors see; fall back to the draft
        # when a placeholder was never published. Unpublished draft edits that
        # differ from public are intentionally NOT carried over -- migrating
        # them would publish content nobody approved.
        source_placeholder_id = static_placeholder.public_id
        plugins = CMSPlugin.objects.filter(placeholder_id=source_placeholder_id)
        if source_placeholder_id is None or not plugins.exists():
            source_placeholder_id = static_placeholder.draft_id
            plugins = CMSPlugin.objects.filter(placeholder_id=source_placeholder_id)

        alias = Alias.objects.create(
            category=category,
            static_code=code,
            site_id=static_placeholder.site_id,
            creation_method="code",
            position=0,
        )

        # `.order_by()` first: CMSPlugin has a Meta ordering, and its columns
        # leak into SELECT DISTINCT, so without this `.distinct()` returns one
        # row per plugin and we would create an AliasContent per plugin.
        languages = sorted(
            set(
                plugins.order_by().values_list("language", flat=True).distinct()
            )
        ) or [settings.LANGUAGE_CODE]

        for language in languages:
            alias_content = AliasContent.objects.create(
                alias=alias,
                name=static_placeholder.name or code,
                language=language,
            )
            # Mirrors AliasContent.placeholder: slot is the static_code.
            placeholder = Placeholder.objects.create(
                slot=code or "content",
                content_type=alias_content_ct,
                object_id=alias_content.pk,
            )
            # Move rather than copy: the source is about to be deleted, and
            # copying would need plugin-model duplication that historical
            # models cannot do.
            CMSPlugin.objects.filter(
                placeholder_id=source_placeholder_id, language=language
            ).update(placeholder=placeholder)

            Version.objects.create(
                content_type=alias_content_ct,
                object_id=alias_content.pk,
                state=PUBLISHED,
                number="1",
                created_by=user,
            )

        # Drop the source Placeholder rows. cms.0042 deletes StaticPlaceholder
        # but not these, which would leave rows whose content_type points at a
        # model that no longer exists -- enough to break `dumpdata` and to
        # confuse later migrations.
        #
        # This also discards draft-only plugins that were never published. That
        # is deliberate: once StaticPlaceholder is gone there is no UI left to
        # edit or publish them, so they are unreachable either way.
        Placeholder.objects.filter(
            pk__in=[
                pk
                for pk in (static_placeholder.draft_id, static_placeholder.public_id)
                if pk is not None
            ]
        ).delete()


def reverse_noop(apps, schema_editor):
    """Deliberately does nothing -- see the module docstring."""


class Migration(migrations.Migration):
    dependencies = [
        ("fds_cms", "0005_borderedsectioncmsplugin_attributes_and_more"),
        # Last cms state in which StaticPlaceholder still exists.
        ("cms", "0041_alter_pageurl_unique_together_pageurl_site_and_more"),
        ("djangocms_alias", "0007_alter_category_options_alter_aliasplugin_alias"),
        ("djangocms_versioning", "0018_fix_typo"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    # Must run before django-cms deletes the model we read from.
    run_before = [
        ("cms", "0042_remove_placeholderreference_placeholder_ref_and_more"),
    ]

    operations = [
        migrations.RunPython(static_placeholders_to_aliases, reverse_noop),
    ]
