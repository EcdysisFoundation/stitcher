import os
from pathlib import Path
from pydantic import validate_call
from uuid import UUID

from . import constants
from .models import get_panorma_path


def get_image_paths(dir):
    """
    Get the images that have the prefix,
    and sort assuming fixed length numberic characters such as prefix_001.
    """
    return sorted([path for path in Path(dir).rglob(
        f'{constants.IMAGES_PREFIX}*')])


def get_image_strs(dir):
    return [str(v) for v in get_image_paths(dir)]


@validate_call
def get_extract_path(guid: UUID):
    return os.path.join(constants.MEDIA_PATH, str(guid))


def get_pano_path(extract_dir):

    panorama_path = get_panorma_path(extract_dir)
    if not panorama_path:
        new_filename = constants.PANO_NAME_BASE
    else:
        filename = os.path.splitext(os.path.basename(panorama_path))[0]
        if filename == constants.PANO_NAME_BASE:
            new_filename = constants.PANO_NAME_BASE + constants.PANO_NAME_SEPERATOR + \
                           '1'
        else:
            filenumber = int(filename.replace(constants.PANO_NAME_BASE + constants.PANO_NAME_SEPERATOR, ''))
            filenumber += 1
            new_filename = constants.PANO_NAME_BASE + constants.PANO_NAME_SEPERATOR + \
                           str(filenumber)

    return os.path.join(extract_dir, new_filename + constants.PANO_EXTENSION)
