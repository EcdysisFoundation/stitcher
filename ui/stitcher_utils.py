import cv2
import numpy as np
from contextlib import closing
from io import BytesIO
from pathlib import Path
from PIL import Image
from uuid import uuid4

from django.conf import settings
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from bugbox3.samples.models import Specimen, SpecimenImage


def crop_and_save_images(image, bounding_boxes):
    """
    Crops images based on a list of bounding boxes and saves them to a directory.
    """
    result = []

    # avoid DecompressionBombError
    original_max_pixels = Image.MAX_IMAGE_PIXELS  # save to reset it later
    if not original_max_pixels:
        raise ValueError('MAX_IMAGE_PIXELS was not set')
    Image.MAX_IMAGE_PIXELS = None

    image_types = {
        'jpg': 'JPEG',
        'jpeg': 'JPEG',
        'png': 'PNG',
    }
    supported_extension = [v for v in image_types.keys()]
    img_suffix = Path(image.file.name).name.split(".")[-1]
    img_basename = Path(image.file.name).name.split(".")[:-1]

    with Image.open(image) as img:
        if img_suffix.lower() in supported_extension:
            img_format = image_types[img_suffix.lower()]
        else:
            return result

        for i, bbox in enumerate(bounding_boxes):
            try:
                x_min, y_min, x_max, y_max = map(int, bbox)
                img_width, img_height = img.size
                x_min = max(0, x_min)
                y_min = max(0, y_min)
                x_max = min(img_width, x_max)
                y_max = min(img_height, y_max)

                cropped_image = img.crop((x_min, y_min, x_max, y_max))
                output_filename = f"{img_basename}_crop_{i}.{img_suffix}"
                buffer = BytesIO()
                cropped_image.save(buffer, format=img_format)
                file_object = File(buffer, name=output_filename)
                result.append((file_object, i))
            except (ValueError, IndexError) as e:
                print(f"Skipping invalid bounding box {bbox}: {e}")
    Image.MAX_IMAGE_PIXELS = original_max_pixels
    return result


def convert_coco_bbox_to_pil(bbox):
    # convert coco formatted bounding box to PIL format
    x, y, width, height = bbox
    x_min = x
    y_min = y
    x_max = x + width
    y_max = y + height
    return (x_min, y_min, x_max, y_max)


def convert_ls_to_coco_to_pil(bbox, image_width, image_height):
    # undo format_result_label_studio() formatted boundingbox
    x, y, width, height = bbox
    x = x / 100 * image_width
    y = y / 100 * image_height
    width = width / 100 * image_width
    height = height / 100 * image_height
    return convert_coco_bbox_to_pil((x, y, width, height))


def crop_img_to_annotations(image, anno):
    if not default_storage.exists(image.name):
        return None
    static_bboxes = [
        convert_ls_to_coco_to_pil(
            (v['x'], v['y'], v['width'], v['height']),
            v['original_width'],
            v['original_height']) for v in anno
    ]
    bytes_imgs = crop_and_save_images(image, static_bboxes)
    return bytes_imgs


def create_segmentation(
    label, segmentation, image_height, image_width
):
    """
    FROM: https://github.com/HumanSignal/label-studio-sdk/blob/master/src/label_studio_sdk/converter/imports/coco.py#L78C5-L78C24
    Convert COCO segmentation annotation to Label Studio polygon format.

    COCO segmentation format: flat array of [x1,y1,x2,y2,...] coordinates
    Label Studio format: array of [x,y] points as percentages

    Args:
        label (txt): label for object
        segmentation (list): Flat list of polygon coordinates [x1,y1,x2,y2,...]
        from_name (str): Control tag name from Label Studio labeling config
        image_height (int): Height of the source image in pixels
        image_width (int): Width of the source image in pixels
        to_name (str): Object name from Label Studio labeling config

    Returns:
        dict: Label Studio polygon annotation item
    """
    # Convert flat array [x1,y1,x2,y2,...] to array of points [[x1,y1],[x2,y2],...]
    points = [list(x) for x in zip(*[iter(segmentation)] * 2)]

    # Convert absolute coordinates to percentages
    for i in range(len(points)):
        points[i][0] = points[i][0] / image_width * 100.0
        points[i][1] = points[i][1] / image_height * 100.0

    item = {
        "id": uuid4().hex[0:10],
        "type": "polygonlabels",
        "value": {"points": points, "polygonlabels": [label]},
        "to_name": "image",
        "from_name": "label",
        "image_rotation": 0,
        "original_width": image_width,
        "original_height": image_height,
    }
    return item


