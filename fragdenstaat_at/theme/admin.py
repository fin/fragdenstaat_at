from django.contrib import admin
from django.core.exceptions import BadRequest, PermissionDenied
from django.db.models import Model
from django.http import JsonResponse
from django.urls import path, reverse_lazy

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


def make_tag_autocomplete_admin(model: type[Model], url_name: str):
    """Register a tag model with an admin autocomplete endpoint.

    Ported from DE alongside its fds_donation, which uses it for donor and
    donation tag autocompletes.
    """

    @admin.register(model)
    class TagAutocompleteAdmin(admin.ModelAdmin):
        def get_urls(self):
            urls = super().get_urls()
            my_urls = [
                path(
                    "autocomplete/",
                    self.admin_site.admin_view(self.autocomplete),
                    name=url_name,
                ),
            ]
            return my_urls + urls

        def autocomplete(self, request):
            if not request.method == "GET":
                raise BadRequest
            if not self.has_change_permission(request):
                raise PermissionDenied

            query = request.GET.get("q", "")
            tags = []
            if query:
                tags = model.objects.filter(name__istartswith=query).values_list(
                    "name", flat=True
                )

            return JsonResponse(
                {"objects": [{"value": t, "label": t} for t in tags]}, safe=False
            )

    return reverse_lazy(f"admin:{url_name}")
