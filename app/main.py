import cv2 as cv
import logging
import os
import shutil
import sys
import uuid
import zipfile
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, UploadFile
from fastapi.staticfiles import StaticFiles
from .stitching import AffineStitcher

from . import constants
from .utils import get_image_strs


app = FastAPI()

app.mount("/static", StaticFiles(directory=constants.MEDIA_PATH), name="static")


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Create a StreamHandler that outputs to sys.stdout
stream_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


def stitch_imgs(extract_dir: Path):

    settings = {# The dish should be considered
            "crop": False,
            "confidence_threshold": 0.3}

    stitcher = AffineStitcher(**settings)

    img_paths = get_image_strs(extract_dir)

    try:
        panorama = stitcher.stitch(img_paths)
        output = os.path.join(extract_dir, 'panorama.png')
        cv.imwrite(output, panorama)
        logger.info('cv.imwrite to file: {0}'.format(output))
    except Exception as e:
        logger.info(e)



@app.get("/")
def read_root():
    return {"message": "Welcome to Stitcher-FastAPI!"}


@app.post("/upload-zip-images/")
async def upload_zip_images(file: UploadFile, background_tasks: BackgroundTasks):
    if not file.filename.endswith(".zip"):
        return {"message": "Only ZIP files are allowed."}

    # Create a temporary path for the uploaded ZIP file
    zip_path = os.path.join(constants.MEDIA_PATH, file.filename)
    messages = {}

    # Save the uploaded ZIP file
    with open(zip_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Extract images from the ZIP file
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Create a subdirectory for the extracted images
            extract_dir = os.path.join(
                constants.MEDIA_PATH, str(uuid.uuid4())) # os.path.splitext(file.filename)[0]
            os.makedirs(extract_dir, exist_ok=True)
            zip_ref.extractall(extract_dir)

        # Remove the uploaded ZIP file after extraction
        os.remove(zip_path)

        messages.update({"zip_message": f"Images from {file.filename} extracted successfully to {extract_dir}"})
    except zipfile.BadZipFile:
        os.remove(zip_path) # Clean up invalid zip file
        return {"message": "Invalid ZIP file."}
    except Exception as e:
        os.remove(zip_path) # Clean up in case of other errors
        return {"message": f"An error occurred: {str(e)}"}

    background_tasks.add_task(stitch_imgs, extract_dir)

    messages.update({
        'extract_dir': extract_dir,
    })
    return messages

