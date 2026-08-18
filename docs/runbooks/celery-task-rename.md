# Runbook: renaming the `fragdenstaat_de.fds_donation.*` Celery tasks

## Background

`fragdenstaat_at/fds_donation/tasks.py` registers five Celery tasks whose
explicit `name=` still carries the old `fragdenstaat_de` package prefix.
The equivalent tasks in `fragdenstaat_at/theme/tasks.py` were already
renamed to the `fragdenstaat_at.*` prefix; these five were missed:

| Current name                                              | Target name                                              | Task function                  |
|-------------------------------------------------------------|-------------------------------------------------------------|---------------------------------|
| `fragdenstaat_de.fds_donation.new_donation`                | `fragdenstaat_at.fds_donation.new_donation`                | `send_donation_notification`   |
| `fragdenstaat_de.fds_donation.remind_unreceived_banktransfers` | `fragdenstaat_at.fds_donation.remind_unreceived_banktransfers` | `remind_unreceived_banktransfers` |
| `fragdenstaat_de.fds_donation.remove_old_donations`        | `fragdenstaat_at.fds_donation.remove_old_donations`        | `remove_old_donations`         |
| `fragdenstaat_de.fds_donation.send_jzwb`                   | `fragdenstaat_at.fds_donation.send_jzwb`                   | `send_jzwb_mailing_task`       |
| `fragdenstaat_de.fds_donation.backup_jzwb_pdf`             | `fragdenstaat_at.fds_donation.backup_jzwb_pdf`             | `backup_jzwb_pdf_task`         |

All in-repo callers invoke these via the decorated function object
(`send_donation_notification.delay(...)`, `backup_jzwb_pdf_task.delay(...)`,
etc.), never by the string name, so a rename does not require touching any
call site in this codebase. The risk is entirely at the broker/worker level.

## Why this is not a plain code edit

A Celery task's registered `name` is also its **routing key**: it is the
string a producer puts on the message and the string a worker uses to look
up which function to run. Simply changing the `name=` kwarg and deploying is
unsafe because:

- **In-flight messages are unroutable after the rename.** Anything already
  enqueued under the old name (e.g. `remind_unreceived_banktransfers`
  triggered on the 15th, or a `send_jzwb_mailing_task`/`backup_jzwb_pdf_task`
  queued from an admin action moments before deploy) will be picked up by a
  worker that, post-deploy, only knows the new name. Celery raises
  `NotRegistered` for that message and it is either lost or dead-lettered,
  depending on broker/ack configuration.
- **Workers and web processes deploy at different times.** During a rolling
  deploy there is a window where old-name workers and new-name workers (or
  an old-code web process still calling `.delay()` against an old
  task-object cached in a long-lived process) coexist. A hard rename makes
  that window lossy in both directions.
- **`remind_unreceived_banktransfers` and `remove_old_donations` look like
  scheduled/periodic tasks** (a beat schedule or a DB-backed
  `django_celery_beat.PeriodicTask` row referencing the task by name is the
  likely mechanism, though no such schedule is defined in this repo — it may
  be configured via the Celery Beat admin or infra config outside this
  checkout). If a periodic schedule entry still names the old task after the
  rename, that job silently stops firing instead of failing loudly.

## Safe sequence

1. **Register both names temporarily.** Keep the existing task function but
   have it (or a thin duplicate) respond to *both* the old and new name, e.g.
   by adding a second `@celery_app.task(name="fragdenstaat_at.fds_donation.<x>")`
   wrapper that calls the same implementation, or by using
   `celery_app.tasks[...]` aliasing. Deploy this first. At this point workers
   can process messages sent under either name.
2. **Switch producers to the new name where they matter**, i.e. re-point any
   `django_celery_beat.PeriodicTask` rows (or external cron/infra that
   enqueues these tasks by name) at `fragdenstaat_at.fds_donation.*`. In-repo
   `.delay()` callers are unaffected either way since they use the function
   object, but confirm whether any external system (admin scripts, other
   services) sends by string name.
3. **Drain the old name.** Watch broker/worker metrics (or `celery -A ...
   inspect active`/`reserved`, and the queue depth for the old routing key)
   until no more messages arrive under the old name and nothing is queued
   under it. For the periodic tasks this may mean waiting a full schedule
   cycle (a month, for the bank-transfer reminder) to be sure no stray
   message is still in flight.
4. **Remove the old name.** Once drained, delete the old-name registration
   (or the compatibility wrapper) and keep only
   `fragdenstaat_at.fds_donation.*`. Deploy.
5. **Verify** no `NotRegistered` errors appear in worker logs and that the
   periodic jobs (bank-transfer reminders, old-donation cleanup) still fire
   on schedule after step 4.

## Explicitly out of scope for this change

No code was modified as part of documenting this runbook — renaming a live
task name is an operational (drain-and-deploy) change, not a refactor, and
should be executed by whoever owns the Celery broker/worker deploy, following
the sequence above.
