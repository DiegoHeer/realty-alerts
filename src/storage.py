import logging
from datetime import datetime

from peewee import CharField, Check, DateTimeField, Model, SqliteDatabase

from enums import QueryResultORMStatus
from models import QueryResult
from settings import DATA_PATH

LOGGER = logging.getLogger(__name__)

sqlite_db = SqliteDatabase(DATA_PATH / "sqlite.db", pragmas={"journal_mode": "wal"})


class QueryResultsORM(Model):
    detail_url = CharField()
    query_name = CharField()
    title = CharField()
    price = CharField()
    image_url = CharField()

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
        indexes = (("detail_url", "query_name"), True)


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
    if record := QueryResultsORM.get_or_none(
        QueryResultsORM.detail_url == query_result.detail_url,
        QueryResultsORM.query_name == query_result.query_name,
    ):
        if _is_query_result_changed(query_result, record):
            for key, value in query_result.model_dump().items():
                setattr(record, key, value)
            record.status = QueryResultORMStatus.UPDATED
            record.save()
    else:
        QueryResultsORM.create(**query_result.model_dump())


def _is_query_result_changed(query_result: QueryResult, record: QueryResultsORM) -> bool:
    for field in query_result.__class__.model_fields:
        if getattr(record, field) != getattr(query_result, field):
            return True
    return False


def get_new_query_results() -> list[QueryResult]:
    return list(QueryResultsORM.select().where(QueryResultsORM.status == QueryResultORMStatus.NEW))


def update_query_results_status(query_results: list[QueryResult], status: QueryResultORMStatus) -> None:
    for query_result in query_results:
        if record := QueryResultsORM.get_or_none(
            QueryResultsORM.detail_url == query_result.detail_url,
            QueryResultsORM.query_name == query_result.query_name,
        ):
            record.status = status
            record.save()
            LOGGER.info(f"Query result '{query_result.title}' has been updated to status '{status.value}'")
