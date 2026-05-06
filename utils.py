import hashlib
from typing import List, NamedTuple
from collections import defaultdict

from datatypes import Dataset, Image


def calc_image_id(repo: str, digest: str) -> str:
    return hashlib.sha256(f"{repo}\0{digest}".encode("utf-8")).hexdigest()

def calc_dataset_id(endpoint_url: str, bucket: str, key: str) -> str:
    return hashlib.sha256(f"{endpoint_url}\0{bucket}\0{key}".encode("utf-8")).hexdigest()


class SearchPrefix(NamedTuple):
    endpoint_url: str
    bucket: str
    prefix: str


def group_s3_prefixes(
    refs: list[SearchPrefix],
) -> dict[tuple[str | None, str], list[str]]:
    grouped = defaultdict(list)

    for ref in refs:
        grouped[(ref.endpoint_url, ref.bucket)].append(ref.prefix)

    return dict(grouped)


def get_datasets(search_prefixes: List[SearchPrefix]) -> List[Dataset]:
    """
    use boto3 to find all datasets (files on s3(like) really..) matching criteria
    """
    return NotImplementedError()


def get_images(repos: List[str]) -> List[Image]:
    """
    use oras to list images on oci repo
    """
    return NotImplementedError()