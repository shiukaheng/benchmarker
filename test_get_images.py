"""Test for get_images that upserts results to database efficiently."""
from sqlalchemy.dialects.sqlite import insert
from sqlmodel import Session, SQLModel, create_engine

from datatypes import Image, ImageTag
from utils import get_images


_engine = None


def get_engine(db_path: str = "benchmark.db"):
    """Get or create singleton engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(f"sqlite:///{db_path}")
        SQLModel.metadata.create_all(_engine)
    return _engine


def bulk_upsert_images(
    repo: str, db_path: str = "benchmark.db"
) -> tuple[list[Image], list[ImageTag]]:
    """Fetch images from ECR and bulk upsert to database."""
    images, image_tags = get_images([repo])

    engine = get_engine(db_path)

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


def test_get_gs_train_images():
    """Test getting images from ECR and upserting to database."""
    repo = "223952452436.dkr.ecr.eu-west-2.amazonaws.com/m-xr/material-gaussians-gs-train"

    images, image_tags = bulk_upsert_images(repo)

    print(f"\nFound {len(images)} unique image digests")
    print(f"Found {len(image_tags)} total tags")

    for img in images:
        print(f"\nImage: {img.repo}")
        print(f"  Digest: {img.digest}")
        tags_for_image = [t.tag for t in image_tags if t.image_id == img.id]
        print(f"  Tags: {tags_for_image}")

    assert len(images) > 0, "Expected at least one image"

    tag_names = [t.tag for t in image_tags]
    print(f"\nAll tags found: {tag_names}")

    expected = "material-gaussians-latest"
    assert expected in tag_names, f"Expected tag '{expected}' not found"


if __name__ == "__main__":
    test_get_gs_train_images()
