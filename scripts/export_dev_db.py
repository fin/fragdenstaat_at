#!/usr/bin/env python
"""
Privacy-preserving development database export for fragdenstaat.at.

Exports:
  - django_content_type, django_site
  - froide publicbody reference data (jurisdiction, foilaw, publicbody, categories)
  - django-cms page content (published versions only, usernames scrubbed)
  - djangocms-versioning (published versions only, user refs → dev user id=1)
  - djangocms-alias (published versions only)
  - All CMS plugin tables (filer image FKs nulled out)

All application tables are truncated in the dump. Tables not listed above are
exported empty (no rows). FK columns in exported rows that reference empty tables
are nulled out (e.g. filer image FKs in plugin tables, region_id in jurisdictions).

Usage (on the live server):
    DJANGO_SETTINGS_MODULE=fragdenstaat_at.settings.production \\
      DEV_DUMP_OUT=dev_dump.sql \\
      python manage.py shell -c "exec(open('scripts/export_dev_db.py').read())" \\
      2>export.log

    Prefer DEV_DUMP_OUT over redirecting stdout. Django prints during startup --
    before this script runs -- and that output would otherwise land in the .sql
    file as bare text, where psql merges it with the next statement and both
    fail. Redirecting stdout still works and is guarded, but the file path is
    the safe route.

Load into a dev database (no prior migration needed — schema is included):
    psql -h db -U fragdenstaat_at -d fragdenstaat_at -f dev_dump.sql

    The dump drops every table in the public schema first, so it is safe to load
    over an existing dev database. Afterwards run `manage.py migrate`: the schema
    is production's, which is normally behind this branch.
"""

import datetime
import decimal
import json
import os
import subprocess
import sys
import uuid

# ─── Django setup ─────────────────────────────────────────────────────────────
# When run via `manage.py shell -c "exec(...)"`, Django is already set up.
# For standalone use, configure DJANGO_SETTINGS_MODULE and call django.setup().
try:
    from django.db import connection
    connection.ensure_connection()
except Exception:
    import os

    import django
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE", "fragdenstaat_at.settings.production"
    )
    django.setup()
    from django.db import connection

ERR = sys.stderr

# Where the SQL goes.
#
# Writing the dump to stdout is fragile: under the documented invocation
# (`manage.py shell -c "exec(...)"`) Django is fully initialised -- and has
# already printed to stdout -- before the first line of this script runs, so the
# redirect below cannot catch it. djangocms-versioning emits "N objects could not
# be automatically imported" during app loading, which then lands at the top of
# the .sql file as bare text. psql accumulates input until the first ";", so that
# text merges with whatever statement follows and both fail together. That
# silently ate the "drop all existing tables" block in the 2026-06-14 export.
#
# Set DEV_DUMP_OUT to a path and the dump is written there instead, out of reach
# of anything that prints during startup. Stdout remains supported for
# compatibility, guarded below.
_OUT_PATH = os.environ.get("DEV_DUMP_OUT")
OUT = open(_OUT_PATH, "w", encoding="utf-8") if _OUT_PATH else sys.stdout

# Redirect sys.stdout → stderr so any Django/library code that prints directly
# *from here on* (e.g. djangocms-versioning auto-import messages) goes to the
# log, not the dump. Anything printed before this point is handled by the
# statement terminator written at the top of the SQL.
sys.stdout = sys.stderr


# ─── Value escaping ───────────────────────────────────────────────────────────

def pg_str(s: str) -> str:
    """Single-quote a string, escaping embedded quotes and backslashes."""
    return "'" + str(s).replace("'", "''") + "'"


def pg_escape(val, col: str = "", geom_cols: frozenset = frozenset(), json_cols: frozenset = frozenset()) -> str:
    """Convert a Python value to a safe PostgreSQL literal."""
    if val is None:
        return "NULL"
    if col in geom_cols:
        # val is already EWKT text from ST_AsEWKT() — wrap for re-import
        return f"ST_GeomFromEWKT({pg_str(val)})"
    if col in json_cols:
        # val is raw JSON text from the CAST("col" AS text) in SELECT —
        # pass it straight through; no Python serialisation roundtrip.
        return pg_str(val) + "::jsonb"
    if isinstance(val, (dict, list)):
        # fallback for non-jsonb columns that return Python containers
        return pg_str(json.dumps(val, default=str)) + "::jsonb"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        return repr(val)
    if isinstance(val, decimal.Decimal):
        return str(val)
    if isinstance(val, str):
        return pg_str(val)
    if isinstance(val, datetime.datetime):
        return pg_str(val.isoformat()) + "::timestamptz"
    if isinstance(val, datetime.date):
        return pg_str(val.isoformat()) + "::date"
    if isinstance(val, datetime.time):
        return pg_str(str(val)) + "::time"
    if isinstance(val, uuid.UUID):
        return pg_str(str(val))
    if isinstance(val, memoryview):
        return f"decode('{bytes(val).hex()}', 'hex')"
    if isinstance(val, bytes):
        return f"decode('{val.hex()}', 'hex')"
    return pg_str(str(val))


