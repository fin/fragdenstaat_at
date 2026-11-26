"""Synthetic rehearsal of the hstore -> JSON move of Donor.attributes (P7.3).

No production data: every shape below was reconstructed from the code that
writes donor attributes (external.update_iban_on_donor before and after its
';'-join fix, utils.merge_donor_list's old_data), not copied from a database.
"""

from importlib import import_module

from django.db import connection
from django.db.migrations.executor import MigrationExecutor

import pytest

migration = import_module(
    "fragdenstaat_at.fds_donation.migrations.0051_move_donor_attributes"
)
convert_attributes = migration.convert_attributes

SHAPES = [
    # (hstore value, expected JSON value)
    pytest.param({}, {}, id="empty"),
    pytest.param(
        {"iban": "AT611904300234573201"}, {"iban": "AT611904300234573201"}, id="iban"
    ),
    pytest.param(
        {"ibans": "AT611904300234573201;DE89370400440532013000"},
        {"ibans": ["AT611904300234573201", "DE89370400440532013000"]},
        id="ibans-semicolon",
    ),
    pytest.param(
        {"ibans": "AT1;;AT1;"}, {"ibans": ["AT1"]}, id="ibans-semicolon-dupes-empties"
    ),
    pytest.param({"ibans": ""}, {"ibans": []}, id="ibans-empty-string"),
    pytest.param(
        {"ibans": "['AT611904300234573201', 'DE89370400440532013000']"},
        {"ibans": ["AT611904300234573201", "DE89370400440532013000"]},
        id="ibans-legacy-repr",
    ),
    pytest.param(
        # the doubling the old code produced: a repr()-ed list wrapped and
        # repr()-ed again on every save
        {"ibans": "[\"['AT1']\", 'AT2']"},
        {"ibans": ["AT1", "AT2"]},
        id="ibans-legacy-doubled",
    ),
    pytest.param(
        {"ibans": "[\"[\\\"['AT1']\\\", 'AT1']\", 'AT2']"},
        {"ibans": ["AT1", "AT2"]},
        id="ibans-legacy-tripled",
    ),
    pytest.param(
        {"ibans": "['AT1'"}, {"ibans": ["['AT1'"]}, id="ibans-broken-repr-kept"
    ),
    pytest.param(
        {"banktransfer_reference": "123456"},
        {"banktransfer_reference": "123456"},
        id="numeric-reference-stays-string",
    ),
    pytest.param(
        {"banktransfer_reference": "true"},
        {"banktransfer_reference": "true"},
        id="json-literal-stays-string",
    ),
    pytest.param(
        {"banktransfer_reference": "Spende O'Brien FDS ABC"},
        {"banktransfer_reference": "Spende O'Brien FDS ABC"},
        id="apostrophe",
    ),
    pytest.param(
        {"old_data": "[{'id': 12, 'email': 'a@example.org'}]"},
        {"old_data": [{"id": 12, "email": "a@example.org"}]},
        id="old-data-repr",
    ),
    pytest.param(
        {"old_data": "[{'id': 12, 'timestamp': datetime.datetime(2024, 1, 1)}]"},
        {"old_data": "[{'id': 12, 'timestamp': datetime.datetime(2024, 1, 1)}]"},
        id="unparsable-repr-kept-verbatim",
    ),
    pytest.param(
        {"note": "__import__('os').system('true')"},
        {"note": "__import__('os').system('true')"},
        id="code-is-never-evaluated",
    ),
]


@pytest.mark.parametrize("hstore,expected", SHAPES)
def test_convert_attributes(hstore, expected):
    assert convert_attributes(hstore) == expected


def test_convert_attributes_none():
    assert convert_attributes(None) == {}


def _migrate(target):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate([target])
    return executor.loader.project_state([target]).apps


@pytest.mark.django_db(transaction=True)
def test_migration_moves_every_shape():
    old_apps = _migrate(("fds_donation", "0050_donor_new_attributes"))
    OldDonor = old_apps.get_model("fds_donation", "Donor")

    created = []
    for i, param in enumerate(SHAPES):
        hstore, expected = param.values
        donor = OldDonor.objects.create(
            email=f"synthetic-{i}@example.org",
            attributes=hstore or None,
        )
        created.append((donor.pk, expected))
    null_donor = OldDonor.objects.create(
        email="synthetic-null@example.org", attributes=None
    )
    count_before = OldDonor.objects.count()

    new_apps = _migrate(("fds_donation", "0052_replace_attributes_with_new_attributes"))
    NewDonor = new_apps.get_model("fds_donation", "Donor")

    assert NewDonor.objects.count() == count_before
    for pk, expected in created:
        assert NewDonor.objects.get(pk=pk).attributes == expected
    assert NewDonor.objects.get(pk=null_donor.pk).attributes == {}
