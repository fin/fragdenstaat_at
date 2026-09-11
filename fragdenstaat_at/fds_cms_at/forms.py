from django import forms
from django.utils.translation import gettext_lazy as _

from .models import RSSFeedCMSPlugin


class RSSFeedPluginForm(forms.ModelForm):
    refresh_now = forms.BooleanField(
        label=_("Refresh feed now"),
        required=False,
        help_text=_(
            "Re-fetch the feed immediately when saving instead of waiting for "
            "the periodic refresh. The fetch runs while you save, so it may "
            "take a few seconds."
        ),
    )

    class Meta:
        model = RSSFeedCMSPlugin
        exclude = ()
