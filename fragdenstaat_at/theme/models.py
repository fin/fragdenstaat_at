from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.core.mail import mail_managers

# from django.shortcuts import redirect
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import trans_real

from froide.foirequest.hooks import registry
from froide.helper.email_sending import mail_registry

mail_registry.register("moderation/warn_user", ("user", "foirequest", "action_url"))

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


def detect_troll_pre_request_creation(request, **kwargs):
    user = kwargs["user"]
    data = kwargs["data"]
    if user.trusted():
        return data

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
        data["blocked"] = True
        return data

    now = timezone.now()
    diff = now - user.date_joined
    if diff < timedelta(days=1) and count > 10:
        user.is_blocked = True
        user.save()
        mail_managers(_("User auto blocked"), str(user.pk))
        data["blocked"] = True

    return data


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
