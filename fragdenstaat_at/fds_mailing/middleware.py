from datetime import timedelta

from django.utils import timezone

from froide.helper.email_sending import EmailContent

from fragdenstaat_at.fds_newsletter.utils import has_newsletter

from .models import ContinuousMailing, EmailTemplate


class EmailTemplateMiddleware:
    def get_email_content(self, mail_intent, context, template_base, email_kwargs):
        email_template = None
        intent = mail_intent
        if template_base is not None:
            try:
                email_template = EmailTemplate.objects.get(
                    active=True, mail_intent=template_base
                )
            except EmailTemplate.DoesNotExist:
                pass
        if email_template is None:
            try:
                email_template = EmailTemplate.objects.get(
                    active=True, mail_intent=intent
                )
            except EmailTemplate.DoesNotExist:
                return
        context = self._enhance_context(context)
        return email_template.get_email_content(context)

    def _enhance_context(self, context):
        if context.get("user"):
            user = context["user"]
            context["has_newsletter"] = has_newsletter(user)

        return context

    def send_mail(
        self,
        mail_intent: str,
        email_content: EmailContent,
        email_address,
        context: dict,
        email_kwargs: dict,
    ):
        try:
            mailing = ContinuousMailing.objects.get(
                email_template__active=True,
                email_template__mail_intent=mail_intent,
                ready=True,
            )
        except ContinuousMailing.DoesNotExist:
            return

        message = mailing.create_message(email_address, context=context)

        # this generates email content a second time but with a different context
        # FIXME: don't generate email content twice
        return message.send(mailing_context=context)


CLASSIFICATION_REMINDER_INTENT = "foirequest/emails/classification_reminder"
# Weekly reminders while the last message is younger than this ...
CLASSIFICATION_REMINDER_MAX_AGE = timedelta(days=30)
# ... then exactly one final reminder: the task runs weekly, so a 7-day window
# contains exactly one run.
CLASSIFICATION_REMINDER_FINAL_AGE = timedelta(days=60)
CLASSIFICATION_REMINDER_FINAL_WINDOW = timedelta(days=7)


def should_send_classification_reminder(last_message, now=None):
    if now is None:
        now = timezone.now()
    age = now - last_message
    if age < CLASSIFICATION_REMINDER_MAX_AGE:
        return True
    final_start = CLASSIFICATION_REMINDER_FINAL_AGE
    return final_start <= age < final_start + CLASSIFICATION_REMINDER_FINAL_WINDOW


class StaleClassificationReminderMiddleware:
    """Limit froide's weekly "please classify" reminder.

    froide's ``get_unclassified()`` has only a lower age bound, so a request
    left in ``awaiting_classification`` gets the reminder every Saturday
    forever. Here it is sent weekly for the first 30 days after the last
    message, then once more around day 60, then never. The bound is applied
    here rather than to that queryset because the moderation queue
    (``get_unclassified_for_moderation``) reuses it.
    """

    def should_mail(self, mail_intent, context, email_kwargs):
        if mail_intent != CLASSIFICATION_REMINDER_INTENT:
            return None
        foirequest = context.get("foirequest")
        if foirequest is None or foirequest.last_message is None:
            return None
        if not should_send_classification_reminder(foirequest.last_message):
            return False
        return None
