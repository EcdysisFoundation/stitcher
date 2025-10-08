import json
import logging
import os
import shutil
import sys
import time
import uuid
import zipfile
from typing import List


from fastapi import (
    BackgroundTasks,
    HTTPException, FastAPI,
    Query, UploadFile, Request, status
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_405_METHOD_NOT_ALLOWED

from . import constants
from .bg_tasks import background_stitch_imgs
from .models import (
    UploadFileModel,
    UploadFileUpdate,
    UploadFileModelPublic,
    create_upload_file,
    datatables_uploads,
    delete_by_guid,
    read_upload_files,
    read_upload_file,
    create_db_and_tables,
    update_annotations_post,
    update_sent_label_studio,
    update_predictions_post,
    update_upload_file_update)
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*']
)
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
    """
    Upload a zip file of images intended to be stitched together into a single panorama.
    Each image for the panorama should be prefixed with 'image_r', such as 'image_r1_c1'
    indicates the image in the position of the first row and column.
    Only the prefix, 'image_r' is used in the process. Other images and files may exist in the
    zip file but will not be attempted to be used unless they include this prefix.
    """
    allowed_types = [
        'application/zip', 'application/octet-stream',
        'application/x-zip', 'application/x-zip-compressed']
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Only {', '.join(allowed_types)} are allowed."
        )
    messages = {}
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
        os.remove(zip_path)  # Clean up invalid zip file
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Invalid zip file, zipfile.BadZipFile"
        )
    except Exception as e:
        os.remove(zip_path)  # Clean up in case of other errors
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Exception: {e}"
        )
    background_tasks.add_task(background_stitch_imgs, extract_path, confidence_threshold)
    return messages


@app.get("/list-upload-files/", response_model=list[UploadFileModelPublic])
def list_upload_files(
        offset: int = 0,
        limit: int = Query(default=10, le=100),
        approved: bool = Query(default=None)):
    """
    List the uploaded zip files and their related information.
    """
    records = read_upload_files(offset, limit, approved)
    return records


@app.get("/list-upload/", response_model=UploadFileModel)
async def list_upload_file(guid: uuid.UUID):
    return read_upload_file(guid)


@app.get("/uploads")
def index_datatables(request: Request, start: int, length: int = 10):
    params = request.query_params.get
    search = params("search[value]")
    results = datatables_uploads(start, length, search)
    results.update({'draw': params('draw')})
    return results


@app.post("/update-stitching/")
async def update_stitching(
    guid: uuid.UUID,
    background_tasks: BackgroundTasks,
    confidence_threshold: float = Query(
        default=constants.DEFAULT_CONFIDENCE_LEVEL, le=0.9, ge=0.1)):
    """
    Create a new panorama from an existing upload. This will clear any predictions on the previous panorama,
    if applicable. Changing the default confidence may be helpful if a previous stitching did not work well.
    """
    record = read_upload_file(guid)
    if record.approved is not None:
        HTTP_405_METHOD_NOT_ALLOWED
        raise HTTPException(
            status_code=HTTP_405_METHOD_NOT_ALLOWED,
            detail=f"Not Allowed: record.approved is set to {record.approved}"
        )
    extract_path = get_extract_path(guid)
    background_tasks.add_task(background_stitch_imgs, extract_path, confidence_threshold)
    return {'message': f'Stitching process started for: {guid} with confidence_threshold of {confidence_threshold}'}


@app.post("/update-predictions/")
async def update_predictions(guid: uuid.UUID, predictions: List[dict]):
    """
    After performing inference on the panorama, enter the predictions here.
    """
    update_predictions_post(guid, predictions)
    return {'message': f'Updated predictions for: {guid}'}


@app.post("/sent_label_studio/")
async def sent_label_studio(guid: uuid.UUID):
    """
    After sending the panoroma to label studio, use this endpoint to indicate the
    panorama version (panorama_path) sent to label studio by entering the guid
    of the record.
    """
    update_sent_label_studio(guid)
    return {'message': f'set sent_label_studio to true for {guid}'}


@app.delete("/delete/{guid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_guid(guid: uuid.UUID):
    delete_by_guid(guid)
    return {'message': f'delete record for {guid}'}


@app.patch("/update-record/{guid}")
def update_record(guid: uuid.UUID, upload_file: UploadFileUpdate):
    return update_upload_file_update(guid, upload_file)


@app.post("/upload-annotations/")
async def upload_annotations(file: UploadFile):
    """
    Upload a .json file of annotations from label-studio json-min export.
    If the record is already sent to BugBox with bugbox_croped_saved set it will be skipped.
    """
    allowed_types = ['application/json']
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Only {', '.join(allowed_types)} are allowed."
        )
    messages = {
        'guids_not_found': [],
        'errors': [],
        'updated_annotations': 0,
        'skipped_due_to_requirements': 0}
    temp_path = os.path.join(constants.MEDIA_PATH, file.filename)
    # save the file
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    # now open it
    with open(temp_path, 'r') as file:
        data = json.load(file)
        for d in data:
            guid = None
            annotations = None
            try:
                guid = d['meta']['guid']
                annotations = d['label']
                annotator = d['annotator']
                updated_at = d['updated_at']
            except Exception as e:
                messages['errors'].append(f'missing keys in record: {e}')
            if guid:
                try:
                    v = update_annotations_post(guid, annotations, annotator, updated_at)
                    if v:
                        messages['updated_annotations'] += 1
                    else:
                        messages['skipped_due_to_requirements'] += 1
                except HTTPException:
                    messages['guids_not_found'].append(guid)
    return messages
