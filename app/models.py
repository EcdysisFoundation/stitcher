from pydantic import validate_call
from uuid import UUID
from pathlib import Path
from sqlmodel import Field, Session, SQLModel, create_engine, select


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


def get_panorma_path(extract_path):
    with Session(ENGINE) as session:
        statement = select(UploadFileModel).where(UploadFileModel.extract_path == extract_path)
        results = session.exec(statement)
        rec = results.one()
        return rec.panorama_path


def update_panorama_path(extract_path, panorama_path):
    with Session(ENGINE) as session:
        statement = select(UploadFileModel).where(UploadFileModel.extract_path == extract_path)
        results = session.exec(statement)
        rec = results.one()
        rec.panorama_path = panorama_path
        session.add(rec)
        session.commit()
        session.refresh(rec)


def read_upload_files(offset, limit):
    with Session(ENGINE) as session:
        recs = session.exec(select(UploadFileModel).offset(offset).limit(limit)).all()
        return recs
