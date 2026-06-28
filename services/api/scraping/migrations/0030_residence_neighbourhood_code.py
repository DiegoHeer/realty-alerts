from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models
from django.db.migrations.operations.models import AddIndex


class AddIndexConcurrentlyIfPostgres(AddIndexConcurrently):
    """CREATE INDEX CONCURRENTLY on PostgreSQL (CI + prod); a plain CREATE INDEX
    everywhere else. The local/test default backend is SQLite, which has no
    CONCURRENTLY and rejects the kwarg, so fall back to the standard AddIndex."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == "postgresql":
            super().database_forwards(app_label, schema_editor, from_state, to_state)
        else:
            AddIndex.database_forwards(self, app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == "postgresql":
            super().database_backwards(app_label, schema_editor, from_state, to_state)
        else:
            AddIndex.database_backwards(self, app_label, schema_editor, from_state, to_state)


class Migration(migrations.Migration):
    # CREATE INDEX CONCURRENTLY cannot run inside a transaction, so the whole
    # migration is non-atomic. Nullable AddField is metadata-only on PostgreSQL.
    atomic = False

    dependencies = [
        ("scraping", "0029_residence_price_per_m2"),
    ]

    operations = [
        migrations.AddField(
            model_name="residence",
            name="neighbourhood_code",
            field=models.CharField(blank=True, max_length=12, null=True),
        ),
        AddIndexConcurrentlyIfPostgres(
            model_name="residence",
            index=models.Index(fields=["neighbourhood_code"], name="idx_res_neighbourhood_code"),
        ),
    ]
