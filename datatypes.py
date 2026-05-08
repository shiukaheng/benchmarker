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
    succeeded = "succeeded"
    failed = "failed"


class Job(SQLModel, table=True):
    input_file_id: str = Field(foreign_key="s3file.id", primary_key=True)
    workflow_template: str = Field(primary_key=True)
    output_file_id: str = Field(primary_key=True)  # not foreign key because it may or may not exist yet
    status: str = "pending"

    # Reference to the K8s workflow we launched
    workflow_namespace: str | None = None
    workflow_name: str | None = None


class Workflow(SQLModel, table=True):
    """Mirror of K8s Argo Workflow state."""

    namespace: str = Field(primary_key=True)
    name: str = Field(primary_key=True)
    phase: str  # Pending, Running, Succeeded, Failed, Error, Unknown
    created_at: str | None = None  # ISO8601 timestamp
    finished_at: str | None = None  # ISO8601 timestamp