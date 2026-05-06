from enum import Enum

from sqlmodel import SQLModel, Field



class Dataset(SQLModel, table=True):
    id: str = Field(primary_key=True)
    endpoint_url: str
    bucket: str
    key: str


class Image(SQLModel, table=True):
    id: str = Field(primary_key=True)
    repo: str
    digest: str
    tag: str | None = None


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    suceeded = "suceeded"
    failed = "failed"


class Job(SQLModel, table=True):
    dataset_id: str = Field(foreign_key="dataset.id", primary_key=True)
    image_id: str = Field(foreign_key="image.id", primary_key=True)

    status: str = "pending"