from pathlib import Path

import yaml
from loguru import logger

from models import RealtyQuery


def load_queries(queries_dir: Path) -> list[RealtyQuery]:
    file_paths = [file_path for file_path in queries_dir.rglob("*.yml") if file_path.is_file()]
    file_paths.sort(key=lambda path: path.name)

    try:
        queries = [_get_query_from_file(file_path) for file_path in file_paths]
    except ValueError as exc:
        logger.error(exc)
        raise

    if not queries:
        exc_message = "There are no query files (in yml format) to be parsed. Please include one before continuing."
        raise FileNotFoundError(exc_message)

    return queries


def _get_query_from_file(file_path: Path) -> RealtyQuery:
    with open(file_path) as file:
        data = yaml.safe_load(file)

    return RealtyQuery.model_validate(data)
