"""Simple test for get_images against ECR gs-train image."""
from utils import get_images


def test_get_gs_train_images():
    """Test getting images from ECR for material-gaussians-gs-train."""
    repo = "223952452436.dkr.ecr.eu-west-2.amazonaws.com/m-xr/material-gaussians-gs-train"

    images, image_tags = get_images([repo])

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

    # Verify expected tags from build script
    expected = "material-gaussians-latest"
    assert expected in tag_names, f"Expected tag '{expected}' not found"


if __name__ == "__main__":
    test_get_gs_train_images()
