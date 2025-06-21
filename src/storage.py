from datetime import datetime

from peewee import CharField, Check, DateTimeField, Model, SqliteDatabase

from enums import QueryResultORMStatus
from models import QueryResult
from settings import DATA_PATH

sqlite_db = SqliteDatabase(DATA_PATH / "sqlite.db", pragmas={"journal_mode": "wal"})


class QueryResultsORM(Model):
    url = CharField(unique=True)
    title = CharField()

    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(null=True)
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


def save_query_results(query_results: list[QueryResult]) -> None:
    for query_result in query_results:
        _save_query_result_to_db(query_result)


def _save_query_result_to_db(query_result: QueryResult) -> None:
    if record := QueryResultsORM.get_or_none(QueryResultsORM.url == query_result.url):
        for key, value in query_result.model_dump().items():
            setattr(record, key, value)
        record.status = QueryResultORMStatus.UPDATED
        record.save()
    else:
        QueryResultsORM.create(**query_result.model_dump())


def get_new_query_results() -> list[QueryResult]:
    return list(QueryResultsORM.select().where(QueryResultsORM.status == QueryResultORMStatus.NEW))
