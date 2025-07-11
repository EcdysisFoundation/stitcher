import os
import cv2 as cv
from pathlib import Path

from . import constants
from .models import update_panorama_path
from .stitching import AffineStitcher
from .utils import get_image_strs

def stitch_imgs(extract_dir: Path):

    settings = {
        "crop": False,
        "confidence_threshold": 0.3
    }
    stitcher = AffineStitcher(**settings)
    img_paths = get_image_strs(extract_dir)
    panorama_path = os.path.join(
        extract_dir, constants.PANO_NAME_BASE + constants.PANO_SUFFIX)

    panorama = stitcher.stitch(img_paths)
    cv.imwrite(panorama_path, panorama)
    update_panorama_path(extract_dir, panorama_path)
