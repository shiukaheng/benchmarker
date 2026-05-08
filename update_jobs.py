"""Update jobs by generating new work from database state.

Replace my_generator() with your own logic for creating jobs.
Add multiple generators to the list to compose different job creation strategies.
"""
import argparse

from sqlmodel import Session, select

from lib.job_generation_utils import update_jobs
from lib.datatypes import Job, S3File


def my_generator(session: Session) -> list[Job]:
    """Generate jobs from current database state.

    Replace this with your own logic.
    """
    existing = {(j.input_file_id, j.workflow_template) for j in session.exec(select(Job)).all()}
    files = session.exec(select(S3File)).all()

    new_jobs = []
    for f in files:
        template = "your-workflow-template"
        if (f.id, template) in existing:
            continue

        new_jobs.append(Job(
            input_file_id=f.id,
            workflow_template=template,
            output_file_id="your-output-id",
            status="pending",
        ))

    return new_jobs


def main():
    parser = argparse.ArgumentParser(description="Update jobs from database state")
    parser.add_argument("--dry-run", action="store_true", help="Preview without updating")
    args = parser.parse_args()

    from sqlmodel import create_engine
    engine = create_engine("sqlite:///benchmark.db")

    # Pass multiple generators to compose different strategies
    # update_jobs(engine, generators=[gen_datasets, gen_experiments, gen_backfill], ...)
    update_jobs(engine, generators=[my_generator], dry_run=args.dry_run)


if __name__ == "__main__":
    main()
