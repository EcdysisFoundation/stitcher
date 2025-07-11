
import cv2 as cv
from pathlib import Path

from .models import update_panorama_path
from .stitching import AffineStitcher
from .utils import get_image_strs, get_pano_path


def stitch_imgs(extract_dir: Path):

    settings = {
        "crop": False,
        "confidence_threshold": 0.3
    }
    panorama_path = get_pano_path(extract_dir)
    img_paths = get_image_strs(extract_dir)
    stitcher = AffineStitcher(**settings)
    panorama = stitcher.stitch(img_paths)
    cv.imwrite(panorama_path, panorama)
    update_panorama_path(extract_dir, panorama_path)
