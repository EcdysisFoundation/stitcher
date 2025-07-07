from pathlib import Path

from . import constants


def get_image_paths(dir):
    return [path for path in Path(dir).rglob(
        f'{constants.IMAGES_PREFIX}*')]
