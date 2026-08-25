"""The reply-address QR code on outgoing fax letters. docs/qr-code-on-faxes.md.

Two things are worth guarding here, and neither is visible in a rendered PDF:

  - what the QR actually encodes. A QR of the wrong string still looks like a
    QR, and the whole point is that an official scans it instead of retyping a
    machine-generated address off a halftoned page.
  - that the QR is *additive*. If it ever replaced the printed address, an
    unscannable code would become a dead end instead of degrading to today's
    letter.

What these tests cannot tell you is whether the code survives a real fax. Only
sending one and scanning the received page does that -- see the doc.
"""

import re

from django.template.loader import render_to_string
from django.test import TestCase

import pytest
import segno

from froide.foirequest.models.message import MessageKind
from froide.foirequest.tests import factories

from fragdenstaat_at.theme.templatetags.fds_tags import fax_reply_qr_code

EMAIL = "abc123+secret@fragdenstaat.at"


def test_encodes_mailto_not_the_bare_address():
    """The mailto: scheme is the point -- it opens an addressed composer."""
    svg = fax_reply_qr_code(EMAIL)
    assert svg == _svg_for(f"mailto:{EMAIL}")
    assert svg != _svg_for(EMAIL), "encoding the bare address, not a mailto:"


def test_carries_no_subject_or_body_parameters():
    """Those balloon the payload, and small modules are what fax destroys."""
    assert fax_reply_qr_code(EMAIL) == _svg_for(f"mailto:{EMAIL}")
    for noisy in (f"mailto:{EMAIL}?subject=Re", f"mailto:{EMAIL}?body=x"):
        assert fax_reply_qr_code(EMAIL) != _svg_for(noisy)


def test_is_inline_vector_svg():
    """Inline SVG so it stays vector through WeasyPrint; no decl to embed."""
    svg = fax_reply_qr_code(EMAIL)
    assert svg.lstrip().startswith("<svg")
    assert "<?xml" not in svg
    assert "data:image" not in svg


def test_error_correction_is_q():
    """Costs modules, buys tolerance for halftoning. Affordable at this length."""
    assert fax_reply_qr_code(EMAIL) == _svg_for(f"mailto:{EMAIL}", error="q")
    assert fax_reply_qr_code(EMAIL) != _svg_for(f"mailto:{EMAIL}", error="l")


@pytest.mark.parametrize("empty", ["", None])
def test_no_email_renders_nothing(empty):
    assert fax_reply_qr_code(empty) == ""


def _svg_for(payload, error="q"):
    import io

    buf = io.BytesIO()
    segno.make(payload, error=error).save(
        buf, kind="svg", scale=6, border=4, svgclass=None, xmldecl=False
    )
    return buf.getvalue().decode()


class FaxLetterTest(TestCase):
    """Render the real template chain: ours -> froide_fax's -> froide's."""

    def _message(self, kind):
        request = factories.FoiRequestFactory.create()
        return factories.FoiMessageFactory.create(
            request=request,
            kind=kind,
            is_response=False,
            sender_email=EMAIL,
        )

    def _render(self, kind):
        return render_to_string(
            "froide_fax/message_letter.html",
            {"object": self._message(kind), "SITE_NAME": "FragDenStaat"},
        )

    def test_qr_is_added_without_removing_the_printed_address(self):
        html = self._render(MessageKind.EMAIL)
        assert "fax-reply-qr" in html
        assert "<svg" in html
        # block.super's contents must survive: the address and the short URL.
        assert EMAIL in html, "printed reply address was replaced by the QR"
        assert html.count(EMAIL) >= 2, "expected both the mailto link and text"

    def test_via_line_shown_when_the_fax_copies_an_email(self):
        """Mode A: an email really is sent alongside, so the line is true."""
        html = self._render(MessageKind.EMAIL)
        assert re.search(r"Fax (and|und) [Ee]-?mail", html), html[:0]

    def test_via_line_hidden_when_the_fax_replaces_the_email(self):
        """Mode B (FaxOverride): no email is sent, so the line would mislead.

        send_fax_message renders `fax_message.original or fax_message`, so the
        object here is the fax message itself. `original` is None in both modes,
        which is why this keys on `kind`.
        """
        html = self._render(MessageKind.FAX)
        assert not re.search(r"Fax (and|und) [Ee]-?mail", html)
        # ...but the QR still belongs on it. Mode B is where it matters most.
        assert "fax-reply-qr" in html

    def test_letter_still_renders_as_a_pdf(self):
        """WeasyPrint has to accept the inline SVG, not silently drop it.

        A unit test on the tag cannot catch a WeasyPrint-side rejection, and a
        dropped QR leaves a letter that looks perfectly fine.
        """
        from froide_fax.pdf_generator import FaxMessagePDFGenerator

        pdf = FaxMessagePDFGenerator(self._message(MessageKind.FAX)).get_pdf_bytes()
        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 5000, "suspiciously small; content may have been dropped"
