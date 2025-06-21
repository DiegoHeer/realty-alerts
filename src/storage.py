from datetime import datetime

from peewee import CharField, Check, DateTimeField, Model, SqliteDatabase

from enums import QueryResultORMStatus

sqlite_db = SqliteDatabase("db.sqlite", pragmas={"journal_mode": "wal"})


class QueryResultsORM(Model):
    url = CharField(unique=True)
    title = CharField()

    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    status = CharField(
        choices=QueryResultORMStatus.choices(),
        default=QueryResultORMStatus.NEW,
        constraints=[Check(f"status IN {tuple(QueryResultORMStatus.values())}")],
    )

    def save(self, *args, **kwargs):
        self.updated_at = datetime.now()
        return super().save(*args, **kwargs)

    class Meta:
        database = sqlite_db
        table_name = "query_results"


def setup_database() -> None:
    if not sqlite_db.get_tables():
        _create_database_tables()


def _create_database_tables() -> None:
    with sqlite_db:
        sqlite_db.create_tables([QueryResultsORM])

