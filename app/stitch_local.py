import os
import cv2 as cv
from stitching import AffineStitcher


def get_image_paths(img_prefix, img_directory):
    matching_files = []
    for filename in os.listdir(img_directory):
        if filename.startswith(img_prefix) and os.path.isfile(os.path.join(img_directory, filename)):
            matching_files.append(filename)
    matching_files = sorted(matching_files)
    return [img_directory + i for i in matching_files]


if __name__ == '__main__':
    """
    This is intended for testing directly in a conda environment
    Use libraries defined in environment.yml
    """

    img_dir_name = 'test1_works'
    panroma_filename = 'panorama_local.jpg'

    settings = {
        'crop': False,
        'confidence_threshold': 0.6,
        # 'blender_type': 'feather',
        'blend_strength': 1,  # 5 is default
        # 'finder': 'voronoi'
        # 'warper_type': 'plane'
    }

    current_directory = os.getcwd()
    img_directory = current_directory.replace(
        '/app', f'/local_files/{img_dir_name}/')
    imgs = get_image_paths('image_r', img_directory)

    cv.ocl.setUseOpenCL(False)

    # use with /stitching module
    stitcher = AffineStitcher(**settings)
    # use stitcher.stitch_verbose to generate images each stage
    panorama = stitcher.stitch_verbose(imgs, verbose_dir=img_directory)
    # panorama = stitcher.stitch(imgs)
    cv.imwrite(img_directory + panroma_filename, panorama)

    # Alternative: Use without /stitching module intervention
    # stitcher = cv.Stitcher.create(cv.Stitcher_SCANS)
    # stitcher.setPanoConfidenceThresh(0.5)
    # read_images = [cv.imread(i) for i in imgs]
    # print('images read...')
    # status, panorama = stitcher.stitch(read_images)

    # if status == cv.Stitcher_OK:
    #     cv.imwrite(img_directory + panroma_filename, panorama)
    # else:
    #     print("Image stitching failed with error code:", status)
