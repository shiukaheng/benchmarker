import hashlib
import json
from typing import List, NamedTuple
from collections import defaultdict

import boto3
import oras.client

from datatypes import S3File, Image, ImageTag, Workflow


def calc_image_id(repo: str, digest: str) -> str:
    return hashlib.sha256(f"{repo}\0{digest}".encode("utf-8")).hexdigest()

def calc_s3file_id(endpoint_url: str, bucket: str, key: str) -> str:
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


def get_s3files(search_prefixes: List[SearchPrefix]) -> List[S3File]:
    """
    use boto3 to find all s3 files matching criteria
    """
    grouped = group_s3_prefixes(search_prefixes)
    s3files = []
    
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
                    s3file_id = calc_s3file_id(endpoint_url or '', bucket, key)
                    s3files.append(S3File(
                        id=s3file_id,
                        endpoint_url=endpoint_url or '',
                        bucket=bucket,
                        key=key
                    ))
    
    return s3files


def _is_ecr_repo(hostname: str) -> bool:
    """Check if hostname is an AWS ECR registry."""
    return ".dkr.ecr." in hostname and hostname.endswith(".amazonaws.com")


def _get_ecr_images(repo: str, hostname: str, repo_path: str) -> tuple[List[Image], List[ImageTag]]:
    """Get images from ECR using boto3."""
    # Parse: 223952452436.dkr.ecr.eu-west-2.amazonaws.com
    parts = hostname.split(".")
    if len(parts) < 4:
        return [], []

    registry_id = parts[0]
    region = parts[3]

    client = boto3.client("ecr", region_name=region)
    paginator = client.get_paginator("describe_images")
    images = []
    image_tags = []

    for page in paginator.paginate(registryId=registry_id, repositoryName=repo_path):
        for img in page.get("imageDetails", []):
            digest = img["imageDigest"]
            image_id = calc_image_id(repo, digest)

            images.append(Image(
                id=image_id,
                repo=repo,
                digest=digest
            ))

            for tag in img.get("imageTags", []):
                image_tags.append(ImageTag(
                    image_id=image_id,
                    tag=tag
                ))

    return images, image_tags


def _get_oras_images(repo: str, hostname: str, repo_path: str) -> tuple[List[Image], List[ImageTag]]:
    """Get images from OCI registry using oras."""
    images = []
    image_tags = []

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

    return images, image_tags


def get_images(repos: List[str]) -> tuple[List[Image], List[ImageTag]]:
    """
    List images on OCI repos.
    Uses boto3 for ECR repos, oras for others.
    Returns tuple of (images, image_tags).
    """
    images = []
    image_tags = []

    for repo in repos:
        parts = repo.split('/', 1)
        if len(parts) != 2:
            continue

        hostname, repo_path = parts

        try:
            if _is_ecr_repo(hostname):
                imgs, tags = _get_ecr_images(repo, hostname, repo_path)
            else:
                imgs, tags = _get_oras_images(repo, hostname, repo_path)

            images.extend(imgs)
            image_tags.extend(tags)
        except Exception:
            continue

    return images, image_tags


def get_workflows(namespace: str) -> list[Workflow]:
    """List all Argo workflows in a namespace from K8s.

    Args:
        namespace: K8s namespace to list workflows from

    Returns:
        List of Workflow objects
    """
    from kubernetes import client, config

    config.load_kube_config()
    api = client.CustomObjectsApi()

    workflows = []

    try:
        response = api.list_namespaced_custom_object(
            group="argoproj.io",
            version="v1alpha1",
            namespace=namespace,
            plural="workflows",
        )

        for item in response.get("items", []):
            metadata = item.get("metadata", {})
            status = item.get("status", {})

            namespace_val = metadata.get("namespace", namespace)
            name = metadata.get("name", "")
            phase = status.get("phase", "Unknown")
            created_at = metadata.get("creationTimestamp")
            finished_at = status.get("finishedAt")

            workflows.append(Workflow(
                namespace=namespace_val,
                name=name,
                phase=phase,
                created_at=created_at,
                finished_at=finished_at,
            ))
    except Exception:
        pass

    return workflows