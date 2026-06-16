import logging
import os

from huggingface_hub import hf_hub_download, login

from ai.models import DownloadStatus, HuggingFaceModel
from config import celery_app
from config.settings.base import LLAMA_MODEL_DIR

logger = logging.getLogger(__name__)


def _download_hf_model(hf_token, model_name, model_file):
    if hf_token:
        login(token=hf_token)
    hf_hub_download(repo_id=model_name, filename=model_file, local_dir=LLAMA_MODEL_DIR)


@celery_app.task()
def download_model(instance_id=None):
    logger.info("Download task started. instance_id=%s", instance_id)
    try:
        if instance_id is None:
            instance = HuggingFaceModel.objects.first()
            if not instance:
                logger.info("No HuggingFace model found. Creating default...")
                hf_token = os.getenv("HF_TOKEN", "")
                instance = HuggingFaceModel.objects.create(
                    name_model="hugging-quants/Llama-3.2-3B-Instruct-Q4_K_M-GGUF",
                    name_file="llama-3.2-3b-instruct-q4_k_m.gguf",
                    hf_token=hf_token,
                    download_status=DownloadStatus.DOWNLOADING,
                )
            else:
                instance.download_status = DownloadStatus.DOWNLOADING
                instance.save()
        else:
            instance = HuggingFaceModel.objects.get(pk=instance_id)
            instance.download_status = DownloadStatus.DOWNLOADING
            instance.save()

        logger.info("Downloading %s / %s...", instance.name_model, instance.name_file)
        _download_hf_model(instance.hf_token, instance.name_model, instance.name_file)
        instance.download_status = DownloadStatus.DOWNLOADED
        instance.save()
        logger.info("Download complete.")
    except Exception as e:
        logger.error("Download failed: %s", e, exc_info=True)
        instance = locals().get("instance")
        if instance:
            instance.download_status = DownloadStatus.ERROR
            instance.save()
