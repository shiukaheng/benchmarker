"""Reconciliation actions - dataclasses representing operations to perform."""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class LaunchWorkflowAction:
    """Action to launch a new Argo workflow for a job."""

    action_type: Literal["launch_workflow"]
    job_input_file_id: str
    job_workflow_template: str
    input_s3_file: str
    output_s3_file: str
    namespace: str = "material-gaussians"
    service_account: str = "product-apps-workflow"

    def __str__(self) -> str:
        return (
            f"LaunchWorkflow({self.job_input_file_id[:8]}, "
            f"template={self.job_workflow_template}, "
            f"input={self.input_s3_file.split('/')[-1]})"
        )


@dataclass(frozen=True)
class UpdateJobStateAction:
    """Action to update a job's state in the database."""

    action_type: Literal["update_job_state"]
    job_input_file_id: str
    job_workflow_template: str
    new_status: str  # pending, running, succeeded, failed
    workflow_namespace: str | None = None
    workflow_name: str | None = None

    def __str__(self) -> str:
        wf_ref = f" ({self.workflow_namespace}/{self.workflow_name})" if self.workflow_name else ""
        return f"UpdateJobState({self.job_input_file_id[:8]} -> {self.new_status}{wf_ref})"


# Union type for all actions
ReconcileAction = LaunchWorkflowAction | UpdateJobStateAction
