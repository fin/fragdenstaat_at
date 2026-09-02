"""AT theme views.

DE's `index`, `glyphosat_download` and `meisterschaften_tippspiel` views are not
carried over: their features (the custom homepage, the glyphosat BfR download,
a 2020 prediction game) do not exist on AT. They were kept here commented out
for years; git history is the right place for them (D2).
"""

from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from fcdocs_annotate.annotation.views import AnnotateDocumentView

from froide.foirequest.decorators import allow_write_foirequest
from froide.foirequest.models import FoiEvent

EXTEND_DEADLINE_DELTA = timedelta(weeks=4)


class FDSAnnotationView(AnnotateDocumentView):
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(portal__isnull=True)


@require_POST
@allow_write_foirequest
def extend_deadline_four_weeks(request, foirequest):
    """Extend the request's deadline by a flat four weeks.

    froide's own ``extend_deadline`` takes a count of the law's response-time
    unit capped at 15 (days, for AT), so the requester cannot add a longer
    stretch in one go. This is a separate fixed-size action rendered from the
    ``foirequest_explain_deadline`` block (no froide change needed). Same
    permission gate froide uses -- ``allow_write_foirequest`` also resolves
    ``slug`` -> ``foirequest``; the overdue -> awaiting_response flip mirrors
    ``ExtendDeadlineForm.save()``.
    """
    if foirequest.due_date is None:
        return redirect(foirequest)
    foirequest.due_date = foirequest.due_date + EXTEND_DEADLINE_DELTA
    if foirequest.due_date > timezone.now() and foirequest.status == "overdue":
        foirequest.status = "awaiting_response"
    foirequest.save()
    FoiEvent.objects.create_event("deadline_extended", foirequest, user=request.user)
    messages.add_message(
        request, messages.INFO, _("Deadline has been extended by four weeks.")
    )
    return redirect(foirequest)


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
