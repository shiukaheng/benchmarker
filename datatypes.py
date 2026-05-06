from enum import Enum

from sqlmodel import SQLModel, Field



class Dataset(SQLModel, table=True):
    path: str = Field(primary_key=True)


class Model(SQLModel, table=True):
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
    dataset_path: str = Field(foreign_key="dataset.path", primary_key=True)
    model_id: str = Field(foreign_key="model.id", primary_key=True)

    status: str = "pending"