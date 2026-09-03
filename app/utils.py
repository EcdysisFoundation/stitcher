import os
import cv2
from pathlib import Path
from pydantic import validate_call
from uuid import UUID

from . import constants


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


def get_pano_path(extract_dir, panorama_path_filenames):
    """
    Get the path for a new image, considering previous entries.
    If previous entries exist, the filename increments by one.
    """
    panorama_path, panorama_filenames = panorama_path_filenames
    if not panorama_path:
        new_filename = constants.PANO_NAME_BASE
    else:
        if not panorama_filenames:
            # entries have not been logged in panorama_filenames, so use current path
            last_entry = panorama_path
        else:
            # use last path in the history
            last_entry = panorama_filenames[-1]
        filename = os.path.splitext(os.path.basename(last_entry))[0]
        if filename == constants.PANO_NAME_BASE:
            new_filename = constants.PANO_NAME_BASE + constants.PANO_NAME_SEPERATOR + \
                           '1'
        else:
            filenumber = int(filename.replace(constants.PANO_NAME_BASE + constants.PANO_NAME_SEPERATOR, ''))
            filenumber += 1
            new_filename = constants.PANO_NAME_BASE + constants.PANO_NAME_SEPERATOR + \
                str(filenumber)

    return os.path.join(extract_dir, new_filename + constants.PANO_EXTENSION)


def load_resize_and_save_thumbnail(path, new_width, thumbnail_path):

    try:
        img = cv2.imread(path)
    except cv2.error as e:
        print(f"Error loading image: {e}")
        img = None
    if img is None:
        raise FileNotFoundError(f"Could not read image: {path}")

    # Resize, keeping aspect ratio, or skip
    h, w = img.shape[:2]
    if float(w) <= new_width:
        return
    scale = new_width / float(w)
    new_height = int(h * scale)
    resized = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
    success = cv2.imwrite(thumbnail_path, resized)
    if not success:
        raise IOError(f"Could not write image: {thumbnail_path}")
    return


def get_panorama_thumbnail_path(panorama_path: str):
    p = Path(panorama_path)
    return str(p.with_name(p.stem + '_thumbnail' + p.suffix))


def get_stitch_img_params(panorama_path, extract_path, confidence):
    """
    Returns the args for models.update_panorama_path when stitching images
    """
    thumb_path = get_panorama_thumbnail_path(panorama_path)
    return {
        'extract_path': extract_path,
        'panorama_path': panorama_path,
        'panorama_thumbnail_path': thumb_path,
        'panorama_confidence': confidence
    }


def get_panorama_history(panorama_path: str | None) -> list[str]:
    """
    Given a path like '.../panorama__2.jpg', returns:
    ['panorama.jpg', 'panorama__1.jpg', 'panorama__2.jpg']
    with the parent appended to the front of each.
    """
    if not panorama_path:
        return []

    dir_path = str(Path(panorama_path).parent)
    base = constants.PANO_NAME_BASE
    sep = constants.PANO_NAME_SEPERATOR
    ext = constants.PANO_EXTENSION
    filename_without_ext = os.path.splitext(os.path.basename(panorama_path))[0]

    # Base case: "panorama.jpg"
    if filename_without_ext == base:
        return [panorama_path]

    # Incremented case: "panorama__N.jpg"
    if filename_without_ext.startswith(base + sep):
        try:
            current_num = int(filename_without_ext.replace(base + sep, ""))
            history = [f"{base}{ext}"]
            for i in range(1, current_num + 1):
                history.append(f"{base}{sep}{i}{ext}")
            history = [f'{dir_path}/{v}' for v in history]
            return history
        except ValueError:
            pass

    # Fallback for unexpected format
    return [panorama_path]