# ─── Table introspection ──────────────────────────────────────────────────────

_col_cache: dict = {}


def get_table_columns(cursor, table: str) -> tuple:
    """Return (ordered_col_names, geom_cols, json_cols) for a DB table."""
    if table in _col_cache:
        return _col_cache[table]
    cursor.execute(
        """
        SELECT column_name, udt_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        [table],
    )
    rows = cursor.fetchall()
    cols = [r[0] for r in rows]
    geom = frozenset(r[0] for r in rows if r[1] == "geometry")
    jsn = frozenset(r[0] for r in rows if r[1] in ("json", "jsonb"))
    _col_cache[table] = (cols, geom, jsn)
    return cols, geom, jsn


def table_exists(cursor, table: str) -> bool:
    cursor.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = %s
        """,
        [table],
    )
    return bool(cursor.fetchone())


def get_content_type_id(cursor, app_label: str, model: str) -> int | None:
    cursor.execute(
        "SELECT id FROM django_content_type WHERE app_label = %s AND model = %s",
        [app_label, model],
    )
    row = cursor.fetchone()
    return row[0] if row else None


# ─── Core export function ──────────────────────────────────────────────────────

def export_table(
    cursor,
    table: str,
    where: str = "",
    order_by: str = "id",
    overrides: dict | None = None,
    geom_cols: tuple = (),
    optional: bool = False,
) -> int:
    """
    Export rows from *table* as SQL INSERTs written to OUT.

    Args:
        where:     SQL WHERE clause (without 'WHERE'), e.g. "id IN (1, 2, 3)"
        order_by:  ORDER BY expression, default 'id'
        overrides: {col_name: sql_expression} replacing that column in the SELECT,
                   e.g. {'_created_by_id': 'NULL', 'created_by': "'dev'"}
        geom_cols: column names containing PostGIS geometry (auto ST_AsEWKT'd)
        optional:  the table genuinely may not exist, either because this
                   deployment does not install the app, or because the source
                   database has not applied the migration that creates it yet.
                   Anything else missing is a bug and raises.
    Returns:
        number of rows exported
    """
    if not table_exists(cursor, table):
        if not optional:
            # Do not skip quietly. A mistyped table name is indistinguishable
            # from an absent one, and the result is a dump that loads cleanly
            # while missing data -- exactly how the FoiLaw translations went
            # missing from the 2026-06-14 export.
            raise RuntimeError(
                f"export_table: table {table!r} does not exist. If that is "
                f"expected for this deployment, pass optional=True."
            )
        print(f"  SKIP {table} (not in source DB, optional)", file=ERR)
        # Also record it in the SQL. A silently absent table is invisible to
        # whoever loads the dump later; a comment makes it self-documenting.
        OUT.write(f"-- SKIPPED {table}: not present in the source database\n")
        return 0

    all_cols, tbl_geom_cols, tbl_json_cols = get_table_columns(cursor, table)
    if not all_cols:
        print(f"  SKIP {table} (no columns)", file=ERR)
        return 0

    overrides = overrides or {}
    geom_set = set(geom_cols) | tbl_geom_cols  # auto-detect geometry columns too

    # Build SELECT parts, applying overrides and geometry/json wrapping.
    # JSON/JSONB columns are cast to text so we get raw JSON bytes from
    # PostgreSQL and avoid any Python serialisation roundtrip that could
    # double-encode the value.
    select_parts = []
    for col in all_cols:
        if col in overrides:
            select_parts.append(f"{overrides[col]} AS \"{col}\"")
        elif col in geom_set:
            select_parts.append(f"ST_AsEWKT(\"{col}\") AS \"{col}\"")
        elif col in tbl_json_cols:
            select_parts.append(f'CAST("{col}" AS text) AS "{col}"')
        else:
            select_parts.append(f"\"{col}\"")

    sql = f'SELECT {", ".join(select_parts)} FROM "{table}"'
    if where:
        sql += f" WHERE {where}"
    if order_by:
        sql += f" ORDER BY {order_by}"

    cursor.execute(sql)
    rows = cursor.fetchall()

    if not rows:
        print(f"  {table}: 0 rows", file=ERR)
        return 0

    col_list = ", ".join(f'"{c}"' for c in all_cols)
    count = 0
    for row in rows:
        vals = ", ".join(
            pg_escape(v, col=col, geom_cols=geom_set, json_cols=tbl_json_cols)
            for col, v in zip(all_cols, row, strict=True)
        )
        OUT.write(f'INSERT INTO "{table}" ({col_list}) VALUES ({vals}) ON CONFLICT DO NOTHING;\n')
        count += 1

    print(f"  {table}: {count} rows", file=ERR)
    return count


