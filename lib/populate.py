"""Job population utilities - insert generated jobs into database."""
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
