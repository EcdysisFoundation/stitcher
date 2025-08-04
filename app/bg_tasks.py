
import logging
import sys
import cv2 as cv
from pathlib import Path
from pydantic import validate_call

from .models import update_panorama_path
from .stitching import AffineStitcher
from .utils import get_image_strs, get_pano_path


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Create a StreamHandler that outputs to sys.stdout
stream_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


@validate_call
def stitch_imgs(extract_dir: Path, conf: float):

    settings = {
        'crop': False,
        'confidence_threshold': conf
    }
    panorama_path = get_pano_path(extract_dir)
    img_paths = get_image_strs(extract_dir)
    if len(img_paths) > 1:
        stitcher = AffineStitcher(**settings)

        try:
            panorama = stitcher.stitch(img_paths)
            cv.imwrite(panorama_path, panorama)
            update_panorama_path(extract_dir, panorama_path)
        except Exception as e:
            logger.info(e)