def get_polygon_area(x, y):
    """
    From https://github.com/HumanSignal/label-studio-sdk/blob/master/src/label_studio_sdk/converter/utils.py
    https://en.wikipedia.org/wiki/Shoelace_formula

    """

    assert len(x) == len(y)
    return float(0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))))


def get_polygon_bounding_box(x, y):
    """
    From https://github.com/HumanSignal/label-studio-sdk/blob/master/src/label_studio_sdk/converter/utils.py
    """

    assert len(x) == len(y)
    x1, y1, x2, y2 = min(x), min(y), max(x), max(y)
    return [x1, y1, x2 - x1, y2 - y1]


def convert_ls_polygonlabels(
        points, width, height):
    """
    From https://github.com/HumanSignal/label-studio-sdk/blob/master/src/label_studio_sdk/converter/converter.py#L836
    """
    points_abs = [
        (x / 100 * width, y / 100 * height) for x, y in points
    ]
    x, y = zip(*points_abs)

    return {
        'segmentation':
            [
                [coord for point in points_abs for coord in point]
            ],
        'bbox': get_polygon_bounding_box(x, y)
    }


def convert_coco_bbox_opencv(box):
    x, y, w, h = box
    x_start = int(x)
    y_start = int(y)
    x_end = int(x + w)
    y_end = int(y + h)
    return y_start, y_end, x_start, x_end


def crop_img_with_segmentation(
        image, annotations_segment, sample_instance, user_instance, uuid):
    if settings.ON_ECDYSIS_SERVER != 'YES':
        # high memory usage, do on local server
        print('Warning: function disabled when not ON_ECDYSIS_SERVER')
        return

    width = annotations_segment[0]['original_width']
    height = annotations_segment[0]['original_height']
    conv = [convert_ls_polygonlabels(
        v['points'],
        v['original_width'],
        v['original_height']) for v in annotations_segment]
    points = [v['segmentation'] for v in conv]
    bboxs = [v['bbox'] for v in conv]
    img_basename = Path(image.file.name).name.split(".")[:-1]

    mask = np.zeros((height, width), dtype=np.uint8)
    polys = [np.array(poly, dtype=np.int32).reshape(-1, 2) for poly in points]
    cv2.fillPoly(mask, polys, 255)  # all polygons in one call

    with closing(image.open()) as img:
        file_bytes = img.read()
        np_arr = np.frombuffer(file_bytes, np.uint8)
        np_arr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if np_arr.shape[2] == 3:
        np_arr = cv2.cvtColor(np_arr, cv2.COLOR_BGR2BGRA)

    np_arr[:, :, 3] = mask  # alpha = 255 inside polygon, 0 outside

    completed = 0
    # crop and save
    for i, box in enumerate(bboxs):
        y_start, y_end, x_start, x_end = convert_coco_bbox_opencv(box)
        cropped_img = np_arr[y_start:y_end, x_start:x_end]

        success, buffer = cv2.imencode(".png", cropped_img)
        if success:
            out_filename = f"{img_basename}_{i}.png"
            content = ContentFile(buffer.tobytes())
            content.name = out_filename
            specimen = Specimen.objects.create(
                sample=sample_instance,
                created_by_user=user_instance)
            SpecimenImage.objects.create(
                specimen=specimen,
                image=content,
                multispecimen_image_uuid=uuid,
                multispecimen_image_index=i,
                uploaded_by_user=user_instance
            )
            completed += 1
    if completed == len(bboxs):
        return True
    else:
        return False
