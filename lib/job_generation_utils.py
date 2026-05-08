"""Job population utilities - generate and insert jobs into database."""
import hashlib
from typing import Callable

from sqlalchemy.dialects.sqlite import insert
from sqlmodel import Session

from lib.datatypes import Job


def calc_workflow_name(job: Job, namespace: str = "material-gaussians") -> str:
    """Calculate deterministic workflow name for a job.

    This ensures the same job always maps to the same workflow name,
    preventing accidental duplicate launches.

    Args:
        job: The job to calculate workflow name for
        namespace: K8s namespace (included in hash for uniqueness)

    Returns:
        Deterministic workflow name (max 63 chars for K8s)
    """
    # Hash the job's unique identity (composite PK)
    unique_str = f"{namespace}\0{job.input_file_id}\0{job.workflow_template}\0{job.output_file_id}"
    hash_suffix = hashlib.sha256(unique_str.encode("utf-8")).hexdigest()[:8]

    # Build name: template-hash (K8s limit: 63 chars)
    base = job.workflow_template[:54]  # Leave room for dash + 8 char hash
    return f"{base}-{hash_suffix}"


def insert_jobs(session: Session, jobs: list[Job]) -> tuple[int, int]:
    """Insert jobs to database, skipping duplicates (by composite PK).

    Args:
        session: Database session
        jobs: List of Job objects to insert

    Returns:
        Tuple of (inserted_count, skipped_count)
    """
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


def update_jobs(
    engine,
    generators: list[Callable[[Session], list[Job]]],
    dry_run: bool = False,
) -> list[Job]:
    """Generate jobs from database state and insert them.

    This is a convenience wrapper that combines generation + insertion.
    For finer control, use the individual functions.

    Args:
        engine: SQLAlchemy engine
        generators: List of functions that take a Session and return list of Job objects
        dry_run: If True, generate only without inserting

    Returns:
        List of all jobs (generated or inserted)
    """
    with Session(engine) as session:
        # Run all generators and merge results
        all_jobs: list[Job] = []
        for gen in generators:
            jobs = gen(session)
            all_jobs.extend(jobs)

        if dry_run:
            print(f"[DRY RUN] Generated {len(all_jobs)} jobs (not inserting)")
            return all_jobs

        inserted, skipped = insert_jobs(session, all_jobs)
        session.commit()
        print(f"Generated {len(all_jobs)} jobs, inserted {inserted}, skipped {skipped} duplicates")
        return all_jobs
