from fastapi import APIRouter

router = APIRouter(prefix="/listings", tags=["listings"])


# TODO: GET / (paginated, filtered), GET /{id}
