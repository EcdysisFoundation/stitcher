import datetime
import uuid
from typing import List, Optional
from pydantic import BaseModel, validate_call
from uuid import UUID
from pathlib import Path
from fastapi import HTTPException, status
from sqlmodel import (
    Field, Session, SQLModel, create_engine, select, JSON, Column, col, func
)
from sqlalchemy.exc import NoResultFound
from fastapi.encoders import jsonable_encoder


SQLITE_FILE_NAME = '/data/database.db'
SQLITE_URL = f'sqlite:///{SQLITE_FILE_NAME}'  # also stated in alembic.ini

CONNECT_ARGS = {'check_same_thread': False}
ENGINE = create_engine(SQLITE_URL, echo=True, connect_args=CONNECT_ARGS)


class UploadFileModelBase(SQLModel):
    guid: str | None = Field(default=None)
    extract_path: str | None = Field(default=None)
    upload_dir_name: str = Field(index=True)
    panorama_path: str | None = Field(default=None)
    panorama_width: int | None
    panorama_height: int | None
    panorama_confidence: float | None = Field(default=None)
    approved: bool | None = Field(default=None)
    predictions: List[dict] | None = Field(sa_column=Column(JSON))
    predictions_timestamp: datetime.datetime | None
    predictions_coco: List[dict] | None = Field(sa_column=Column(JSON))
    predictions_timestamp_coco: datetime.datetime | None
    sent_label_studio: str | None = Field(default=None)  # panorama_path when sent
    label_studio_project: str | None = Field(default=None)
    stitching_exception: str | None = Field(default=None)
    stitching_exception_at: datetime.datetime | None
    panorma_timestamp: datetime.datetime | None
    created_at: datetime.datetime | None
    annotations: List[dict] | None = Field(sa_column=Column(JSON))
    annotator: int | None
    annotations_updated_at: str | None
    annotations_segment: List[dict] | None = Field(sa_column=Column(JSON))
    annotator_segment: int | None
    annotations_updated_at_segment: str | None
    bugbox_sample_id: int | None
    bugbox_croped_saved: str | None


