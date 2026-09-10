# The donation app is mounted in the urlconf instead: theme/urls.py includes
# fragdenstaat_at.fds_donation.urls under spenden/, which serves exactly the
# URLs this apphook would. fds_donation.urls has no root route, so an apphook
# page keeps rendering its own CMS content either way and only gains the child
# URLs beneath it -- attaching the apphook to the spenden/ page would produce
# byte-identical URLs.
#
# Registered but unattached, the apphook did nothing (no page sets
# application_urls). Attaching it would mount the namespace a second time,
# leaving reverse() to pick an instance, and would make donation URLs depend
# on CMS state: a celery worker rendering donation mail can only reverse them
# if the apphook page existed when the worker built its urlconf, since
# ApphookReloadMiddleware runs in the request cycle only and a worker's
# urlconf is frozen for the life of the process.
#
# DE mounts the app the other way round -- apphook only, no urlconf include --
# so keep this class in sync if that ever gets ported.
#
# from django.utils.translation import gettext_lazy as _
#
# from cms.app_base import CMSApp
# from cms.apphook_pool import apphook_pool
#
#
# @apphook_pool.register
# class FdsDonationApp(CMSApp):
#     name = _("FragDenStaat Donation Gift App")
#     app_name = "fds_donation"
#
#     def get_urls(self, page=None, language=None, **kwargs):
#         return ["fragdenstaat_at.fds_donation.urls"]
