from fastapi import APIRouter, Depends

from app.dependencies import verify_internal_api_key

router = APIRouter(dependencies=[Depends(verify_internal_api_key)], tags=["internal"])


# TODO: GET /scrape-runs/{website}/last-successful
# TODO: POST /scrape-runs/{website}/results
# TODO: GET /scrape-runs/active
