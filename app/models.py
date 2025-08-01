import uuid
from typing import List
from pydantic import validate_call
from uuid import UUID
from pathlib import Path
from fastapi import HTTPException, status
from sqlmodel import (
    Field, Session, SQLModel, create_engine, select, JSON, Column, col
)
from fastapi.encoders import jsonable_encoder


SQLITE_FILE_NAME = '/data/database.db'
SQLITE_URL = f'sqlite:///{SQLITE_FILE_NAME}'  # also stated in alembic.ini

CONNECT_ARGS = {'check_same_thread': False}
ENGINE = create_engine(SQLITE_URL, echo=True, connect_args=CONNECT_ARGS)


class UploadFileModel(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    guid: str | None = Field(default=None)
    extract_path: str | None = Field(default=None)
    upload_dir_name: str = Field(index=True)
    panorama_path: str | None = Field(default=None)
    approved: bool | None = Field(default=None)
    predictions: List[dict] = Field(sa_column=Column(JSON))
    sent_label_studio: str | None = Field(default=None)  # panorama_path when sent


def create_db_and_tables():
    SQLModel.metadata.create_all(ENGINE)


@validate_call
def create_upload_file(guid: UUID, extract_path: Path, upload_dir_name: str):
    rec = UploadFileModel(
        guid=str(guid),
        extract_path=str(extract_path),
        upload_dir_name=upload_dir_name
    )
    with Session(ENGINE) as session:
        session.add(rec)
        session.commit()


@validate_call
def get_panorma_path(extract_path: Path):
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
def update_panorama_path(extract_path: Path, panorama_path: Path):
    with Session(ENGINE) as session:
        statement = select(UploadFileModel).where(UploadFileModel.extract_path == str(extract_path))
        results = session.exec(statement)
        rec = results.first()
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found")
        rec.panorama_path = str(panorama_path)
        if rec.predictions:
            # clear the predictions since they are no longer valid
            rec.predictions = []
        session.add(rec)
        session.commit()
        session.refresh(rec)


@validate_call
def read_upload_files(offset: int, limit: int, label_studio_filter: bool):
    with Session(ENGINE) as session:
        statement = select(UploadFileModel)
        if label_studio_filter:
            subquery = select(UploadFileModel.id).where(col(UploadFileModel.panorama_path) == col(UploadFileModel.sent_label_studio))
            statement = statement.where(UploadFileModel.id.not_in(subquery), UploadFileModel.panorama_path.is_not(None))
        statement = statement.offset(offset).limit(limit)
        result = session.exec(statement).all()
        return result


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
        session.add(rec)
        session.commit()
        session.refresh(rec)


@validate_call
def update_sent_label_studio(guid: uuid.UUID):
    with Session(ENGINE) as session:
        statement = select(UploadFileModel).where(UploadFileModel.guid == str(guid))
        results = session.exec(statement)
        rec = results.first()
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found")
        rec.sent_label_studio = rec.panorama_path
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
