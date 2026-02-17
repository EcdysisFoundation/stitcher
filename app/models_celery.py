import datetime
import os
from typing import Optional
from sqlmodel import SQLModel, create_engine, Session, Field

"""
These models are for Celery usage only for writing, while FastAPI can read them.
These models are not registered with Alembic.
"""

CELERY_DB_URL = os.getenv('CELERY_DB_URL_URL', '')

CELERY_DB_ENGINE = create_engine(
    CELERY_DB_URL,
    connect_args={"check_same_thread": False},  # for threaded worker, still 1 process
    echo=False,
)

CELERY_DB_READ_ENGINE = create_engine(
    CELERY_DB_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)


def create_celery_db_and_tables():
    SQLModel.metadata.create_all(
        CELERY_DB_ENGINE,
        tables=[CeleryTask.__table__])


def get_celery_session() -> Session:
    return Session(CELERY_DB_ENGINE)


# use seperate session for read operations from FastAPI
def get_celery_read_session() -> Session:
    return Session(CELERY_DB_READ_ENGINE)


class CeleryTask(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    upload_file_guid: str
    panorama_path: str
    starting_timestamp: datetime.datetime
    exception: str | None
    finishing_timestamp: datetime.datetime | None
