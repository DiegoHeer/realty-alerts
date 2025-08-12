from celery import shared_task

# NOTE: Command to run -> celery -A core worker -B


@shared_task
def task() -> None:
    print("Hello World")
