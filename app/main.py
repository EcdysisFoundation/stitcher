import zipfile
import os
import shutil
# import cv2 as cv

from fastapi import FastAPI, File, UploadFile
from .stitching import AffineStitcher

from . import constants
from .utils import get_image_paths


app = FastAPI()


@app.get("/")
def read_root():
    return {"message": "Welcome to Stitcher-FastAPI!"}



@app.post("/upload-zip-images/")
async def upload_zip_images(file: UploadFile = File(...)):
    if not file.filename.endswith(".zip"):
        return {"message": "Only ZIP files are allowed."}

    # Create a temporary path for the uploaded ZIP file
    zip_path = os.path.join(constants.MEDIA_DIRECTORY, file.filename)
    messages = {}

    # Save the uploaded ZIP file
    with open(zip_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Extract images from the ZIP file
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Create a subdirectory for the extracted images
            extract_dir = os.path.join(
                constants.MEDIA_DIRECTORY, 'myuniquedir') # os.path.splitext(file.filename)[0]
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

    settings = {# The dish should be considered
            "crop": False,
            "confidence_threshold": 0.3}

    stitcher = AffineStitcher(**settings)

    img_paths = get_image_paths(extract_dir)

    panorama = stitcher.stitch(img_paths)
    output = os.path.join(extract_dir, 'panorama.png')
    # cv.imwrite(output, panorama)


    messages.update({
        'extract_dir': extract_dir,
        'img_paths': img_paths
    })
    return messages

