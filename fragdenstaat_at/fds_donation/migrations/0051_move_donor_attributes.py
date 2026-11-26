# Copy Donor.attributes (hstore, str -> str) into new_attributes (JSON).
#
# AT-specific, NOT a port of DE's 0082. DE's version parses every value with
# json.loads(val.replace("'", '"')), a heuristic for DE's stringified Python
# lists, which would silently turn a numeric banktransfer_reference into an int
# and mangle values containing apostrophes. AT's shapes, from the code that has
# written them:
#
#   iban                    a plain string
#   ibans                   a ';'-joined string (external.update_iban_on_donor),
#                           or, from before that fix, a repr()-ed Python list,
#                           possibly nested ("doubled") by repeated re-saving
#   banktransfer_reference  a plain string, possibly all digits
#   old_data                a repr()-ed list of dicts (utils.merge_donor_list)
#
# Rules: ibans becomes a flat, de-duplicated list of strings. A value that is a
# repr()-ed list or dict is parsed with ast.literal_eval (literals only, never
# executes code). Everything else stays exactly the string it was.
import ast

from django.db import migrations


def _parse_literal(value):
    """Parse a repr()-ed list/dict; return None if it is not one."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or stripped[0] not in "[{":
        return None
    try:
        parsed = ast.literal_eval(stripped)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return None
    return parsed if isinstance(parsed, (list, dict)) else None


def _flatten_ibans(value, out):
    if value is None:
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _flatten_ibans(item, out)
        return
    value = str(value)
    parsed = _parse_literal(value)
    if parsed is not None:
        _flatten_ibans(parsed, out)
        return
    for part in value.split(";"):
        part = part.strip()
        if part and part not in out:
            out.append(part)


def convert_attributes(attributes):
    """hstore dict -> JSON-ready dict. Pure, so it can be tested directly."""
    if not attributes:
        return {}
    result = {}
    for key, value in attributes.items():
        if key == "ibans":
            ibans = []
            _flatten_ibans(value, ibans)
            result[key] = ibans
            continue
        parsed = _parse_literal(value)
        result[key] = parsed if parsed is not None else value
    return result


def move_donor_attributes(apps, schema_editor):
    Donor = apps.get_model("fds_donation", "Donor")
    donors = Donor.objects.filter(attributes__isnull=False).only("id", "attributes")
    for donor in donors.iterator(chunk_size=500):
        new_attributes = convert_attributes(donor.attributes)
        if new_attributes:
            Donor.objects.filter(id=donor.id).update(new_attributes=new_attributes)


class Migration(migrations.Migration):
    dependencies = [
        ("fds_donation", "0050_donor_new_attributes"),
    ]

    operations = [
        migrations.RunPython(move_donor_attributes, migrations.RunPython.noop),
    ]
