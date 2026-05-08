"""Populate jobs by generating new work from current database state."""
import argparse

from sqlmodel import create_engine

from lib.populate import generate_cartesian_jobs, run


def main():
    parser = argparse.ArgumentParser(description="Populate jobs from database state")
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating")
    parser.add_argument("--input-prefix", default="benchmark_source_", help="S3 key prefix")
    parser.add_argument("--image-tag-filter", default="benchmark-", help="Image tag prefix")
    args = parser.parse_args()

    engine = create_engine("sqlite:///benchmark.db")

    def generator(session):
        return generate_cartesian_jobs(
            session,
            input_prefix=args.input_prefix,
            image_tag_filter=args.image_tag_filter,
        )

    jobs = run(engine, generator=generator, dry_run=args.dry_run)

    if args.dry_run:
        print(f"[DRY RUN] Would create {len(jobs)} new jobs:")
        for job in jobs[:10]:
            print(f"  - {job.input_file_id[:8]}... × {job.workflow_template}")
        if len(jobs) > 10:
            print(f"  ... and {len(jobs) - 10} more")


if __name__ == "__main__":
    main()
