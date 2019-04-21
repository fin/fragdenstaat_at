import os
import csv

from django.core.management.base import BaseCommand
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.utils import LayerMapping
from django.contrib.gis.geos.error import GEOSException
from django.contrib.gis.db.models.functions import Area
from django.utils import timezone

from slugify import slugify

from froide.georegion.models import GeoRegion

from django.core.management.commands.dumpdata import Command as DumpataCommand


class Command(DumpataCommand):
    """
    Dumpdata for all CMS apps
    """
    help = "load shapefiles to georegion"


    def handle(self, *args, **options):
        super(Command, self).handle(*['cms','fds_cms','djangocms_text_ckeditor',
            'djangocms_picture','djangocms_video'], **options)
