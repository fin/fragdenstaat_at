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
