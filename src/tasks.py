from pathlib import Path

from celery import Celery

from models import RealtyQuery
from queries import load_queries
from settings import CeleryConfig

queries_dir = Path(__file__).resolve().parents[1] / "queries"
realty_queries = load_queries(queries_dir)

app = Celery("tasks")
app.config_from_object(CeleryConfig(realty_queries))
app.autodiscover_tasks()


@app.task(pydantic=True)
def main(realty_query: RealtyQuery) -> None:
    print(f"Realty query: {realty_query.website}")
