from django.contrib import admin

from leaflet.admin import LeafletGeoAdmin

from froide.publicbody import admin as pb_admin
from froide.publicbody.models import PublicBody

# A deliberately minimal subset of DE's theme/admin.py. DE's version also
# customises User, GeoRegion, Amenity and InformationObject admins, which would
# drag back django-amenities and other apps D6 dropped. `PublicBodyAdmin` is
# kept because fds_mailing monkey-patches a "setup mailing" action onto it.


class PublicBodyAdmin(pb_admin.PublicBodyAdminMixin, LeafletGeoAdmin):
    pass


admin.site.unregister(PublicBody)
admin.site.register(PublicBody, PublicBodyAdmin)
