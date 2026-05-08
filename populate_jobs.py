"""Populate jobs by generating new work from database state.

EXAMPLE: This is a template. Replace the `my_generator` function
with your own logic for creating jobs from current DB state.
"""
import argparse

from sqlmodel import Session, create_engine, select

from lib.datatypes import Job, S3File
from lib.populate import populate


def my_generator(session: Session) -> list[Job]:
    """Example generator - replace with your own logic.

    Query current DB state (S3File, Image, ImageTag, Workflow, Job, etc.)
    and return new Job objects to create.
    """
    # Example: Create a job for each S3 file (if not already exists)
    existing = {(j.input_file_id, j.workflow_template) for j in session.exec(select(Job)).all()}

    files = session.exec(select(S3File)).all()

    new_jobs = []
    for f in files:
        template = "example-workflow"  # Replace with your template
        key = (f.id, template)

        if key in existing:
            continue

        # Define how YOU want to calculate output_file_id
        output_id = "your_output_id_logic_here"

        new_jobs.append(Job(
            input_file_id=f.id,
            workflow_template=template,
            output_file_id=output_id,
            status="pending",
        ))

    return new_jobs


def main():
    parser = argparse.ArgumentParser(description="Populate jobs from database state")
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating")
    args = parser.parse_args()

    engine = create_engine("sqlite:///benchmark.db")

    jobs = populate(engine, generator=my_generator, dry_run=args.dry_run)

    if args.dry_run:
        print(f"[DRY RUN] Would create {len(jobs)} new jobs")
        for job in jobs[:5]:
            print(f"  - {job.input_file_id[:8]}... × {job.workflow_template}")


if __name__ == "__main__":
    main()
