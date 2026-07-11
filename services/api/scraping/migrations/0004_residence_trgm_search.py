"""Enable pg_trgm + GIN trigram indexes on Residence address fields.

Backs the fuzzy, ranked `/v1/residences/search` typeahead. Both operations are
PostgreSQL-only: `TrigramExtension` (a `CreateExtension` subclass) already no-ops
on other backends, and the index creation is vendor-guarded so the migration
still applies cleanly on the SQLite fallback used by plain `manage.py runserver`.
"""

from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations

# name -> Residence column. Plain CharFields, so column == field name; table is `residences`.
_TRGM_INDEXES = {
    "idx_res_street_trgm": "street",
    "idx_res_city_trgm": "city",
    "idx_res_postcode_trgm": "postcode",
    "idx_res_neighbourhood_trgm": "neighbourhood",
}


def _create_trgm_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for name, column in _TRGM_INDEXES.items():
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {name} ON residences USING gin ({column} gin_trgm_ops)")


def _drop_trgm_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for name in _TRGM_INDEXES:
            cursor.execute(f"DROP INDEX IF EXISTS {name}")


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0003_feedback"),
    ]

    operations = [
        TrigramExtension(),
        migrations.RunPython(_create_trgm_indexes, _drop_trgm_indexes),
    ]
