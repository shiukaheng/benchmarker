"""Main sync script for updating database from external sources."""
from sqlmodel import SQLModel, create_engine

from sync_utils import sync_images, sync_s3_files
from utils import SearchPrefix


def main():
    # Create engine and ensure tables exist
    engine = create_engine("sqlite:///benchmark.db")
    SQLModel.metadata.create_all(engine)

    # Sync images from ECR
    repo = "223952452436.dkr.ecr.eu-west-2.amazonaws.com/m-xr/material-gaussians-gs-train"
    print(f"Syncing images from: {repo}")
    images, image_tags = sync_images(engine, [repo])
    print(f"  -> Synced {len(images)} images, {len(image_tags)} tags")

    # Sync S3 files
    bucket = "mxr-internal-research-gaussian-splats"
    prefix = "benchmark_source_jpeg_datasets/"
    print(f"Syncing S3 files from: s3://{bucket}/{prefix}")
    search_prefixes = [SearchPrefix(endpoint_url="", bucket=bucket, prefix=prefix)]
    s3files = sync_s3_files(engine, search_prefixes)
    print(f"  -> Synced {len(s3files)} files")

    print("\nSync complete.")


if __name__ == "__main__":
    main()
