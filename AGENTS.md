We are building a minimal Python-based orchestration system for reconstruction benchmarking experiments.

Core responsibilities:

Discover available container images from a Docker/OCI registry using ORAS.
Discover available datasets from S3 using boto3.
Store discovered metadata in Postgres.
Generate and track reconstruction experiment combinations.
Launch Kubernetes jobs through the Kubernetes Python client.
Track experiment lifecycle and outputs.

Architecture goals:

Extremely small and maintainable codebase.
Modular adapters for each external system.
Simple orchestration logic.
Database as the source of truth.
Avoid heavy orchestration frameworks (Airflow, Argo, Celery, etc.).

Proposed package structure:

benchrunner/
  adapters/
    postgres.py
    image_registry.py
    dataset_registry.py
    k8s.py

  services/
    discovery.py
    planner.py
    launcher.py

  models.py
  config.py
  main.py

System components:

Image discovery
Query OCI/Docker registry via ORAS.
Store:
repository
tag
digest
Dataset discovery
Query S3 bucket/prefix via boto3.
Each dataset is represented by:
bucket
prefix (subdirectory)
optional dataset name
Experiment planner
Produce Cartesian product:
all images × all datasets
Insert missing experiments into DB.
Deduplicate via DB constraints.
Kubernetes launcher
Pull pending experiments from DB.
Launch Kubernetes Jobs.
Pass image + dataset location + output location as job args/env vars.
Record Kubernetes job name/status.
Postgres schema
container_images
- id
- repo
- tag
- digest
- discovered_at

datasets
- id
- bucket
- prefix
- dataset_name
- discovered_at

reconstruction_experiments
- id
- image_id
- dataset_id
- status
- k8s_job_name
- output_bucket
- output_prefix
- timestamps

Key design principle:

services/ contains workflow/business logic.
adapters/ are thin wrappers around external systems.
Database acts as the persistent experiment graph/state machine.