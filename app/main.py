import logging
import os
import shutil
import sys
import uuid
import zipfile


from fastapi import BackgroundTasks, FastAPI, Query, UploadFile
from fastapi.staticfiles import StaticFiles


from . import constants
from .bg_tasks import stitch_imgs
from .models import (
    UploadFileModel, create_upload_file,
    read_upload_files, create_db_and_tables)



app = FastAPI()

app.mount("/static", StaticFiles(directory=constants.MEDIA_PATH), name="static")

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Create a StreamHandler that outputs to sys.stdout
stream_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


@app.get("/")
def read_root():
    return {"message": "Welcome to Stitcher-FastAPI!"}


@app.post("/upload-zip-images/")
async def upload_zip_images(file: UploadFile, background_tasks: BackgroundTasks):
    messages = {}
    if not file.filename.endswith(".zip"):
        return messages.update({"warning": "Only ZIP files are allowed."})

    # Create a temporary path for the uploaded ZIP file
    zip_path = os.path.join(constants.MEDIA_PATH, file.filename)

    # Save the uploaded ZIP file
    with open(zip_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Extract images from the ZIP file
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Create a subdirectory for the extracted images
            guid = str(uuid.uuid4())
            extract_path = os.path.join(
                constants.MEDIA_PATH, guid)
            upload_dir_name = os.path.splitext(file.filename)[0]
            os.makedirs(extract_path, exist_ok=True)
            zip_ref.extractall(extract_path)

        # Remove the uploaded ZIP file after extraction
        os.remove(zip_path)

        create_upload_file(guid, extract_path, upload_dir_name)

        messages.update({"zip_message": f"Images from {file.filename} extracted successfully to {extract_path}"})
    except zipfile.BadZipFile:
        os.remove(zip_path) # Clean up invalid zip file
        return messages.update({"error": "Invalid ZIP file."})
    except Exception as e:
        os.remove(zip_path) # Clean up in case of other errors
        return messages.update({"error": f"An error occurred: {str(e)}"})

    try:
        background_tasks.add_task(stitch_imgs, extract_path)
    except Exception as e:
        logger.info(e)

    messages.update({
        'extract_path': extract_path,
    })
    return messages


@app.get("/list-upload-files/", response_model=list[UploadFileModel])
def list_upload_files(offset: int = 0, limit: int = Query(default=100, le=100)):
    return read_upload_files(offset, limit)
