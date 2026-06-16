from config import celery_app

from . import processing


@celery_app.task(bind=True)
def process_input(self, processing_id, start_action=None):
    processing.process_input(self, processing_id, start_action)
