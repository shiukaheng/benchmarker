"""Job population logic - generating new jobs from database state."""
import hashlib
from typing import Callable

from sqlalchemy.dialects.sqlite import insert
from sqlmodel import Session, select

from lib.datatypes import Job, S3File, ImageTag


def calc_output_file_id(input_file_id: str, workflow_template: str) -> str:
    """Calculate deterministic output file ID from input and template."""
    return hashlib.sha256(f"{input_file_id}\0{workflow_template}".encode("utf-8")).hexdigest()


def generate_cartesian_jobs(
    session: Session,
    input_prefix: str = "benchmark_source_",
    image_tag_filter: str = "benchmark-",
    workflow_template_prefix: str = "mgs-pipeline-",
) -> list[Job]:
    """Generate jobs as cartesian product of datasets × image versions."""
    existing = {
        (j.input_file_id, j.workflow_template)
        for j in session.exec(select(Job)).all()
    }

    input_files = session.exec(
        select(S3File).where(S3File.key.like(f"%{input_prefix}%"))
    ).all()

    image_tags = session.exec(
        select(ImageTag).where(ImageTag.tag.like(f"%{image_tag_filter}%"))
    ).all()

    templates = [f"{workflow_template_prefix}{tag.tag}" for tag in image_tags]

    new_jobs = []
    for inp in input_files:
        for template in templates:
            if (inp.id, template) in existing:
                continue
            output_id = calc_output_file_id(inp.id, template)
            new_jobs.append(Job(
                input_file_id=inp.id,
                workflow_template=template,
                output_file_id=output_id,
                status="pending",
            ))
    return new_jobs


def insert_jobs(session: Session, jobs: list[Job]) -> tuple[int, int]:
    """Insert jobs to database, skipping duplicates."""
    if not jobs:
        return 0, 0

    data = [
        {
            "input_file_id": j.input_file_id,
            "workflow_template": j.workflow_template,
            "output_file_id": j.output_file_id,
            "status": j.status,
            "workflow_namespace": j.workflow_namespace,
            "workflow_name": j.workflow_name,
        }
        for j in jobs
    ]

    stmt = insert(Job).values(data).on_conflict_do_nothing()
    result = session.exec(stmt)
    inserted = result.rowcount if hasattr(result, 'rowcount') else len(jobs)
    return inserted, len(jobs) - inserted


def populate(
    engine,
    generator: Callable[[Session], list[Job]],
    dry_run: bool = False,
) -> list[Job]:
    """Populate jobs from database state."""
    with Session(engine) as session:
        jobs = generator(session)

        if dry_run:
            return jobs

        inserted, skipped = insert_jobs(session, jobs)
        session.commit()
        print(f"Created {inserted} jobs, skipped {skipped} duplicates")
        return jobs
