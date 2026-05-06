from enum import Enum

from sqlmodel import SQLModel, Field



class S3File(SQLModel, table=True):
    id: str = Field(primary_key=True)
    endpoint_url: str
    bucket: str
    key: str


class Image(SQLModel, table=True):
    id: str = Field(primary_key=True)
    repo: str
    digest: str


class ImageTag(SQLModel, table=True):
    image_id: str = Field(foreign_key="image.id", primary_key=True)
    tag: str = Field(primary_key=True)


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    suceeded = "suceeded"
    failed = "failed"


class Job(SQLModel, table=True):
    s3file_id: str = Field(foreign_key="s3file.id", primary_key=True)
    image_id: str = Field(foreign_key="image.id", primary_key=True)

    status: str = "pending"