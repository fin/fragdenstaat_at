# Generated by Django 3.2.8 on 2021-11-26 11:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fds_donation", "0035_donationprogressbarcmsplugin_received_donations_only"),
    ]

    operations = [
        migrations.AddField(
            model_name="donationformcmsplugin",
            name="extra_classes",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]