"""Update jobs by generating new work from database state.

Generates jobs for benchmark preprocessing:
- Input: s3://material-gaussians-data-dev/benchmark_source_jpeg_datasets/<name>.zip
- Output: s3://material-gaussians-data-dev/benchmark_preprocessed_jpeg_datasets/<name>.zip
- Workflow: benchmark-preprocess (from workflows/benchmark_preprocess_workflow.yaml)
"""
import argparse
import hashlib

from sqlmodel import Session, select

from lib.job_generation_utils import update_jobs
from lib.datatypes import Job, S3File
from lib.utils import calc_s3file_id


# Configuration
BUCKET = "material-gaussians-data-dev"
INPUT_PREFIX = "benchmark_source_jpeg_datasets/"
OUTPUT_PREFIX = "benchmark_preprocessed_jpeg_datasets/"
WORKFLOW_TEMPLATE = "benchmark-preprocess"


def calc_output_file_id(input_file: S3File) -> str:
    """Calculate output file ID by swapping prefix in the S3 key."""
    output_key = input_file.key.replace(INPUT_PREFIX, OUTPUT_PREFIX, 1)
    return calc_s3file_id(input_file.endpoint_url, input_file.bucket, output_key)


def my_generator(session: Session) -> list[Job]:
    """Generate preprocessing jobs for benchmark datasets.

    For each S3 file in benchmark_source_jpeg_datasets/, create a job
    that outputs to benchmark_preprocessed_jpeg_datasets/ with the same suffix.
    """
    # Get existing jobs to avoid duplicates
    existing = {
        (j.input_file_id, j.workflow_template)
        for j in session.exec(select(Job)).all()
    }

    # Get input files from the specific bucket and prefix
    files = session.exec(
        select(S3File)
        .where(S3File.bucket == BUCKET)
        .where(S3File.key.like(f"{INPUT_PREFIX}%"))
    ).all()

    new_jobs = []
    for f in files:
        # Skip if job already exists for this input + template
        if (f.id, WORKFLOW_TEMPLATE) in existing:
            continue

        # Calculate deterministic output file ID
        output_id = calc_output_file_id(f)

        new_jobs.append(Job(
            input_file_id=f.id,
            workflow_template=WORKFLOW_TEMPLATE,
            output_file_id=output_id,
            status="pending",
        ))

    return new_jobs


def main():
    parser = argparse.ArgumentParser(description="Update benchmark preprocessing jobs")
    parser.add_argument("--dry-run", action="store_true", help="Preview without updating")
    args = parser.parse_args()

    from sqlmodel import create_engine
    engine = create_engine("sqlite:///benchmark.db")

    update_jobs(engine, generators=[my_generator], dry_run=args.dry_run)


if __name__ == "__main__":
    main()
