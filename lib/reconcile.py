"""Job reconciliation logic."""
from enum import Enum
from typing import NamedTuple

from kubernetes import client, config
from sqlmodel import Session, select

from lib.datatypes import Job, JobStatus, S3File, Workflow


class ReconcileState(str, Enum):
    success = "success"
    running = "running"
    pending = "pending"
    failed = "failed"


class WorkflowRef(NamedTuple):
    namespace: str
    name: str


def get_workflow_phase(workflows: dict[tuple[str, str], Workflow], namespace: str | None, name: str | None) -> str | None:
    """Lookup workflow phase from the synced workflows dict.

    Args:
        workflows: Dict mapping (namespace, name) -> Workflow
        namespace: Workflow namespace
        name: Workflow name

    Returns:
        Phase string if found, None if workflow not in DB
    """
    if not namespace or not name:
        return None
    wf = workflows.get((namespace, name))
    return wf.phase if wf else None


def compute_job_state(
    job: Job,
    output_exists: bool,
    workflow_phase: str | None,
) -> ReconcileState:
    """Compute the state of a single job without modifying it.

    Args:
        job: The job to check
        output_exists: Whether the output file exists in S3 (from DB sync)
        workflow_phase: Current phase from synced Workflow table, or None if not found

    Returns:
        The computed state
    """
    # Case 1: Output exists -> SUCCESS
    if output_exists:
        return ReconcileState.success

    # Case 2: Have workflow reference -> check phase from DB
    if workflow_phase:
        match workflow_phase:
            case "Pending" | "Unknown":
                return ReconcileState.pending
            case "Running":
                return ReconcileState.running
            case "Succeeded":
                # Workflow reports success but no output file -> problem
                return ReconcileState.failed
            case "Failed" | "Error":
                return ReconcileState.failed

    # Case 3: No workflow reference, or workflow not found in DB, and no output
    # -> need to launch (or workflow disappeared/crashed)
    if job.workflow_namespace and job.workflow_name and not workflow_phase:
        # Referenced workflow no longer exists in K8s (crashed, timed out, manually deleted)
        return ReconcileState.failed

    # No workflow reference yet -> need to launch
    return ReconcileState.pending


def reconcile_job(
    job: Job,
    output_exists: bool,
    workflow_phase: str | None,
) -> ReconcileState:
    """Reconcile a single job's state and update the job object.

    Args:
        job: The job to reconcile (will be modified)
        output_exists: Whether the output file exists in S3 (from DB sync)
        workflow_phase: Current phase from synced Workflow table, or None

    Returns:
        The reconciled state
    """
    state = compute_job_state(job, output_exists, workflow_phase)

    # Map reconcile state to job status
    status_map = {
        ReconcileState.success: JobStatus.succeeded,
        ReconcileState.running: JobStatus.running,
        ReconcileState.pending: JobStatus.pending,
        ReconcileState.failed: JobStatus.failed,
    }
    job.status = status_map[state]

    return state


def launch_workflow(
    api: client.CustomObjectsApi,
    job: Job,
    input_s3_file: str,
    output_s3_file: str,
    namespace: str = "material-gaussians",
    service_account: str = "product-apps-workflow",
) -> WorkflowRef:
    """Launch a new Argo workflow for the job.

    Args:
        api: K8s CustomObjectsApi
        job: The job to launch workflow for
        input_s3_file: Full S3 URI for input file
        output_s3_file: Full S3 URI for output file
        namespace: K8s namespace
        service_account: Service account for workflow

    Returns:
        Reference to the launched workflow
    """
    import uuid

    workflow_name = f"{job.workflow_template}-{job.input_file_id[:8]}-{str(uuid.uuid4())[:6]}"

    workflow = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Workflow",
        "metadata": {
            "name": workflow_name,
            "namespace": namespace,
        },
        "spec": {
            "serviceAccountName": service_account,
            "workflowTemplateRef": {"name": job.workflow_template},
            "arguments": {
                "parameters": [
                    {"name": "input_s3_file", "value": input_s3_file},
                    {"name": "output_s3_file", "value": output_s3_file},
                ]
            },
        },
    }

    api.create_namespaced_custom_object(
        group="argoproj.io",
        version="v1alpha1",
        namespace=namespace,
        plural="workflows",
        body=workflow,
    )

    return WorkflowRef(namespace=namespace, name=workflow_name)


def run_reconciliation(engine, dry_run: bool = False):
    """Run full reconciliation loop.

    Args:
        engine: SQLAlchemy engine
        dry_run: If True, only print what would be done without making changes
    """
    config.load_kube_config()
    api = client.CustomObjectsApi()

    with Session(engine) as session:
        # Get all jobs
        jobs = session.exec(select(Job)).all()

        # Build lookup of workflows from DB (synced by main.py)
        workflows = {
            (w.namespace, w.name): w
            for w in session.exec(select(Workflow)).all()
        }

        # Build set of existing output file IDs for quick lookup
        output_files = session.exec(select(S3File.id)).all()
        output_file_ids = set(output_files)

        # Get input files for path resolution
        input_files = {
            f.id: f for f in session.exec(select(S3File)).all()
        }

        for job in jobs:
            output_exists = job.output_file_id in output_file_ids

            # Lookup workflow phase from synced DB state
            workflow_phase = get_workflow_phase(workflows, job.workflow_namespace, job.workflow_name)

            # Get S3 paths if we need to launch
            input_file = input_files.get(job.input_file_id)
            if not input_file:
                print(f"Job {job.input_file_id}: missing input file record")
                continue

            input_s3 = f"s3://{input_file.bucket}/{input_file.key}"

            # Resolve output file path (may not exist in S3File table yet)
            output_s3_file = session.get(S3File, job.output_file_id)
            if output_s3_file:
                output_s3 = f"s3://{output_s3_file.bucket}/{output_s3_file.key}"
            else:
                # Infer output path from input path conventions
                output_key = input_file.key.replace(
                    "benchmark_source_", "benchmark_output_"
                )
                output_s3 = f"s3://{input_file.bucket}/{output_key}"

            # Compute state (read-only if dry_run)
            if dry_run:
                state = compute_job_state(job, output_exists, workflow_phase)
            else:
                state = reconcile_job(job, output_exists, workflow_phase)

            # Launch if needed
            if state == ReconcileState.pending and not job.workflow_name:
                if dry_run:
                    print(f"Job ({job.input_file_id[:8]}, {job.workflow_template}): [DRY RUN] would launch workflow")
                    print(f"  -> input: {input_s3}")
                    print(f"  -> output: {output_s3}")
                    continue

                print(f"Job ({job.input_file_id[:8]}, {job.workflow_template}): launching workflow...")
                ref = launch_workflow(api, job, input_s3, output_s3)
                job.workflow_namespace = ref.namespace
                job.workflow_name = ref.name
                job.status = JobStatus.running
                state = ReconcileState.running
                print(f"  -> Launched: {ref.namespace}/{ref.name}")

            print(f"Job ({job.input_file_id[:8]}, {job.workflow_template}): {state.value}")

        if dry_run:
            print("\n[DRY RUN] No changes committed")
        else:
            session.commit()
