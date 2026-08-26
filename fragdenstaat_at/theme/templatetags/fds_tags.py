"""Theme template tags.

Currently just the fax reply QR code; see docs/qr-code-on-faxes.md.
"""

import io

from django import template
from django.utils.safestring import mark_safe

import segno

register = template.Library()


@register.simple_tag
def fax_reply_qr_code(email):
    """Inline SVG QR code of ``mailto:<email>``, sized to survive a fax.

    Some Austrian authorities refuse electronic requests, so those go out by
    fax. froide's inbound path is email-only -- `ReceiveEmailService` matches
    replies on `foirequest.secret_address` -- so a reply threads automatically
    *if* the official retypes a machine-generated address off a 204x98 dpi
    halftoned page. That transcription step is where replies get lost.

    Encodes ``mailto:`` rather than the bare address: it opens an already
    addressed composer, and the seven extra characters cost almost no modules.
    Deliberately no ``?subject=`` or ``?body=`` -- those balloon the payload,
    and smaller modules are exactly what fax destroys.

    Returns SVG, not a PNG data URL, so it stays vector through WeasyPrint.
    Error correction Q, which is affordable at this payload length and buys
    tolerance for the halftoning.
    """
    if not email:
        return ""
    buf = io.BytesIO()
    segno.make(f"mailto:{email}", error="q").save(
        buf, kind="svg", scale=6, border=4, svgclass=None, xmldecl=False
    )
    return mark_safe(buf.getvalue().decode())


@register.simple_tag
def fax_publicbody_ids():
    """Ids of public bodies whose requests go out by fax, comma-separated.

    Rendered into a data attribute so the make-request page can keep the fax
    notice in step with the public body chosen in the chooser, which is a
    client-side change that re-renders no template.

    Only bodies that are actually diverted: FaxOverride.is_usable is enabled
    AND a dialable number. An override we cannot dial diverts nothing, so
    warning about it would be wrong. That check parses the number, so it is
    done in Python rather than in the query -- the table holds one row per
    authority that refuses email, so this stays small.
    """
    from froide_fax.models import FaxOverride

    overrides = FaxOverride.objects.filter(enabled=True).select_related("publicbody")
    return ",".join(str(o.publicbody_id) for o in overrides if o.is_usable)


@register.simple_tag
def any_fax_publicbody(publicbodies):
    """True if any of these public bodies is diverted to fax.

    Used to decide the notice's initial visibility server-side, so a body
    chosen before the page loads is covered even if the script never runs.
    Goes through the manager, which handles the missing reverse OneToOne and
    the enabled/dialable checks in one place.
    """
    from froide_fax.models import FaxOverride

    return any(FaxOverride.objects.is_fax_recipient(pb) for pb in publicbodies or [])
