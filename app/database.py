from sqlmodel import Field, SQLModel


class UploadFile(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    upload_dir_name: str = Field(index=True)
    guid_dir: str | None = Field(default=None)
    panorama: str | None = Field(default=None)
    reviewed: bool = Field(default=False)


SQLITE_FILE_NAME = "database.db"
SQLITE_URL = f"sqlite:///{SQLITE_FILE_NAME}"
