"""AT theme views.

DE's `index`, `glyphosat_download` and `meisterschaften_tippspiel` views are not
carried over: their features (the custom homepage, the glyphosat BfR download,
a 2020 prediction game) do not exist on AT. They were kept here commented out
for years; git history is the right place for them (D2).
"""

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404

from fcdocs_annotate.annotation.views import AnnotateDocumentView


class FDSAnnotationView(AnnotateDocumentView):
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(portal__isnull=True)


@staff_member_required
def fax_letter_debug(request, message_id=None, request_id=None):
    """TEMPORARY: render the fax letter as HTML, for iterating on its layout.

    `FaxMessagePDFGenerator` builds an HTML string and hands it to WeasyPrint;
    this returns that string so the reply-address QR code (and its effect on
    the floated `address#from` block) can be tweaked in a browser instead of
    regenerating a PDF each time. Browser layout is close to WeasyPrint's but
    not identical -- confirm the final result with `?pdf=1`.

      /fax-letter-debug/<message_id>/
      /fax-letter-debug/request/<request_id>/   (first outgoing message)

    DEBUG-only and staff-only; delete once the QR work in
    docs/qr-code-on-faxes.md is settled.
    """
    if not settings.DEBUG:
        raise Http404()

    from froide_fax.pdf_generator import FaxMessagePDFGenerator

    from froide.foirequest.models import FoiMessage, FoiRequest

    if request_id is not None:
        foirequest = get_object_or_404(FoiRequest, pk=request_id)
        message = next((m for m in foirequest.messages if not m.is_response), None)
        if message is None:
            raise Http404("Request has no outgoing message")
    else:
        message = get_object_or_404(FoiMessage, pk=message_id)

    generator = FaxMessagePDFGenerator(message)
    if request.GET.get("pdf"):
        return HttpResponse(generator.get_pdf_bytes(), content_type="application/pdf")
    return HttpResponse(
        generator.get_html_string(), content_type="text/html; charset=utf-8"
    )
