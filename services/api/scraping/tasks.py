from celery import shared_task


@shared_task(name="scraping.ping")
def ping() -> str:
    return "pong"
