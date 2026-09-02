
import datetime
import logging
import sys
import cv2 as cv
from pathlib import Path
from sqlmodel import Session, select

from .celery_app import celery
from .constants import STITCHER_LABEL_IMG, STITCHER_LABEL_THUMB_IMG
from .models_celery import CeleryTask, get_celery_session
from .stitching import AffineStitcher
from .utils import get_image_strs, load_resize_and_save_thumbnail, get_panorama_history
from .models import ENGINE, UploadFileModel


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Create a StreamHandler that outputs to sys.stdout
stream_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


def label_resize_thumbnail(extract_dir: Path):
    existing_label = [path for path in Path(extract_dir).rglob(
        f'{STITCHER_LABEL_IMG}')]
    if not existing_label:
        return
    label_path = existing_label[0]
    thumb_path = str(label_path.with_name(label_path.stem + '_thumbnail' + label_path.suffix))
    try:
        load_resize_and_save_thumbnail(label_path, 600, thumb_path)
    except Exception as e:
        logger.info(e)


@celery.task()
def background_stitch_imgs(
        upload_file_guid: str,
        extract_dir: Path,
        conf: float,
        panorama_path,
        panorama_thumbnail_path):

    settings = {
        'crop': False,
        'confidence_threshold': conf,
        'blend_strength': 1
    }
    start_time = datetime.datetime.now(datetime.timezone.utc)
    exception = ''
    finishing_time = None

    img_paths = get_image_strs(extract_dir)

    label_thumb_existing = [path for path in Path(extract_dir).rglob(
        f'{STITCHER_LABEL_THUMB_IMG}')]
    if not label_thumb_existing:
        label_resize_thumbnail(extract_dir)

    if len(img_paths) > 1:
        cv.ocl.setUseOpenCL(False)
        stitcher = AffineStitcher(**settings)

        try:
            panorama = stitcher.stitch(img_paths)
            logger.info(f'writing panorma to {panorama_path}')
            cv.imwrite(panorama_path, panorama)
            try:
                load_resize_and_save_thumbnail(panorama_path, 600, panorama_thumbnail_path)
            except Exception as e:
                exception += str(e)
                logger.info(e)
            finishing_time = datetime.datetime.now(datetime.timezone.utc)
        except Exception as e:
            logger.info(e)
            exception += str(e)

    if exception and not finishing_time:
        finishing_time = datetime.datetime.now(datetime.timezone.utc)
    with get_celery_session() as session:
        job = CeleryTask(
            upload_file_guid=upload_file_guid,
            panorama_path=panorama_path,
            starting_timestamp=start_time,
            exception=exception,
            finishing_timestamp=finishing_time
        )
        session.add(job)
        session.commit()


@celery.task()
def create_label_thumbnail(extract_dir: Path):
    label_resize_thumbnail(extract_dir)


@celery.task()
def backpopulate_panorama_filenames(batch_size: int = 200):
    """
    Temporary task to populate new field. Can be removed after use
    """
    with Session(ENGINE) as session:
        # 1. Fetch ONLY id and panorama_path (ignores heavy JSON columns)
        statement = select(UploadFileModel.id, UploadFileModel.panorama_path).where(
            UploadFileModel.panorama_path.is_not(None)
        )
        rows = session.exec(statement).all()
        total = len(rows)
        print(f"Found {total} records to process.")

        # 2. Process and commit in batches
        for i in range(0, total, batch_size):
            batch = rows[i : i + batch_size]
            for record_id, pano_path in batch:
                history = get_panorama_history(pano_path)

                # Fetch individual record for update
                rec = session.get(UploadFileModel, record_id)
                if rec:
                    rec.panorama_filenames = history
                    session.add(rec)

            session.commit()
            print(f"Processed {min(i + batch_size, total)}/{total} records...")
