"""Theme template tags.

The fax reply QR code (see docs/qr-code-on-faxes.md) and the helpers behind the
"this request will be sent by fax" notice on the make-request page.
"""

import io

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

import segno

register = template.Library()


def _fax_handler_registered():
    """Whether froide will actually route an outgoing message to fax.

    ``get_request_outgoing_message_kind`` only considers handlers listed in
    ``FROIDE_CONFIG["message_handlers"]``. Without the ``fax`` entry a
    ``FaxOverride`` changes nothing -- the request still goes out by email -- so
    the notice must stay hidden or it tells the user something untrue.
    """
    return "fax" in settings.FROIDE_CONFIG.get("message_handlers", {})


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
    if not _fax_handler_registered():
        return ""

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
    if not _fax_handler_registered():
        return False

    from froide_fax.models import FaxOverride

    return any(FaxOverride.objects.is_fax_recipient(pb) for pb in publicbodies or [])


@register.simple_tag
def foirequest_delivered_by_fax(foirequest):
    """True when a reply to this request could be diverted to fax.

    A usable FaxOverride on the public body diverts a reply to fax when the
    address chosen in the send-message form is the body's own default -- the one
    that refuses email (froide-fax keys ``handle_foirequest_outgoing_messages``
    on ``recipient_email``). This is the coarse gate for rendering the reply-form
    notice; the notice's script narrows it to the selected "To" address.
    """
    if not _fax_handler_registered():
        return False
    if foirequest is None or foirequest.public_body_id is None:
        return False

    from froide_fax.models import FaxOverride

    return FaxOverride.objects.is_fax_recipient(foirequest.public_body)
