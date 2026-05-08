"""Generate jobs from database state and queue them for execution.

This script shows the two-step pattern:
1. GENERATE: Query current DB state, create Job objects
2. INSERT: Write new jobs to database (skipping duplicates)

Replace `my_generator()` with your own logic.
"""
import argparse

from sqlmodel import Session, create_engine, select

from lib.datatypes import Job, S3File
from lib.populate import insert_jobs


def my_generator(session: Session) -> list[Job]:
    """Step 1: GENERATE - Create jobs from current database state.

    Query whatever tables you need (S3File, Image, ImageTag, existing Jobs, etc.)
    and return new Job objects to be queued.

    Replace this with your own logic.
    """
    # Example: Check what already exists to avoid re-generating
    existing = {(j.input_file_id, j.workflow_template) for j in session.exec(select(Job)).all()}

    # Example: Query some input data
    files = session.exec(select(S3File)).all()

    # Example: Generate jobs
    new_jobs = []
    for f in files:
        template = "your-workflow-template"

        # Skip if already exists
        if (f.id, template) in existing:
            continue

        # You define how to calculate output_file_id
        output_id = f"your-output-id-calculation"

        new_jobs.append(Job(
            input_file_id=f.id,
            workflow_template=template,
            output_file_id=output_id,
            status="pending",
        ))

    return new_jobs


def main():
    parser = argparse.ArgumentParser(description="Generate jobs from database state")
    parser.add_argument("--dry-run", action="store_true", help="Generate only, don't insert")
    args = parser.parse_args()

    engine = create_engine("sqlite:///benchmark.db")

    # Step 1: GENERATE jobs from current DB state
    with Session(engine) as session:
        jobs = my_generator(session)

        if args.dry_run:
            print(f"[DRY RUN] Generated {len(jobs)} jobs (not inserting):")
            for job in jobs[:5]:
                print(f"  - {job.input_file_id[:8]}... × {job.workflow_template}")
            if len(jobs) > 5:
                print(f"  ... and {len(jobs) - 5} more")
            return

        # Step 2: INSERT jobs into database
        inserted, skipped = insert_jobs(session, jobs)
        session.commit()

        print(f"Generated {len(jobs)} jobs")
        print(f"  Inserted: {inserted}")
        print(f"  Skipped (duplicates): {skipped}")


if __name__ == "__main__":
    main()