# ─── FK detection for columns that must be NULLed in plugin tables ────────────

# Imported here rather than at the top of the file: Django has to be configured
# first (see the setup block above), so these cannot move up.
from django.contrib.auth import get_user_model as _get_user_model  # noqa: E402
from django.db.models import ForeignKey as _DjFKField  # noqa: E402

_FILER_DB_TABLES = {"filer_file", "filer_image", "filer_folder"}


def _user_db_table() -> str:
    return _get_user_model()._meta.db_table


def get_nulled_fk_attnames(model) -> set:
    """
    Return {attname, ...} for FK columns that must be set to NULL on export:
      - FKs to filer tables (files won't be present in dev)
      - FKs to the user model (real users are not exported)
    """
    user_table = _user_db_table()
    null_tables = _FILER_DB_TABLES | {user_table}
    cols: set = set()
    for field in model._meta.get_fields():
        if isinstance(field, _DjFKField) and field.related_model:
            if field.related_model._meta.db_table in null_tables and field.null:
                cols.add(field.attname)
    return cols


# Keep backward-compat name used elsewhere in the file
def get_filer_fk_attnames(model) -> set:
    return get_nulled_fk_attnames(model)


# ─── CMS helpers ──────────────────────────────────────────────────────────────

def get_published_object_ids(cursor, app_label: str, model: str) -> list:
    """Return object_ids of all published versions for a content type."""
    ct_id = get_content_type_id(cursor, app_label, model)
    if ct_id is None:
        return []
    cursor.execute(
        "SELECT object_id FROM djangocms_versioning_version "
        "WHERE content_type_id = %s AND state = 'published'",
        [ct_id],
    )
    return [row[0] for row in cursor.fetchall()]


def get_placeholder_ids_for_content(cursor, ct_id: int, object_ids: list) -> list:
    """Return placeholder IDs whose GenericFK source points to the given content objects."""
    if not object_ids or ct_id is None:
        return []
    ids_lit = ", ".join(str(i) for i in object_ids)
    cursor.execute(
        f'SELECT id FROM cms_placeholder '
        f'WHERE content_type_id = %s AND object_id IN ({ids_lit})',
        [ct_id],
    )
    return [row[0] for row in cursor.fetchall()]


def get_plugin_ids_in_placeholders(cursor, placeholder_ids: list) -> list:
    """Return all cms_cmsplugin IDs in the given placeholders."""
    if not placeholder_ids:
        return []
    ids_lit = ", ".join(str(i) for i in placeholder_ids)
    cursor.execute(f"SELECT id FROM cms_cmsplugin WHERE placeholder_id IN ({ids_lit})")
    return [row[0] for row in cursor.fetchall()]


# ─── Plugin model discovery ───────────────────────────────────────────────────

def get_plugin_type_map() -> dict:
    """Return {plugin_type_name: model_class} for all registered CMS plugins."""
    from cms.models import CMSPlugin
    from cms.plugin_pool import plugin_pool

    result: dict = {}
    for plugin_cls in plugin_pool.get_all_plugins():
        model = plugin_cls.model
        if model and model is not CMSPlugin:
            result[plugin_cls.__name__] = model
    return result


# ─── Main export ──────────────────────────────────────────────────────────────

