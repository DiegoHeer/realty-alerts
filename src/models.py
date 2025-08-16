from pydantic import BaseModel


class QueryResult(BaseModel):
    detail_url: str
    query_name: str
    title: str
    price: str
    image_url: str
