"""Test for get_images that upserts results to database."""
from sqlmodel import Session, SQLModel, create_engine

from datatypes import Image, ImageTag
from utils import get_images


def upsert_images(repo: str, db_path: str = "benchmark.db") -> tuple[list[Image], list[ImageTag]]:
    """Fetch images from ECR and upsert to database."""
    images, image_tags = get_images([repo])

    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        for img in images:
            session.merge(img)
        for tag in image_tags:
            session.merge(tag)
        session.commit()

    return images, image_tags


def test_get_gs_train_images():
    """Test getting images from ECR and upserting to database."""
    repo = "223952452436.dkr.ecr.eu-west-2.amazonaws.com/m-xr/material-gaussians-gs-train"

    images, image_tags = upsert_images(repo)

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
