from config import celery_app

from .sync_api import sync_issues_from_api, sync_journals_from_api


@celery_app.task()
def task_sync_journals_from_api(**kwargs):
    kwargs.pop("user_id", None)
    sync_journals_from_api(**kwargs)


@celery_app.task()
def task_sync_issues_from_api(**kwargs):
    kwargs.pop("user_id", None)
    sync_issues_from_api(**kwargs)
