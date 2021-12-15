# Generated by Django 3.2.8 on 2021-12-11 19:56

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import djangocms_bootstrap4.fields
import filer.fields.file
import filer.fields.image


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0022_auto_20180620_1551"),
        migrations.swappable_dependency(
            settings.FILINGCABINET_DOCUMENTCOLLECTION_MODEL
        ),
        ("foirequest", "0053_alter_foimessage_email_headers"),
        migrations.swappable_dependency(settings.FILER_IMAGE_MODEL),
        ("filer", "0013_image_width_height_to_float"),
        ("fds_cms", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CollapsibleCMSPlugin",
            fields=[
                (
                    "cmsplugin_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        related_name="fds_cms_collapsiblecmsplugin",
                        serialize=False,
                        to="cms.cmsplugin",
                    ),
                ),
                ("title", models.CharField(blank=True, max_length=255)),
                ("collapsed", models.BooleanField(default=True)),
                ("extra_classes", models.CharField(blank=True, max_length=255)),
            ],
            options={
                "abstract": False,
            },
            bases=("cms.cmsplugin",),
        ),
        migrations.CreateModel(
            name="DesignContainerCMSPlugin",
            fields=[
                (
                    "cmsplugin_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        related_name="fds_cms_designcontainercmsplugin",
                        serialize=False,
                        to="cms.cmsplugin",
                    ),
                ),
                (
                    "template",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("", "Default template"),
                            ("cms/plugins/designs/speech_bubble.html", "Speech bubble"),
                        ],
                        default="",
                        max_length=50,
                        verbose_name="Template",
                    ),
                ),
                (
                    "background",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("", "None"),
                            ("primary", "Primary"),
                            ("secondary", "Secondary"),
                            ("info", "Info"),
                            ("light", "Light"),
                            ("dark", "Dark"),
                            ("success", "Success"),
                            ("warning", "Warning"),
                            ("danger", "Danger"),
                            ("purple", "Purple"),
                            ("pink", "Pink"),
                            ("yellow", "Yellow"),
                            ("cyan", "Cyan"),
                            ("gray", "Gray"),
                            ("gray-dark", "Gray Dark"),
                            ("white", "White"),
                            ("gray-100", "Gray 100"),
                            ("gray-200", "Gray 200"),
                            ("gray-300", "Gray 300"),
                            ("gray-400", "Gray 400"),
                            ("gray-500", "Gray 500"),
                            ("gray-600", "Gray 600"),
                            ("gray-700", "Gray 700"),
                            ("gray-800", "Gray 800"),
                            ("gray-900", "Gray 900"),
                            ("blue-10", "Blue 10"),
                            ("blue-20", "Blue 20"),
                            ("blue-30", "Blue 30"),
                            ("blue-100", "Blue 100"),
                            ("blue-200", "Blue 200"),
                            ("blue-300", "Blue 300"),
                            ("blue-400", "Blue 400"),
                            ("blue-500", "Blue 500"),
                            ("blue-600", "Blue 600"),
                            ("blue-700", "Blue 700"),
                            ("blue-800", "Blue 800"),
                            ("yellow-100", "Yellow 100"),
                            ("yellow-200", "Yellow 200"),
                            ("yellow-300", "Yellow 300"),
                        ],
                        default="",
                        max_length=50,
                        verbose_name="Background",
                    ),
                ),
                (
                    "style",
                    models.CharField(
                        blank=True,
                        choices=[("", "Default"), ("heavy", "Heavy")],
                        default="",
                        max_length=50,
                        verbose_name="Style",
                    ),
                ),
                ("extra_classes", models.CharField(blank=True, max_length=255)),
                ("container", models.BooleanField(default=True)),
                ("padding", models.BooleanField(default=True)),
            ],
            options={
                "abstract": False,
            },
            bases=("cms.cmsplugin",),
        ),
        migrations.CreateModel(
            name="ModalCMSPlugin",
            fields=[
                (
                    "cmsplugin_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        related_name="fds_cms_modalcmsplugin",
                        serialize=False,
                        to="cms.cmsplugin",
                    ),
                ),
                ("identifier", models.CharField(max_length=255)),
                (
                    "tag_type",
                    djangocms_bootstrap4.fields.TagTypeField(
                        choices=[
                            ("div", "div"),
                            ("section", "section"),
                            ("article", "article"),
                            ("header", "header"),
                            ("footer", "footer"),
                            ("aside", "aside"),
                        ],
                        default="div",
                        help_text="Select the HTML tag to be used.",
                        max_length=255,
                        verbose_name="Tag type",
                    ),
                ),
                (
                    "attributes",
                    djangocms_bootstrap4.fields.AttributesField(
                        blank=True, default=dict, verbose_name="Attributes"
                    ),
                ),
                (
                    "dialog_attributes",
                    djangocms_bootstrap4.fields.AttributesField(
                        blank=True, default=dict, verbose_name="Attributes"
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("cms.cmsplugin",),
        ),
        migrations.CreateModel(
            name="ShareLinksCMSPlugin",
            fields=[
                (
                    "cmsplugin_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        related_name="fds_cms_sharelinkscmsplugin",
                        serialize=False,
                        to="cms.cmsplugin",
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("url", models.URLField(blank=True)),
            ],
            options={
                "abstract": False,
            },
            bases=("cms.cmsplugin",),
        ),
        migrations.CreateModel(
            name="SliderCMSPlugin",
            fields=[
                (
                    "cmsplugin_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        related_name="fds_cms_slidercmsplugin",
                        serialize=False,
                        to="cms.cmsplugin",
                    ),
                ),
                ("title", models.CharField(blank=True, max_length=255)),
                ("extra_classes", models.CharField(blank=True, max_length=255)),
                ("options", models.TextField(blank=True)),
                ("wrapper_classes", models.CharField(blank=True, max_length=255)),
            ],
            options={
                "abstract": False,
            },
            bases=("cms.cmsplugin",),
        ),
        migrations.CreateModel(
            name="VegaChartCMSPlugin",
            fields=[
                (
                    "cmsplugin_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        related_name="fds_cms_vegachartcmsplugin",
                        serialize=False,
                        to="cms.cmsplugin",
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("vega_json", models.TextField(default="")),
            ],
            options={
                "abstract": False,
            },
            bases=("cms.cmsplugin",),
        ),
        migrations.AddField(
            model_name="documentembedcmsplugin",
            name="page_number",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="documentembedcmsplugin",
            name="settings",
            field=models.TextField(default="{}"),
        ),
        migrations.AddField(
            model_name="documentpagescmsplugin",
            name="size",
            field=models.CharField(
                choices=[("small", "Small"), ("normal", "Normal"), ("large", "Large")],
                default="small",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="pageannotationcmsplugin",
            name="zoom",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="primarylinkcmsplugin",
            name="extra_classes",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="primarylinkcmsplugin",
            name="link_label",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name="foirequestlistcmsplugin",
            name="template",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "Default template"),
                    ("foirequest/cms_plugins/list_follow.html", "Follow template"),
                ],
                help_text="template used to display the plugin",
                max_length=250,
                verbose_name="template",
            ),
        ),
        migrations.AlterField(
            model_name="primarylinkcmsplugin",
            name="template",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "Default template"),
                    ("featured.html", "Featured template"),
                    ("campaign.html", "Campaign template"),
                ],
                default="",
                max_length=50,
                verbose_name="Template",
            ),
        ),
        migrations.CreateModel(
            name="SVGImageCMSPlugin",
            fields=[
                (
                    "cmsplugin_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        related_name="fds_cms_svgimagecmsplugin",
                        serialize=False,
                        to="cms.cmsplugin",
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                (
                    "svg",
                    filer.fields.file.FilerFileField(
                        blank=True,
                        default=None,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="filer.file",
                        verbose_name="image",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("cms.cmsplugin",),
        ),
        migrations.CreateModel(
            name="OneClickFoiRequestCMSPlugin",
            fields=[
                (
                    "cmsplugin_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        related_name="fds_cms_oneclickfoirequestcmsplugin",
                        serialize=False,
                        to="cms.cmsplugin",
                    ),
                ),
                (
                    "redirect_url",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("reference", models.CharField(blank=True, default="", max_length=255)),
                (
                    "template",
                    models.CharField(
                        blank=True,
                        choices=[("", "Default template")],
                        default="",
                        max_length=50,
                        verbose_name="Template",
                    ),
                ),
                (
                    "foirequest",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="foirequest.foirequest",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("cms.cmsplugin",),
        ),
        migrations.CreateModel(
            name="FdsPageExtension",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("search_index", models.BooleanField(default=True)),
                (
                    "extended_object",
                    models.OneToOneField(
                        editable=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="cms.page",
                    ),
                ),
                (
                    "image",
                    filer.fields.image.FilerImageField(
                        blank=True,
                        default=None,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.FILER_IMAGE_MODEL,
                        verbose_name="image",
                    ),
                ),
                (
                    "public_extension",
                    models.OneToOneField(
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="draft_extension",
                        to="fds_cms.fdspageextension",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="DocumentPortalEmbedCMSPlugin",
            fields=[
                (
                    "cmsplugin_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        related_name="fds_cms_documentportalembedcmsplugin",
                        serialize=False,
                        to="cms.cmsplugin",
                    ),
                ),
                ("settings", models.JSONField(blank=True, default=dict)),
                (
                    "portal",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="filingcabinet.documentportal",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("cms.cmsplugin",),
        ),
        migrations.CreateModel(
            name="DocumentCollectionEmbedCMSPlugin",
            fields=[
                (
                    "cmsplugin_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        related_name="fds_cms_documentcollectionembedcmsplugin",
                        serialize=False,
                        to="cms.cmsplugin",
                    ),
                ),
                ("settings", models.TextField(default="{}")),
                (
                    "collection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to=settings.FILINGCABINET_DOCUMENTCOLLECTION_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("cms.cmsplugin",),
        ),
    ]