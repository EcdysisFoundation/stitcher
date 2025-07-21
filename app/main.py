import logging
import os
import shutil
import sys
import time
import uuid
import zipfile
from typing import List


from fastapi import BackgroundTasks, FastAPI, Query, UploadFile, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from . import constants
from .bg_tasks import stitch_imgs
from .models import (
    UploadFileModel, create_upload_file,
    read_upload_files, create_db_and_tables,
    update_predictions_post)
from .utils import get_extract_path


LOGGER = logging.getLogger(__name__)

stream_handler = logging.StreamHandler(sys.stdout)
LOGGER.addHandler(stream_handler)
LOGGER.setLevel(logging.DEBUG)


class LogRequestsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        LOGGER.info(f"Request: {request.method} {request.url.path} | Processed in {process_time:.4f} seconds | HEADERS: {request.headers} | Client.Host: {request.client.host} | Status: {response.status_code}")
        return response


app = FastAPI()
app.add_middleware(LogRequestsMiddleware)


app.mount("/static", StaticFiles(directory=constants.MEDIA_PATH), name="static")


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


@app.get("/")
def read_root():
    return {"message": "Welcome to Stitcher-FastAPI!"}


@app.post("/upload-zip-images/")
async def upload_zip_images(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    confidence_threshold: float = Query(default=constants.DEFAULT_CONFIDENCE_LEVEL, le=0.9, ge=0.1)):
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
            guid = uuid.uuid4()
            extract_path = get_extract_path(guid)
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

    background_tasks.add_task(stitch_imgs, extract_path, confidence_threshold)

    messages.update({
        'extract_path': extract_path,
    })
    return messages


@app.get("/list-upload-files/", response_model=list[UploadFileModel])
def list_upload_files(offset: int = 0, limit: int = Query(default=100, le=100)):
    return read_upload_files(offset, limit)


@app.post("/update-stitching/")
async def update_stitching(
    guid: uuid.UUID,
    background_tasks: BackgroundTasks,
    confidence_threshold: float = Query(default=constants.DEFAULT_CONFIDENCE_LEVEL, le=0.9, ge=0.1)):
        extract_path = get_extract_path(guid)
        background_tasks.add_task(stitch_imgs, extract_path, confidence_threshold)
        return {'message': f'Stitching process started for: {guid}'}


@app.post("/update-predictions/")
async def update_predictions(guid: uuid.UUID, predictions: List[dict]):
    update_predictions_post(guid, predictions)
    return {'message': f'Updated predictions for: {guid}'}
