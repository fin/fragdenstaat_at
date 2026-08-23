# TODO: a QR code of the reply address on outgoing faxes

Status: **not started.** This is a design note, not a record of work done.

## Why

Some Austrian authorities refuse electronic requests, so those requests go out
by fax instead of email. That routing lives in `froide-fax` on the
`feat/publicbody-fax-routing` branch ("Mode B": the fax replaces the email
rather than accompanying it).

froide's inbound path is email-only. `ReceiveEmailService` matches replies on
`foirequest.secret_address`, so if the authority replies by email to the address
printed on the letter, everything downstream works unchanged and no new receive
machinery is needed.

The obstacle is transcription. `secret_address` is machine-generated, and the
official reading it is reading a **fax** — 204x98 dpi, halftoned, often a
photocopy of a printout. Retyping it by hand is where the reply gets lost.

A QR code removes that step. The prize is real: it is the difference between
froide threading the reply automatically and somebody scanning paper.

Treat it as an experiment, not an obvious win. An office that refuses email may
not scan QR codes either. It costs little to try and should be measured.

## Constraint: `froide-fax` must not change

froide-fax is MIT and headed upstream to okfde. Nothing here should add a
dependency or a feature flag to it. Everything below lives in this repository,
and froide-fax gets a zero-line diff.

This is possible because Django's `{% extends %}` passes the origin history to
the template loader: **a template can extend the template it overrides**, and
resolution continues to the next match instead of recursing. Verified against
this checkout's Django 5.2, not assumed.

The same pattern is already used here for another froide plugin --
`fragdenstaat_at/fds_donation/templates/froide_payment/` -- so it is house
style, not a novelty.

## Steps

### 1. Add the QR library

Add to `dependencies` in `pyproject.toml`:

```
"segno>=1.6",
```

Prefer `segno` over `qrcode`: it is pure Python, needs no Pillow, and emits SVG.

> `qrcode` 7.3.1 already resolves in the environment, but only because
> **django-mfa3** requires it. Nothing declares it directly. Do not rely on it
> — it disappears the day froide changes MFA library.

### 2. Add a template tag

`fragdenstaat_at/theme/templatetags/fds_tags.py` already exists; add there, or
a new module beside it.

```python
import io

from django import template
from django.utils.safestring import mark_safe

import segno

register = template.Library()


@register.simple_tag
def fax_qr_code(payload):
    """Inline SVG QR code, sized to survive fax transmission."""
    buf = io.BytesIO()
    segno.make(payload, error="q").save(
        buf, kind="svg", scale=6, border=4, svgclass=None, xmldecl=False
    )
    return mark_safe(buf.getvalue().decode())
```

Inline SVG, not a PNG data URL: it stays vector through WeasyPrint, and sharp
edges are exactly what survives a fax and what a small raster loses.

### 3. Override the letter template

Create `fragdenstaat_at/theme/templates/froide_fax/message_letter.html`:

```django
{% extends "froide_fax/message_letter.html" %}
{% load fds_tags %}

{% block from_address_links %}
    {{ block.super }}
    <div class="fax-qr">{% fax_qr_code object.sender_email %}</div>
{% endblock %}
```

Three things this gets right:

- `{{ block.super }}` keeps the printed address and short URL. The QR is
  **additive** — never a replacement. An unscannable code must degrade to
  today's letter, not to a dead end.
- Extending inherits froide-fax's own blocks (the `Via` line, the signature)
  without reimplementing them.
- `from_address_links` is a block froide-fax does **not** override. It already
  overrides `extra_meta` and `letter_closing`; staying off those means an
  upstream change to the signature markup cannot collide with this.

Confirm `fragdenstaat_at.theme` still precedes froide's apps in
`INSTALLED_APPS` (it is currently first) so this template wins.

## Fax resolution is the whole difficulty

Group 3 fax is 204x98 dpi standard, 204x196 fine, then halftoned and lossily
compressed. A QR that looks fine on screen can arrive as mush.

- **Size it generously.** 3-4 cm square. Not a 1 cm decoration.
- **Keep the payload short.** Every character adds modules, and smaller modules
  is precisely what fax destroys. Encode the bare address, or the short URL
  (`object.request.get_absolute_domain_short_url`). Do **not** build a
  `mailto:` with subject and body parameters.
- **Error correction Q or H.** Costs modules, buys damage tolerance. With a
  short payload it is affordable.
- **Vector.** See step 2.

Decide what to encode before building. `mailto:` opens a composer already
addressed, which is the smoother path if their client supports it; a bare
address is shorter and always readable by a human as a fallback.

## Verifying

Rendering a PDF locally proves only that it renders. It says nothing about the
thing that matters.

1. Generate a letter and eyeball it — see `froide-fax/README_LIVE_TESTS.md` for
   how to drive the PDF path, and `/workspaces/fds_at/example_fax.pdf` for what
   the letter looks like today.
2. **Send a real fax and scan the received page with a phone.** This is the
   only test that counts. Faxbeep (<https://faxbeep.com>) answers for free and
   returns the received image.
3. Repeat at *standard* resolution, not just fine. Assume the worst path.

## Do not

- Add the dependency or a flag to `froide-fax`. If this proves out on real
  faxes, propose it upstream then, with evidence, as a setting defaulting off
  plus an optional extra — not before.
- Remove the printed address in favour of the QR.
- Put the QR on Mode A faxes without thinking. There the fax accompanies an
  email that already carries the reply address, so it buys much less.

## Related

- `froide-fax/README_LIVE_TESTS.md` — capturing real Telnyx traffic
- `froide-fax/froide_fax/templates/froide_fax/message_letter.html` — the
  template being extended
- `froide/plan.md` — inbound replies stay email-only, which is what makes the
  reply address the thing worth optimising
- **Known bug, unrelated to this but visible on the same letter:** the `Via`
  line is hardcoded to "Fax and email" and is wrong for Mode B, where no email
  is sent. Fix belongs on `feat/publicbody-fax-routing` in froide-fax.
