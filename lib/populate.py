"""Job population utilities - generate and insert jobs into database."""
from typing import Callable

from sqlalchemy.dialects.sqlite import insert
from sqlmodel import Session

from lib.datatypes import Job


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
    generator: Callable[[Session], list[Job]],
    dry_run: bool = False,
) -> list[Job]:
    """Generate jobs from database state and insert them.

    This is a convenience wrapper that combines generation + insertion.
    For finer control, use the individual functions.

    Args:
        engine: SQLAlchemy engine
        generator: Function that takes a Session and returns list of Job objects
        dry_run: If True, generate only without inserting

    Returns:
        List of jobs (generated or inserted)
    """
    with Session(engine) as session:
        jobs = generator(session)

        if dry_run:
            print(f"[DRY RUN] Generated {len(jobs)} jobs (not inserting)")
            return jobs

        inserted, skipped = insert_jobs(session, jobs)
        session.commit()
        print(f"Generated {len(jobs)} jobs, inserted {inserted}, skipped {skipped} duplicates")
        return jobs
