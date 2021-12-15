# Generated by Django 3.2.8 on 2021-12-11 20:57

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import filer.fields.image


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.FILER_IMAGE_MODEL),
        ('cms', '0022_auto_20180620_1551'),
        ('fds_cms', '0002_auto_20211211_2056'),
    ]

    operations = [
        migrations.CreateModel(
            name='CardCMSPlugin',
            fields=[
                ('cmsplugin_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, related_name='fds_cms_cardcmsplugin', serialize=False, to='cms.cmsplugin')),
                ('border', models.CharField(choices=[('none', 'None'), ('blue', 'Blue'), ('gray', 'Gray'), ('yellow', 'Yellow')], default='gray', max_length=50, verbose_name='Border')),
                ('shadow', models.CharField(choices=[('no', 'No'), ('auto', 'Auto'), ('always', 'Always')], default='auto', max_length=10, verbose_name='Shadow')),
                ('spacing', models.CharField(choices=[('sm', 'Small'), ('md', 'Medium'), ('lg', 'Large')], default='lg', max_length=3, verbose_name='Spacing')),
                ('extra_classes', models.CharField(blank=True, max_length=255)),
            ],
            options={
                'abstract': False,
            },
            bases=('cms.cmsplugin',),
        ),
        migrations.CreateModel(
            name='CardHeaderCMSPlugin',
            fields=[
                ('cmsplugin_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, related_name='fds_cms_cardheadercmsplugin', serialize=False, to='cms.cmsplugin')),
                ('title', models.CharField(blank=True, max_length=255)),
                ('icon', models.CharField(blank=True, help_text='Enter an icon name from the <a href="https://fontawesome.com/v4.7.0/icons/" target="_blank">FontAwesome 4 icon set</a>', max_length=50, verbose_name='Icon')),
                ('extra_classes', models.CharField(blank=True, max_length=255)),
            ],
            options={
                'abstract': False,
            },
            bases=('cms.cmsplugin',),
        ),
        migrations.CreateModel(
            name='CardIconCMSPlugin',
            fields=[
                ('cmsplugin_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, related_name='fds_cms_cardiconcmsplugin', serialize=False, to='cms.cmsplugin')),
                ('icon', models.CharField(blank=True, help_text='Enter an icon name from the <a href="https://fontawesome.com/v4.7.0/icons/" target="_blank">FontAwesome 4 icon set</a>', max_length=255)),
                ('overlap', models.CharField(choices=[('left', 'Left'), ('right', 'Right')], default='right', max_length=10, verbose_name='Overlap')),
                ('extra_classes', models.CharField(blank=True, max_length=255)),
            ],
            options={
                'abstract': False,
            },
            bases=('cms.cmsplugin',),
        ),
        migrations.CreateModel(
            name='CardInnerCMSPlugin',
            fields=[
                ('cmsplugin_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, related_name='fds_cms_cardinnercmsplugin', serialize=False, to='cms.cmsplugin')),
                ('background', models.CharField(blank=True, choices=[('', 'None'), ('primary', 'Primary'), ('secondary', 'Secondary'), ('info', 'Info'), ('light', 'Light'), ('dark', 'Dark'), ('success', 'Success'), ('warning', 'Warning'), ('danger', 'Danger'), ('purple', 'Purple'), ('pink', 'Pink'), ('yellow', 'Yellow'), ('cyan', 'Cyan'), ('gray', 'Gray'), ('gray-dark', 'Gray Dark'), ('white', 'White'), ('gray-100', 'Gray 100'), ('gray-200', 'Gray 200'), ('gray-300', 'Gray 300'), ('gray-400', 'Gray 400'), ('gray-500', 'Gray 500'), ('gray-600', 'Gray 600'), ('gray-700', 'Gray 700'), ('gray-800', 'Gray 800'), ('gray-900', 'Gray 900'), ('blue-10', 'Blue 10'), ('blue-20', 'Blue 20'), ('blue-30', 'Blue 30'), ('blue-100', 'Blue 100'), ('blue-200', 'Blue 200'), ('blue-300', 'Blue 300'), ('blue-400', 'Blue 400'), ('blue-500', 'Blue 500'), ('blue-600', 'Blue 600'), ('blue-700', 'Blue 700'), ('blue-800', 'Blue 800'), ('yellow-100', 'Yellow 100'), ('yellow-200', 'Yellow 200'), ('yellow-300', 'Yellow 300')], default='', max_length=50, verbose_name='Background')),
                ('extra_classes', models.CharField(blank=True, max_length=255)),
            ],
            options={
                'abstract': False,
            },
            bases=('cms.cmsplugin',),
        ),
        migrations.CreateModel(
            name='CardImageCMSPlugin',
            fields=[
                ('cmsplugin_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, related_name='fds_cms_cardimagecmsplugin', serialize=False, to='cms.cmsplugin')),
                ('overlap', models.CharField(choices=[('left', 'Left'), ('right', 'Right')], default='right', max_length=10, verbose_name='Overlap')),
                ('extra_classes', models.CharField(blank=True, max_length=255)),
                ('image', filer.fields.image.FilerImageField(blank=True, default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.FILER_IMAGE_MODEL, verbose_name='image')),
            ],
            options={
                'abstract': False,
            },
            bases=('cms.cmsplugin',),
        ),
    ]