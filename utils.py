import hashlib
import json
from typing import List, NamedTuple
from collections import defaultdict

import boto3
import oras.client

from datatypes import Dataset, Image, ImageTag


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
    grouped = group_s3_prefixes(search_prefixes)
    datasets = []
    
    for (endpoint_url, bucket), prefixes in grouped.items():
        client = boto3.client(
            's3',
            endpoint_url=endpoint_url if endpoint_url else None
        )
        
        for prefix in prefixes:
            paginator = client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    dataset_id = calc_dataset_id(endpoint_url or '', bucket, key)
                    datasets.append(Dataset(
                        id=dataset_id,
                        endpoint_url=endpoint_url or '',
                        bucket=bucket,
                        key=key
                    ))
    
    return datasets


def get_images(repos: List[str]) -> tuple[List[Image], List[ImageTag]]:
    """
    use oras to list images on oci repo
    returns tuple of (images, image_tags)
    """
    images = []
    image_tags = []
    
    for repo in repos:
        parts = repo.split('/', 1)
        if len(parts) != 2:
            continue
        
        hostname, repo_path = parts
        
        try:
            client = oras.client.OrasClient(hostname=hostname)
            tags = client.get_tags(repo_path)
            
            digest_tags = defaultdict(list)
            
            for tag in tags:
                try:
                    container = client.get_container(f"{hostname}/{repo_path}:{tag}")
                    manifest = client.get_manifest(container)
                    manifest_bytes = json.dumps(manifest, separators=(',', ':'), sort_keys=True).encode('utf-8')
                    manifest_digest = 'sha256:' + hashlib.sha256(manifest_bytes).hexdigest()
                    
                    digest_tags[manifest_digest].append(tag)
                except Exception:
                    continue
            
            for digest, tag_list in digest_tags.items():
                image_id = calc_image_id(repo, digest)
                images.append(Image(
                    id=image_id,
                    repo=repo,
                    digest=digest
                ))
                
                for tag in tag_list:
                    image_tags.append(ImageTag(
                        image_id=image_id,
                        tag=tag
                    ))
        except Exception:
            continue
    
    return images, image_tags