"""Sync functions for updating database from external sources."""
from sqlalchemy.dialects.sqlite import insert
from sqlmodel import Session

from datatypes import Image, ImageTag, S3File
from utils import get_images, get_s3files, SearchPrefix


def sync_images(engine, repos: list[str]) -> tuple[list[Image], list[ImageTag]]:
    """Fetch images from OCI repos and bulk upsert to database.

    Args:
        engine: SQLAlchemy engine to use for database operations
        repos: List of OCI repository URLs to fetch images from

    Returns:
        Tuple of (images, image_tags) that were synced
    """
    images, image_tags = get_images(repos)

    with Session(engine) as session:
        # Bulk upsert images - single query with ON CONFLICT UPDATE
        if images:
            img_data = [{"id": img.id, "repo": img.repo, "digest": img.digest} for img in images]
            stmt = insert(Image).values(img_data)
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={"repo": stmt.excluded.repo, "digest": stmt.excluded.digest}
            )
            session.exec(stmt)

        # Bulk insert tags - ignore duplicates
        if image_tags:
            tag_data = [{"image_id": t.image_id, "tag": t.tag} for t in image_tags]
            stmt = insert(ImageTag).values(tag_data).on_conflict_do_nothing()
            session.exec(stmt)

        session.commit()

    return images, image_tags


def sync_s3_files(engine, search_prefixes: list[SearchPrefix]) -> list[S3File]:
    """Fetch S3 files and bulk upsert to database.

    Args:
        engine: SQLAlchemy engine to use for database operations
        search_prefixes: List of SearchPrefix objects defining buckets/prefixes to scan

    Returns:
        List of S3File objects that were synced
    """
    s3files = get_s3files(search_prefixes)

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
