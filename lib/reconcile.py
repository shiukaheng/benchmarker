"""Job reconciliation logic - two-phase: plan then execute."""
from enum import Enum
from typing import NamedTuple

from kubernetes import client, config
from sqlmodel import Session, select

from lib.datatypes import Job, JobStatus, S3File, Workflow
from lib.actions import LaunchWorkflowAction, UpdateJobStateAction, ReconcileAction


class ReconcileState(str, Enum):
    success = "success"
    running = "running"
    pending = "pending"
    failed = "failed"


class WorkflowRef(NamedTuple):
    namespace: str
    name: str


def get_workflow_phase(workflows: dict[tuple[str, str], Workflow], namespace: str | None, name: str | None) -> str | None:
    """Lookup workflow phase from the synced workflows dict."""
    if not namespace or not name:
        return None
    wf = workflows.get((namespace, name))
    return wf.phase if wf else None


def compute_job_state(
    job: Job,
    output_exists: bool,
    workflow_phase: str | None,
) -> ReconcileState:
    """Compute the state of a single job without modifying it."""
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
                return ReconcileState.failed
            case "Failed" | "Error":
                return ReconcileState.failed

    # Case 3: Referenced workflow no longer exists -> failed
    if job.workflow_namespace and job.workflow_name and not workflow_phase:
        return ReconcileState.failed

    # No workflow reference yet -> need to launch
    return ReconcileState.pending


def plan_reconciliation(engine) -> list[ReconcileAction]:
    """Generate a plan of actions needed to reconcile jobs.

    This is a pure function that examines the current state and produces
    a list of actions without modifying anything.

    Args:
        engine: SQLAlchemy engine

    Returns:
        List of actions to execute
    """
    actions: list[ReconcileAction] = []

    with Session(engine) as session:
        # Get all jobs
        jobs = session.exec(select(Job)).all()

        # Build lookup of workflows from DB
        workflows = {
            (w.namespace, w.name): w
            for w in session.exec(select(Workflow)).all()
        }

        # Build set of existing output file IDs
        output_files = session.exec(select(S3File.id)).all()
        output_file_ids = set(output_files)

        # Get input files for path resolution
        input_files = {f.id: f for f in session.exec(select(S3File)).all()}

        for job in jobs:
            output_exists = job.output_file_id in output_file_ids
            workflow_phase = get_workflow_phase(workflows, job.workflow_namespace, job.workflow_name)

            state = compute_job_state(job, output_exists, workflow_phase)

            # Map state to status string
            status_map = {
                ReconcileState.success: "succeeded",
                ReconcileState.running: "running",
                ReconcileState.pending: "pending",
                ReconcileState.failed: "failed",
            }
            new_status = status_map[state]

            # Add update state action if status changed
            if job.status != new_status:
                actions.append(UpdateJobStateAction(
                    action_type="update_job_state",
                    job_input_file_id=job.input_file_id,
                    job_workflow_template=job.workflow_template,
                    new_status=new_status,
                    workflow_namespace=job.workflow_namespace,
                    workflow_name=job.workflow_name,
                ))

            # Need to launch workflow?
            if state == ReconcileState.pending and not job.workflow_name:
                input_file = input_files.get(job.input_file_id)
                if not input_file:
                    continue

                input_s3 = f"s3://{input_file.bucket}/{input_file.key}"

                # Resolve output path
                output_s3_file = session.get(S3File, job.output_file_id)
                if output_s3_file:
                    output_s3 = f"s3://{output_s3_file.bucket}/{output_s3_file.key}"
                else:
                    output_key = input_file.key.replace(
                        "benchmark_source_", "benchmark_output_"
                    )
                    output_s3 = f"s3://{input_file.bucket}/{output_key}"

                actions.append(LaunchWorkflowAction(
                    action_type="launch_workflow",
                    job_input_file_id=job.input_file_id,
                    job_workflow_template=job.workflow_template,
                    input_s3_file=input_s3,
                    output_s3_file=output_s3,
                ))

    return actions


def execute_reconciliation(
    engine,
    actions: list[ReconcileAction],
    api: client.CustomObjectsApi | None = None,
) -> None:
    """Execute a list of reconciliation actions.

    Args:
        engine: SQLAlchemy engine
        actions: List of actions to execute
        api: Optional K8s API client (will create if not provided)
    """
    if api is None:
        config.load_kube_config()
        api = client.CustomObjectsApi()

    with Session(engine) as session:
        for action in actions:
            match action:
                case LaunchWorkflowAction():
                    _execute_launch_workflow(session, api, action)

                case UpdateJobStateAction():
                    _execute_update_job_state(session, action)

        session.commit()


def _execute_launch_workflow(
    session: Session,
    api: client.CustomObjectsApi,
    action: LaunchWorkflowAction,
) -> None:
    """Execute a LaunchWorkflowAction."""
    import uuid

    workflow_name = (
        f"{action.job_workflow_template}-{action.job_input_file_id[:8]}-{str(uuid.uuid4())[:6]}"
    )

    workflow = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Workflow",
        "metadata": {
            "name": workflow_name,
            "namespace": action.namespace,
        },
        "spec": {
            "serviceAccountName": action.service_account,
            "workflowTemplateRef": {"name": action.job_workflow_template},
            "arguments": {
                "parameters": [
                    {"name": "input_s3_file", "value": action.input_s3_file},
                    {"name": "output_s3_file", "value": action.output_s3_file},
                ]
            },
        },
    }

    api.create_namespaced_custom_object(
        group="argoproj.io",
        version="v1alpha1",
        namespace=action.namespace,
        plural="workflows",
        body=workflow,
    )

    # Update job with workflow reference
    job = session.get(Job, (action.job_input_file_id, action.job_workflow_template))
    if job:
        job.workflow_namespace = action.namespace
        job.workflow_name = workflow_name
        job.status = "running"

    print(f"  -> Launched: {action.namespace}/{workflow_name}")


def _execute_update_job_state(
    session: Session,
    action: UpdateJobStateAction,
) -> None:
    """Execute an UpdateJobStateAction."""
    job = session.get(Job, (action.job_input_file_id, action.job_workflow_template))
    if job:
        job.status = action.new_status
        if action.workflow_namespace:
            job.workflow_namespace = action.workflow_namespace
        if action.workflow_name:
            job.workflow_name = action.workflow_name


def run_reconciliation(engine, dry_run: bool = False):
    """Run full reconciliation loop (plan + execute).

    Args:
        engine: SQLAlchemy engine
        dry_run: If True, only print plan without executing
    """
    print("Planning reconciliation...")
    actions = plan_reconciliation(engine)

    if not actions:
        print("No actions needed.")
        return

    print(f"\nPlanned {len(actions)} actions:")
    for i, action in enumerate(actions, 1):
        prefix = "[DRY] " if dry_run else ""
        print(f"  {i}. {prefix}{action}")

    if dry_run:
        print("\n[DRY RUN] No changes committed")
        return

    print("\nExecuting actions...")
    config.load_kube_config()
    api = client.CustomObjectsApi()
    execute_reconciliation(engine, actions, api)
    print("\nReconciliation complete.")
