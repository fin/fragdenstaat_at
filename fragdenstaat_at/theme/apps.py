from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ThemeConfig(AppConfig):
    name = "fragdenstaat_at.theme"
    verbose_name = _("FragDenStaat")

    def ready(self):
        from froide.account.forms import user_extra_registry

        from .forms import SignupUserCheckExtra

        user_extra_registry.register("registration", SignupUserCheckExtra())