def main() -> None:
    with connection.cursor() as cursor:

        # ── Pre-collect IDs for CMS filtering ────────────────────────────────
        print("Collecting published content IDs...", file=ERR)

        pub_pc_ids = get_published_object_ids(cursor, "cms", "pagecontent")
        pub_ac_ids = get_published_object_ids(cursor, "djangocms_alias", "aliascontent")

        pc_ct_id = get_content_type_id(cursor, "cms", "pagecontent")
        ac_ct_id = get_content_type_id(cursor, "djangocms_alias", "aliascontent")

        ph_page_ids = get_placeholder_ids_for_content(cursor, pc_ct_id, pub_pc_ids)
        ph_alias_ids = get_placeholder_ids_for_content(cursor, ac_ct_id, pub_ac_ids)

        # Static placeholders (footer, header, etc.) — include their public placeholder
        if table_exists(cursor, "cms_staticplaceholder"):
            cursor.execute(
                "SELECT id, public_id FROM cms_staticplaceholder WHERE public_id IS NOT NULL"
            )
            static_ph_rows = cursor.fetchall()  # [(sp_id, public_id), ...]
        else:
            static_ph_rows = []
        ph_static_ids = [row[1] for row in static_ph_rows]

        all_ph_ids = ph_page_ids + ph_alias_ids + ph_static_ids

        all_plugin_ids = get_plugin_ids_in_placeholders(cursor, all_ph_ids)

        # Discover which plugin model tables we'll need
        if all_plugin_ids:
            ids_lit = ", ".join(str(i) for i in all_plugin_ids)
            cursor.execute(
                f"SELECT DISTINCT plugin_type FROM cms_cmsplugin WHERE id IN ({ids_lit})"
            )
            published_plugin_types = {row[0] for row in cursor.fetchall()}
        else:
            published_plugin_types = set()

        plugin_type_map = get_plugin_type_map()

        # Versioning version IDs to export
        version_ids: list = []
        for ct_id, obj_ids in [
            (pc_ct_id, pub_pc_ids),
            (ac_ct_id, pub_ac_ids),
        ]:
            if ct_id and obj_ids:
                ids_lit = ", ".join(str(i) for i in obj_ids)
                cursor.execute(
                    f"SELECT id FROM djangocms_versioning_version "
                    f"WHERE content_type_id = {ct_id} AND object_id IN ({ids_lit}) "
                    f"AND state = 'published'"
                )
                version_ids.extend(row[0] for row in cursor.fetchall())

        print(f"  {len(pub_pc_ids)} published page contents", file=ERR)
        print(f"  {len(pub_ac_ids)} published alias contents", file=ERR)
        print(f"  {len(static_ph_rows)} static placeholders", file=ERR)
        print(f"  {len(all_ph_ids)} placeholders total", file=ERR)
        print(f"  {len(all_plugin_ids)} plugins across {len(published_plugin_types)} types", file=ERR)

        # ID literal helpers (used in WHERE clauses)
        pc_ids_lit = ", ".join(str(i) for i in pub_pc_ids) if pub_pc_ids else "NULL"
        ac_ids_lit = ", ".join(str(i) for i in pub_ac_ids) if pub_ac_ids else "NULL"
        ph_ids_lit = ", ".join(str(i) for i in all_ph_ids) if all_ph_ids else "NULL"
        plugin_ids_lit = ", ".join(str(i) for i in all_plugin_ids) if all_plugin_ids else "NULL"
        version_ids_lit = ", ".join(str(i) for i in version_ids) if version_ids else "NULL"

        # Export ALL pages to keep the full tree structure intact.
        # cms_page rows contain no PII (only tree metadata and template choices).
        cursor.execute("SELECT id FROM cms_page ORDER BY path")
        page_ids = [row[0] for row in cursor.fetchall()]
        page_ids_lit = ", ".join(str(i) for i in page_ids) if page_ids else "NULL"

        # ── Collect foilaw mediator_id mappings before we null them ───────────
        cursor.execute(
            "SELECT id, mediator_id FROM publicbody_foilaw WHERE mediator_id IS NOT NULL"
        )
        mediator_mappings = cursor.fetchall()

        # ── SQL header ────────────────────────────────────────────────────────
        if not _OUT_PATH:
            # Terminate anything that was printed to stdout before this script
            # got control (see the DEV_DUMP_OUT comment above). On a clean run
            # this is a harmless empty statement; on a noisy one it confines the
            # noise to its own failing statement instead of letting it swallow
            # the DROP block that follows.
            OUT.write(";\n")
        OUT.write("-- ============================================================\n")
        OUT.write("-- fragdenstaat.at privacy-preserving dev database export\n")
        OUT.write("-- Generated by export_dev_db.py\n")
        OUT.write("-- Load: psql -d fragdenstaat_dev < dev_dump.sql\n")
        OUT.write("-- ============================================================\n\n")
        # ── Drop all existing tables in the target database ───────────────────
        # Runs at load time against dev, before the schema is recreated, so it
        # works regardless of what migration state dev was previously at.
        OUT.write("-- Drop all existing tables (if any) so the schema below loads cleanly\n")
        OUT.write(
            "DO $$ DECLARE t text; BEGIN\n"
            "  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP\n"
            "    EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(t) || ' CASCADE';\n"
            "  END LOOP;\n"
            "END $$;\n\n"
        )

        # ── Schema dump (CREATE TABLE, indexes, sequences, etc.) ─────────────
        print("Dumping production schema via pg_dump...", file=ERR)
        from django.conf import settings as _settings
        _db = _settings.DATABASES["default"]
        _pg_env = {**os.environ}
        if _db.get("PASSWORD"):
            _pg_env["PGPASSWORD"] = _db["PASSWORD"]
        _pg_args = ["pg_dump", "--schema-only", "--no-owner", "--no-acl"]
        if _db.get("HOST"):
            _pg_args += ["-h", _db["HOST"]]
        if _db.get("PORT"):
            _pg_args += ["-p", str(_db["PORT"])]
        if _db.get("USER"):
            _pg_args += ["-U", _db["USER"]]
        _pg_args.append(_db["NAME"])
        _schema_sql = subprocess.check_output(_pg_args, env=_pg_env).decode()
        OUT.write(_schema_sql)
        OUT.write("\n")
        print("Schema dump done.", file=ERR)

        OUT.write("BEGIN;\n")
        OUT.write("SET session_replication_role = replica; -- disable FK triggers\n\n")

        # ── 1. Synthetic dev user ─────────────────────────────────────────────
        print("\nExporting prerequisites...", file=ERR)
        _user_table = _get_user_model()._meta.db_table
        OUT.write(f"-- ── Auth: synthetic dev user (id=1, table: {_user_table}) ───────────────\n")
        OUT.write(
            f'INSERT INTO "{_user_table}" '
            "(id, password, last_login, is_superuser, username, first_name, last_name, "
            "email, is_staff, is_active, date_joined, "
            "organization_name, organization_url, language, "
            "private, address, terms, profile_text, profile_photo, "
            "is_trusted, is_blocked, date_deactivated, is_deleted, date_left, notes) "
            "VALUES (1, '!', NULL, TRUE, 'dev', 'Dev', 'User', 'dev@localhost', "
            "TRUE, TRUE, NOW(), "
            "'', '', 'de', "
            "FALSE, '', TRUE, '', NULL, "
            "FALSE, FALSE, NULL, FALSE, NULL, '') "
            "ON CONFLICT DO NOTHING;\n\n"
        )

        # ── 2. Content types (needed for versioning GenericFKs) ───────────────
        OUT.write("-- ── Content types ──────────────────────────────────────────────────────\n")
        export_table(cursor, "django_content_type", order_by="id")

        # ── 3. Sites ──────────────────────────────────────────────────────────
        OUT.write("\n-- ── Sites ──────────────────────────────────────────────────────────────\n")
        export_table(cursor, "django_site", order_by="id")

        # ── 4. Migrations (tracks applied migrations / model versions) ─────────
        OUT.write("\n-- ── Applied migrations (for tracking database/model versions) ───────────\n")
        export_table(cursor, "django_migrations", order_by="id")

        # ── 5. PublicBody reference data ──────────────────────────────────────
        print("\nExporting publicbody data...", file=ERR)

        OUT.write("\n-- ── taggit Tag (used by various M2M filters in CMS plugins) ────────────\n")
        export_table(cursor, "taggit_tag", order_by="id")

        OUT.write("\n-- ── Campaigns (public campaigns, needed for donation form purpose list) ──\n")
        export_table(cursor, "froide_campaign_campaign", order_by="id", optional=True)

        OUT.write("\n-- ── Classification (MP_Node tree) ─────────────────────────────────────\n")
        export_table(cursor, "publicbody_classification", order_by="path")

        OUT.write("\n-- ── Category (MP_Node tree, TagBase) ──────────────────────────────────\n")
        export_table(cursor, "publicbody_category", order_by="path")

        OUT.write("\n-- ── Jurisdiction (region_id → NULL, GeoRegion not exported) ───────────\n")
        export_table(
            cursor,
            "publicbody_jurisdiction",
            order_by="id",
            overrides={"region_id": "NULL"},
        )

        OUT.write("\n-- ── FoiLaw (mediator_id → NULL initially, restored after publicbodies) ─\n")
        export_table(
            cursor,
            "publicbody_foilaw",
            order_by="id",
            overrides={"mediator_id": "NULL"},
        )

        OUT.write("\n-- ── FoiLaw translations (parler) ───────────────────────────────────────\n")
        # NB: "publicbody_foilaw_translation", not "publicbody_foilawtranslation".
        # froide overrides db_table on the parler translation model. The wrong name
        # silently exported nothing, so every FoiLaw arrived with no name,
        # description or letter templates and /anfrage-stellen/ died with
        # parler.models.DoesNotExist.
        export_table(cursor, "publicbody_foilaw_translation", order_by="id")

        OUT.write("\n-- ── FoiLaw combined (meta-law M2M self-ref) ───────────────────────────\n")
        export_table(cursor, "publicbody_foilaw_combined", order_by="id")

        OUT.write(
            "\n-- ── PublicBody (_created_by_id/_updated_by_id → NULL, "
            "geo kept as PostGIS point) ─\n"
        )
        export_table(
            cursor,
            "publicbody_publicbody",
            order_by="id",
            overrides={
                "_created_by_id": "NULL",
                "_updated_by_id": "NULL",
            },
            geom_cols=("geo",),
        )

        OUT.write("\n-- ── Restore foilaw.mediator_id after publicbodies are loaded ───────────\n")
        for law_id, mediator_id in mediator_mappings:
            OUT.write(
                f'UPDATE "publicbody_foilaw" SET mediator_id = {mediator_id} '
                f"WHERE id = {law_id};\n"
            )

        OUT.write("\n-- ── PublicBody ↔ FoiLaw (M2M) ─────────────────────────────────────────\n")
        export_table(cursor, "publicbody_publicbody_laws", order_by="id")

        OUT.write("\n-- ── PublicBody categories (M2M through CategorizedPublicBody) ──────────\n")
        export_table(cursor, "publicbody_categorizedpublicbody", order_by="id")

        OUT.write("\n-- ── PublicBody contacts (confirmed=True only, user_id → NULL) ──────────\n")
        export_table(
            cursor,
            "publicbody_publicbodycontact",
            where="confirmed = TRUE",
            order_by="id",
            overrides={"user_id": "NULL"},
            # Created by froide's publicbody migration 0052. Production is still
            # on 0050, so the table is absent there and this exports nothing --
            # which is correct, not an error. It starts producing rows once
            # production catches up.
            optional=True,
        )

        # ── 6. CMS pages and content ──────────────────────────────────────────
        print("\nExporting CMS data...", file=ERR)

        if not pub_pc_ids:
            print("  No published page content found — skipping CMS export", file=ERR)
        else:
            OUT.write("\n-- ── CMS Pages (full tree for hierarchy, username fields scrubbed) ─────\n")
            # cms_page is an MP_Node; export all pages reachable as ancestors
            # created_by / changed_by are CharField not FK → replace with 'dev'
            export_table(
                cursor,
                "cms_page",
                where=f"id IN ({page_ids_lit})",
                order_by="path",
                overrides={
                    "created_by": "'dev'",
                    "changed_by": "'dev'",
                },
            )

            OUT.write("\n-- ── CMS Page Extension (fds_cms, image_id → NULL) ──────────────────────\n")
            export_table(
                cursor,
                "fds_cms_fdspageextension",
                where=f"extended_object_id IN ({page_ids_lit})",
                order_by="extended_object_id",
                overrides={"image_id": "NULL"},
            )

            OUT.write("\n-- ── CMS PageUrl ────────────────────────────────────────────────────────\n")
            export_table(
                cursor,
                "cms_pageurl",
                where=f"page_id IN ({page_ids_lit})",
                order_by="id",
            )

            OUT.write("\n-- ── CMS PageContent (published versions only, usernames scrubbed) ──────\n")
            export_table(
                cursor,
                "cms_pagecontent",
                where=f"id IN ({pc_ids_lit})",
                order_by="id",
                overrides={
                    "created_by": "'dev'",
                    "changed_by": "'dev'",
                },
            )

        # ── 7. Static placeholders (footer, header, global blocks) ───────────
        if static_ph_rows:
            OUT.write("\n-- ── CMS Static placeholders (footer, header, etc.) ─────────────────────\n")
            # draft_id must be NOT NULL; point it to the same placeholder as public_id
            # so we only need one copy of the content in dev.
            for sp_id, public_id in static_ph_rows:
                cursor.execute(
                    "SELECT name, code, dirty, creation_method, site_id "
                    "FROM cms_staticplaceholder WHERE id = %s",
                    [sp_id],
                )
                row = cursor.fetchone()
                if row:
                    name, code, dirty, creation_method, site_id = row
                    site_val = str(site_id) if site_id is not None else "NULL"
                    OUT.write(
                        f'INSERT INTO "cms_staticplaceholder" '
                        f'(id, name, code, draft_id, public_id, dirty, creation_method, site_id) '
                        f'VALUES ({sp_id}, {pg_str(name)}, {pg_str(code)}, '
                        f'{public_id}, {public_id}, '
                        f'{"TRUE" if dirty else "FALSE"}, {pg_str(creation_method)}, {site_val}) '
                        f'ON CONFLICT DO NOTHING;\n'
                    )
            print(f"  cms_staticplaceholder: {len(static_ph_rows)} rows", file=ERR)

        # ── 8. Alias categories and aliases ───────────────────────────────────
        OUT.write("\n-- ── djangocms-alias: categories ────────────────────────────────────────\n")
        export_table(cursor, "djangocms_alias_category", order_by="id")

        OUT.write("\n-- ── djangocms-alias: aliases (groupers) ────────────────────────────────\n")
        export_table(cursor, "djangocms_alias_alias", order_by="id")

        OUT.write("\n-- ── djangocms-alias: alias content (published only) ────────────────────\n")
        if pub_ac_ids:
            export_table(
                cursor,
                "djangocms_alias_aliascontent",
                where=f"id IN ({ac_ids_lit})",
                order_by="id",
                overrides={
                    "created_by": "'dev'",
                    "changed_by": "'dev'",
                },
            )

        # ── 8. Placeholders and plugins ───────────────────────────────────────
        # DonationGift is referenced by DonationFormCMSPlugin via M2M; export
        # it before plugins so the M2M through rows have a valid target.
        OUT.write("\n-- ── DonationGift (referenced by DonationFormCMSPlugin M2M) ─────────────\n")
        export_table(cursor, "fds_donation_donationgift", order_by="id")

        if all_ph_ids:
            OUT.write("\n-- ── CMS Placeholders (for published page & alias content) ──────────────\n")
            export_table(
                cursor,
                "cms_placeholder",
                where=f"id IN ({ph_ids_lit})",
                order_by="id",
            )

            OUT.write("\n-- ── CMS Plugin base records ────────────────────────────────────────────\n")
            export_table(
                cursor,
                "cms_cmsplugin",
                where=f"id IN ({plugin_ids_lit})",
                order_by="id",
            )

            # ── Plugin-specific tables ─────────────────────────────────────────
            # Discover all plugin child tables from the DB: every CMS plugin that
            # uses multi-table inheritance has a cmsplugin_ptr_id column.
            # This is more robust than iterating plugin_type_map because it catches
            # any plugin whose registered class name doesn't match plugin_type_map.
            OUT.write("\n-- ── CMS Plugin data (one table per plugin type) ────────────────────────\n")
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND column_name = 'cmsplugin_ptr_id'
                ORDER BY table_name
                """
            )
            all_plugin_child_tables = [row[0] for row in cursor.fetchall()]

            # Reverse map db_table → model for FK nulling (filer, user refs)
            table_to_model = {m._meta.db_table: m for m in plugin_type_map.values()}

            for tbl in all_plugin_child_tables:
                model = table_to_model.get(tbl)
                null_cols = get_filer_fk_attnames(model) if model else set()
                overrides = dict.fromkeys(null_cols, "NULL")

                n = export_table(
                    cursor,
                    tbl,
                    where=f'"cmsplugin_ptr_id" IN ({plugin_ids_lit})',
                    order_by='"cmsplugin_ptr_id"',
                    overrides=overrides,
                )

                # Export auto-created M2M through tables for this plugin (e.g. tags)
                if model and n:
                    for field in model._meta.get_fields():
                        if (
                            hasattr(field, "many_to_many")
                            and field.many_to_many
                            and hasattr(field, "remote_field")
                            and field.remote_field
                        ):
                            try:
                                through = field.remote_field.through
                                if through._meta.auto_created:
                                    m2m_tbl = through._meta.db_table
                                    src_col = next(
                                        (
                                            f.attname
                                            for f in through._meta.get_fields()
                                            if hasattr(f, "related_model") and f.related_model == model
                                        ),
                                        None,
                                    )
                                    if src_col:
                                        export_table(
                                            cursor,
                                            m2m_tbl,
                                            where=f'"{src_col}" IN ({plugin_ids_lit})',
                                            order_by="id",
                                        )
                            except Exception as exc:
                                print(f"  WARNING: M2M through table for {tbl}: {exc}", file=ERR)

        # Note: djangocms_alias_aliasplugin is discovered and exported via the
        # plugin type loop above (plugin_type = 'AliasPlugin').

        # ── 9. Versioning ─────────────────────────────────────────────────────
        if version_ids:
            OUT.write(
                "\n-- ── djangocms-versioning: published versions "
                "(created_by → dev user, locked_by → NULL) ─\n"
            )
            export_table(
                cursor,
                "djangocms_versioning_version",
                where=f"id IN ({version_ids_lit})",
                order_by="id",
                overrides={
                    "created_by_id": "1",
                    "locked_by_id": "NULL",
                    "source_id": "NULL",  # source version may not be in export
                },
            )

            OUT.write(
                "\n-- ── djangocms-versioning: state tracking "
                "(published transitions only, user → dev user) ─\n"
            )
            export_table(
                cursor,
                "djangocms_versioning_versionstatetracking",
                where=f"version_id IN ({version_ids_lit})",
                order_by="id",
                overrides={"user_id": "1"},
                # Added by a later djangocms-versioning migration than production
                # has applied. Absent there, present once it catches up.
                optional=True,
            )

        # ── Footer ────────────────────────────────────────────────────────────
        # ── Reset sequences to max(id)+1 so future inserts don't collide ────────
        # pg_dump --schema-only resets sequences to their starting value (1), but
        # we insert rows with explicit production IDs. Without this, nextval() would
        # return IDs that already exist (e.g. when Django records new migrations).
        OUT.write("\n-- Reset all sequences to max existing value + 1\n")
        OUT.write(
            "DO $$\n"
            "DECLARE r RECORD;\n"
            "BEGIN\n"
            "  FOR r IN\n"
            "    SELECT\n"
            "      n.nspname AS schema_name,\n"
            "      s.relname AS seq_name,\n"
            "      a.attname AS col_name,\n"
            "      t.relname AS tbl_name\n"
            "    FROM pg_class s\n"
            "    JOIN pg_depend d\n"
            "      ON d.objid = s.oid\n"
            "      AND d.classid = 'pg_class'::regclass\n"
            "      AND d.refclassid = 'pg_class'::regclass\n"
            "    JOIN pg_class t ON t.oid = d.refobjid\n"
            "    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid\n"
            "    JOIN pg_namespace n ON n.oid = s.relnamespace\n"
            "    WHERE s.relkind = 'S' AND n.nspname = 'public'\n"
            "  LOOP\n"
            "    EXECUTE format(\n"
            "      'SELECT setval(%L, COALESCE(MAX(%I), 0) + 1, false) FROM %I.%I',\n"
            "      r.schema_name || '.' || r.seq_name,\n"
            "      r.col_name, r.schema_name, r.tbl_name\n"
            "    );\n"
            "  END LOOP;\n"
            "END $$;\n"
        )

        OUT.write("\nSET session_replication_role = DEFAULT;\n")
        OUT.write("COMMIT;\n")
        OUT.write("\n-- Refresh table statistics for the query planner\n")
        OUT.write("ANALYZE;\n")

        print("\nDone.", file=ERR)


main()

if _OUT_PATH:
    OUT.close()
    print(f"Wrote {_OUT_PATH}", file=ERR)
