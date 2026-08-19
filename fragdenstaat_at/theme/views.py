"""AT theme views.

DE's `index`, `glyphosat_download` and `meisterschaften_tippspiel` views are not
carried over: their features (the custom homepage, the glyphosat BfR download,
a 2020 prediction game) do not exist on AT. They were kept here commented out
for years; git history is the right place for them (D2).
"""

from fcdocs_annotate.annotation.views import AnnotateDocumentView


class FDSAnnotationView(AnnotateDocumentView):
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(portal__isnull=True)
