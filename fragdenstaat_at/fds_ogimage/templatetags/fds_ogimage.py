import hashlib
from urllib.parse import quote_plus

from django import template
from django.conf import settings
from django.template.loader import render_to_string
from django.urls import Resolver404, resolve

register = template.Library()


@register.simple_tag(takes_context=True)
def ogimage_url(context, path=None, template=None):
    # No rendering service configured: return empty so callers can fall back to
    # SITE_LOGO instead of emitting og:image with an empty content attribute.
    # Also skips the render_to_string below, which is not free.
    if not settings.FDS_OGIMAGE_URL or not path:
        return ""

    if template is None:
        try:
            match = resolve(path)
        except Resolver404:
            return ""
        view_class = getattr(match.func, "view_class", None)
        if view_class is None:
            return ""
        template = getattr(view_class, "template_name", None)
        if not template:
            return ""

    rendered = render_to_string(template, context.flatten())
    h = hashlib.sha256()
    h.update(rendered.encode("utf-8"))
    hex_digest = h.hexdigest()
    url = settings.FDS_OGIMAGE_URL.format(hash=hex_digest, path=quote_plus(path))
    return url
