from pydantic import BaseModel


class QueryResult(BaseModel):
    detail_url: str
    title: str
    price: str
    image_url: str
