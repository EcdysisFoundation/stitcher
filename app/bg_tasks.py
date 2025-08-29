
import asyncio
import logging
import sys
import cv2 as cv
from pathlib import Path
from pydantic import validate_call

from .models import update_panorama_path, record_stitching_exception
from .stitching import AffineStitcher
from .utils import get_image_strs, get_pano_path


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Create a StreamHandler that outputs to sys.stdout
stream_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

task_lock = asyncio.Lock()


@validate_call
async def background_stitch_imgs(extract_dir: Path, conf: float):
    async with task_lock:

        settings = {
            'crop': False,
            'confidence_threshold': conf,
            'blend_strength': 1
        }
        panorama_path = get_pano_path(extract_dir)
        img_paths = get_image_strs(extract_dir)

        if len(img_paths) > 1:
            cv.ocl.setUseOpenCL(False)
            stitcher = AffineStitcher(**settings)
            try:
                panorama = stitcher.stitch(img_paths)
                logger.info(f'writing panorma to {panorama_path}')
                cv.imwrite(panorama_path, panorama)
                update_panorama_path(extract_dir, panorama_path, conf)
            except Exception as e:
                logger.info(e)
                record_stitching_exception(extract_dir, str(e))
