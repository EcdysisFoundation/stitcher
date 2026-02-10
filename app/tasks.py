
import logging
import sys
import cv2 as cv
from pathlib import Path

from .celery_app import celery
# from .models import record_stitching_exception
from .stitching import AffineStitcher
from .utils import get_image_strs, load_resize_and_save_thumbnail


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Create a StreamHandler that outputs to sys.stdout
stream_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


@celery.task
def background_stitch_imgs(
        extract_dir: Path,
        conf: float,
        panorama_path,
        panorama_thumbnail_path):

    settings = {
        'crop': False,
        'confidence_threshold': conf,
        'blend_strength': 1
    }
    img_paths = get_image_strs(extract_dir)

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
                logger.info(e)
        except Exception as e:
            logger.info(e)
            # database entry disabled
            # creates sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) database is locked
            # when using Celery and SQLite
            # record_stitching_exception(extract_dir, str(e))
