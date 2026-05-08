"""Populate jobs by generating new work from current database state."""
import hashlib
from typing import Callable

from sqlalchemy.dialects.sqlite import insert
from sqlmodel import Session, select

from lib.datatypes import Job, S3File, Image, ImageTag


def calc_output_file_id(input_file_id: str, workflow_template: str) -> str:
    """Calculate deterministic output file ID from input and template.

    This ensures the same input+template always maps to the same output.
    """
    return hashlib.sha256(f"{input_file_id}\0{workflow_template}".encode("utf-8")).hexdigest()


def generate_cartesian_jobs(
    session: Session,
    input_prefix: str = "benchmark_source_",
    image_tag_filter: str = "benchmark-",
    workflow_template_prefix: str = "mgs-pipeline-",
) -> list[Job]:
    """Generate jobs as cartesian product of datasets × image versions.

    For each S3 file matching input_prefix, and each image tag matching
    image_tag_filter, create a job if one doesn't already exist.

    Args:
        session: Database session
        input_prefix: S3 key prefix to filter input files
        image_tag_filter: Tag prefix to filter processing versions
        workflow_template_prefix: Prefix for workflow template names

    Returns:
        List of new Job objects to create
    """
    # Get existing jobs to avoid duplicates
    existing_jobs = {
        (j.input_file_id, j.workflow_template)
        for j in session.exec(select(Job)).all()
    }

    # Get input files matching prefix
    input_files = session.exec(
        select(S3File).where(S3File.key.like(f"%{input_prefix}%"))
    ).all()

    # Get image tags matching filter
    image_tags = session.exec(
        select(ImageTag).where(ImageTag.tag.like(f"%{image_tag_filter}%"))
    ).all()

    # Build workflow templates from image tags
    workflow_templates = [
        f"{workflow_template_prefix}{tag.tag}"
        for tag in image_tags
    ]

    new_jobs = []

    for input_file in input_files:
        for template in workflow_templates:
            # Check if job already exists
            if (input_file.id, template) in existing_jobs:
                continue

            # Calculate deterministic output file ID
            output_file_id = calc_output_file_id(input_file.id, template)

            job = Job(
                input_file_id=input_file.id,
                workflow_template=template,
                output_file_id=output_file_id,
                status="pending",
            )
            new_jobs.append(job)

    return new_jobs


def generate_jobs_from_callback(
    session: Session,
    generator: Callable[[Session], list[Job]],
) -> list[Job]:
    """Generate jobs using a custom generator function.

    Args:
        session: Database session
        generator: Function that takes a session and returns list of Job objects

    Returns:
        List of new Job objects to create
    """
    return generator(session)


def insert_jobs(session: Session, jobs: list[Job]) -> tuple[int, int]:
    """Insert jobs to database, skipping duplicates.

    Args:
        session: Database session
        jobs: List of Job objects to insert

    Returns:
        Tuple of (inserted_count, skipped_count)
    """
    if not jobs:
        return 0, 0

    # Prepare data for bulk insert
    job_data = [
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

    # Bulk insert with ignore on conflict (composite PK conflict)
    stmt = insert(Job).values(job_data).on_conflict_do_nothing()
    result = session.exec(stmt)

    # SQLite doesn't easily tell us how many were skipped, so calculate
    inserted = result.rowcount if hasattr(result, 'rowcount') else len(jobs)
    skipped = len(jobs) - inserted

    return inserted, skipped


def run_populate(
    engine,
    generator: Callable[[Session], list[Job]] | None = None,
    dry_run: bool = False,
) -> list[Job]:
    """Run job population.

    Args:
        engine: SQLAlchemy engine
        generator: Optional custom generator function. If None, uses default cartesian generator.
        dry_run: If True, only print what would be created without inserting

    Returns:
        List of jobs that would be/were created
    """
    with Session(engine) as session:
        # Use provided generator or default
        if generator:
            new_jobs = generate_jobs_from_callback(session, generator)
        else:
            new_jobs = generate_cartesian_jobs(session)

        if dry_run:
            print(f"[DRY RUN] Would create {len(new_jobs)} new jobs:")
            for job in new_jobs[:10]:  # Show first 10
                print(f"  - {job.input_file_id[:8]}... × {job.workflow_template}")
            if len(new_jobs) > 10:
                print(f"  ... and {len(new_jobs) - 10} more")
            return new_jobs

        # Actually insert
        inserted, skipped = insert_jobs(session, new_jobs)
        session.commit()

        print(f"Created {inserted} new jobs, skipped {skipped} duplicates")
        return new_jobs


if __name__ == "__main__":
    import argparse
    from sqlmodel import create_engine

    parser = argparse.ArgumentParser(description="Populate jobs from database state")
    parser.add_argument("--dry-run", action="store_true", help="Preview jobs without creating")
    parser.add_argument("--input-prefix", default="benchmark_source_", help="S3 key prefix for inputs")
    parser.add_argument("--image-tag-filter", default="benchmark-", help="Image tag prefix filter")
    args = parser.parse_args()

    engine = create_engine("sqlite:///benchmark.db")

    # Create custom generator with CLI args
    def generator(session):
        return generate_cartesian_jobs(
            session,
            input_prefix=args.input_prefix,
            image_tag_filter=args.image_tag_filter,
        )

    run_populate(engine, generator=generator, dry_run=args.dry_run)
