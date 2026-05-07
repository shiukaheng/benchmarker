"""Test for get_s3files that upserts results to database."""
from sqlalchemy.dialects.sqlite import insert
from sqlmodel import Session, SQLModel, create_engine

from datatypes import S3File
from utils import get_s3files, SearchPrefix

_engine = None


def get_engine(db_path: str = "benchmark.db"):
    global _engine
    if _engine is None:
        _engine = create_engine(f"sqlite:///{db_path}")
        SQLModel.metadata.create_all(_engine)
    return _engine


def bulk_upsert_s3files(
    bucket: str, prefix: str, db_path: str = "benchmark.db"
) -> list[S3File]:
    """Fetch S3 files and bulk upsert to database."""
    search_prefixes = [SearchPrefix(endpoint_url="", bucket=bucket, prefix=prefix)]
    s3files = get_s3files(search_prefixes)

    engine = get_engine(db_path)

    with Session(engine) as session:
        if s3files:
            file_data = [{"id": f.id, "endpoint_url": f.endpoint_url, "bucket": f.bucket, "key": f.key} for f in s3files]
            stmt = insert(S3File).values(file_data)
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "endpoint_url": stmt.excluded.endpoint_url,
                    "bucket": stmt.excluded.bucket,
                    "key": stmt.excluded.key,
                },
            )
            session.exec(stmt)
            session.commit()

    return s3files


def test_get_s3files():
    bucket = "mxr-internal-research-gaussian-splats"
    prefix = "jpeg_benchmark_max_500/"

    s3files = bulk_upsert_s3files(bucket, prefix)

    print(f"\nFound {len(s3files)} S3 files")
    for f in s3files[:10]:
        print(f"  {f.key}")

    if len(s3files) > 10:
        print(f"  ... and {len(s3files) - 10} more")


if __name__ == "__main__":
    test_get_s3files()