class UploadFileModel(UploadFileModelBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


def create_db_and_tables():
    SQLModel.metadata.create_all(ENGINE)


class UploadFileUpdate(BaseModel):
    approved: Optional[bool] = None
    upload_dir_name: str
    bugbox_sample_id: Optional[int] = None
    bugbox_croped_saved: Optional[str] = None


class UploadFileModelPublic(UploadFileModelBase):
    id: int


@validate_call
def update_upload_file_update(guid: UUID, upload_file: UploadFileUpdate):
    with Session(ENGINE) as session:
        statement = select(UploadFileModel).where(col(UploadFileModel.guid) == str(guid))
        try:
            rec = session.exec(statement).one()
        except NoResultFound:
            raise HTTPException(status_code=404, detail="Item not found")
        rec_data = upload_file.model_dump(exclude_unset=True)
        rec.sqlmodel_update(rec_data)
        session.add(rec)
        session.commit()
        session.refresh(rec)
        return rec


@validate_call
def create_upload_file(guid: UUID, extract_path: Path, upload_dir_name: str):
    rec = UploadFileModel(
        guid=str(guid),
        extract_path=str(extract_path),
        upload_dir_name=upload_dir_name,
        created_at=datetime.datetime.now(datetime.timezone.utc)
    )
    with Session(ENGINE) as session:
        session.add(rec)
        session.commit()


@validate_call
def get_panorama_path(extract_path: Path):
    with Session(ENGINE) as session:
        statement = select(UploadFileModel).where(UploadFileModel.extract_path == str(extract_path))
        results = session.exec(statement)
        if not results:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        rec = results.first()
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found")
        return rec.panorama_path


@validate_call
def update_panorama_path(extract_path: Path, panorama_path: Path, panorama_confidence: float):
    with Session(ENGINE) as session:
        statement = select(UploadFileModel).where(UploadFileModel.extract_path == str(extract_path))
        results = session.exec(statement)
        rec = results.first()
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found")
        rec.panorama_path = str(panorama_path)
        rec.panorama_confidence = panorama_confidence
        rec.panorma_timestamp = datetime.datetime.now(datetime.timezone.utc)
        # clear fields that are no longer valid
        rec.predictions = []
        rec.approved = None
        rec.predictions_timestamp = None
        rec.annotations = []
        rec.annotator = None
        rec.annotations_updated_at = None
        rec.sent_label_studio = None
        rec.label_studio_project = None
        rec.annotations_segment = None
        rec.annotator_segment = None
        rec.annotator_segment = None
        rec.annotations_updated_at_segment = None
        session.add(rec)
        session.commit()
        session.refresh(rec)


@validate_call
def record_stitching_exception(extract_path: Path, e: str):
    with Session(ENGINE) as session:
        statement = select(UploadFileModel).where(UploadFileModel.extract_path == str(extract_path))
        results = session.exec(statement)
        rec = results.first()
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found")
        rec.stitching_exception = e
        rec.stitching_exception_at = datetime.datetime.now(datetime.timezone.utc)
        session.add(rec)
        session.commit()
        session.refresh(rec)


@validate_call
def read_upload_files(offset: int, limit: int, approved: bool | None):
    with Session(ENGINE) as session:
        statement = select(UploadFileModel)
        if approved is not None:
            statement = statement.where(UploadFileModel.approved == approved)
        statement = statement.offset(offset).limit(limit)
        result = session.exec(statement).all()
        return result


@validate_call
def read_upload_file(guid: uuid.UUID):
    with Session(ENGINE) as session:
        statement = select(UploadFileModel).where(col(UploadFileModel.guid) == str(guid))
        try:
            return session.exec(statement).one()
        except NoResultFound:
            raise HTTPException(status_code=404, detail="Item not found")


@validate_call
def update_predictions_post(guid: uuid.UUID, predictions: List[dict]):
    with Session(ENGINE) as session:
        statement = select(UploadFileModel).where(UploadFileModel.guid == str(guid))
        results = session.exec(statement)
        rec = results.first()
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found")
        rec.predictions = jsonable_encoder(predictions)
        rec.predictions_timestamp = datetime.datetime.now(datetime.timezone.utc)
        session.add(rec)
        session.commit()
        session.refresh(rec)


@validate_call
def update_predictions_coco_post(guid: uuid.UUID, predictions_coco: List[dict]):
    with Session(ENGINE) as session:
        statement = select(UploadFileModel).where(UploadFileModel.guid == str(guid))
        results = session.exec(statement)
        rec = results.first()
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found")
        prediction_result = jsonable_encoder(predictions_coco)[0]
        rec.predictions_coco = prediction_result['predictions']
        rec.predictions_timestamp_coco = datetime.datetime.now(datetime.timezone.utc)
        rec.panorama_width = prediction_result['original_width']
        rec.panorama_height = prediction_result['original_height']
        session.add(rec)
        session.commit()
        session.refresh(rec)


@validate_call
def update_sent_label_studio(guid: uuid.UUID, project: str):
    with Session(ENGINE) as session:
        statement = select(UploadFileModel).where(UploadFileModel.guid == str(guid))
        results = session.exec(statement)
        rec = results.first()
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found")
        rec.sent_label_studio = rec.panorama_path
        rec.label_studio_project = project
        session.add(rec)
        session.commit()
        session.refresh(rec)


@validate_call
def delete_by_guid(guid: uuid.UUID):
    with Session(ENGINE) as session:
        statement = select(UploadFileModel).where(UploadFileModel.guid == str(guid))
        results = session.exec(statement)
        rec = results.first()
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found")
        session.delete(rec)
        session.commit()


@validate_call
def datatables_uploads(start: int, length: int, search: str, lsproject: str | None):
    with Session(ENGINE) as session:
        statement = select(UploadFileModel)
        count_statement = select(func.count()).select_from(UploadFileModel)
        records_total = session.exec(count_statement).one()
        if search:
            statement = statement.where(
                UploadFileModel.upload_dir_name.like(f"%{search}%") | UploadFileModel.guid.like(f"%{search}%"))
        if lsproject:
            statement = statement.where(UploadFileModel.label_studio_project.like(f"%{lsproject}%"))
        statement = statement.order_by(UploadFileModel.id.desc())
        rf = select(func.count()).select_from(statement)
        records_filtered = session.exec(rf).one()
        statement = statement.offset(start).limit(length)
        results = session.exec(statement).all()
        return {
            "recordsTotal": records_total,
            "recordsFiltered": records_filtered,
            "data": results
        }


@validate_call
def update_annotations_post(guid: uuid.UUID, annotations: List[dict] | None, annotator: int, updated_at: str):
    with Session(ENGINE) as session:
        statement = select(UploadFileModel).where(UploadFileModel.guid == str(guid))
        results = session.exec(statement)
        rec = results.first()
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found")
        if rec.bugbox_croped_saved:
            return False
        rec.annotations = jsonable_encoder(annotations)
        rec.annotator = annotator
        rec.annotations_updated_at = updated_at
        session.add(rec)
        session.commit()
        session.refresh(rec)
        return True


@validate_call
def update_annotations_segment_post(
        guid: uuid.UUID, annotations_segment: List[dict] | None, annotator_segment: int, updated_at: str):
    with Session(ENGINE) as session:
        statement = select(UploadFileModel).where(UploadFileModel.guid == str(guid))
        results = session.exec(statement)
        rec = results.first()
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found")
        if rec.bugbox_croped_saved:
            return False
        rec.annotations_segment = jsonable_encoder(annotations_segment)
        rec.annotator_segment = annotator_segment
        rec.annotations_updated_at_segment = updated_at
        session.add(rec)
        session.commit()
        session.refresh(rec)
        return True


def get_stats():
    with Session(ENGINE) as session:
        stats = {}
        ls_statement = select(
            UploadFileModel.label_studio_project,
            func.count(func.distinct(UploadFileModel.label_studio_project)).label(
                "distinct_ls_project_count")).where(
                UploadFileModel.label_studio_project is not None).group_by(UploadFileModel.label_studio_project)
        ls_results = session.exec(ls_statement).all()
        ls_results = [tuple(v) for v in ls_results if v[0]]
        stats.update({
            "label_studio_projects": ls_results if ls_results else None
        })
        return stats
