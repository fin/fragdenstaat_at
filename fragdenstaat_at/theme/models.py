from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from django.core.mail import mail_managers
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils.translation import trans_real
from django.forms import Media

from parler import admin as parler_admin

from froide.foirequest.hooks import registry


orig_get_language_from_path = trans_real.get_language_from_path


def wrapping_get_language_from_path(*args, **kwargs):
    """
    Monkey patch
    If no language can be detected from path
    it means the default language should be used.
    The current method in Django doesn't support
    i18n_patterns prefix_default_language=False
    """
    result = orig_get_language_from_path(*args, **kwargs)
    if result is None:
        return settings.LANGUAGE_CODE
    return result


trans_real.get_language_from_path = wrapping_get_language_from_path

# Monkey patch reference to no longer existing .min.js files
parler_admin._language_prepopulated_media = parler_admin._language_media + Media(
    js=(
        "admin/js/urlify.js",
        "admin/js/prepopulate.js",
    )
)


def detect_troll_pre_request_creation(request, **kwargs):
    user = kwargs["user"]
    if user.trusted():
        return kwargs

    ip_address = request.META["REMOTE_ADDR"]
    cache_key = "froide:foirequest:request_per_ip:%s" % ip_address
    count = cache.get(cache_key, 0)
    if count == 0:
        cache.set(cache_key, 1)
    else:
        try:
            cache.incr(cache_key)
        except ValueError:
            pass
    count += 1

    if user.is_blocked:
        kwargs["blocked"] = True
        return kwargs

    now = timezone.now()
    diff = now - user.date_joined
    if diff < timedelta(days=1) and count > 10:
        user.is_blocked = True
        user.save()
        mail_managers(_("User auto blocked"), str(user.pk))
        kwargs["blocked"] = True

    return kwargs


registry.register("pre_request_creation", detect_troll_pre_request_creation)


# def inject_status_change(request, **kwargs):
#     data = kwargs['data']
#     foirequest = data['foirequest']
#     form = data['form']
#     data = form.cleaned_data
#     if data['resolution'] in ('successful', 'partially_successful'):
#         next_url = foirequest.get_absolute_url()
#         params = urlencode({'pk_keyword': next_url, 'pk_campaign': 'request-successful'})
#         return redirect('/spenden/erfolgreiche-anfrage/?' + params)

# Disable status change inject
# registry.register('post_status_set', inject_status_change)
