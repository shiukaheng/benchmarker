from kubernetes import client, config
import uuid

config.load_kube_config()  # or load_incluster_config()
api = client.CustomObjectsApi()

# All datasets in the benchmark source bucket
DATASETS = [
    "Blanket_Silk",
    "Burberry_Brown",
    "Burberry_Cream_GoldChain",
    "Car_Tyre",
    "Chair_Detailed_GoldEmbroidery",
    "DebugScene_Xrite_Jeans",
    "DebugScene_Xrite_Jeans_1m",
    "GuitarAmpYellowVintage",
    # "GuitarAmp_Gibsson_OldStripes",  # Skip - already reconstructed
    "HackneyMuseum_HelmetSpike",
    "Oil_Painting_AbstractSwirl",
    "Oil_Painting_BeachScene",
    "Petrol_Can_Green",
    "PianoStool_v2",
    "Piano_Upright",
    "Plastic_Container_Blue",
    "WateringCan_Galvanized",
    "antiqueCupboardLow_A",
    "basketCase",
    "chestSriLankan",
]

BUCKET_SOURCE = "material-gaussians-data-dev"
BUCKET_OUTPUT = "material-gaussians-data-dev"


def submit_pipeline_workflow(
    dataset_name: str,
    namespace: str = "material-gaussians",
    service_account: str = "product-apps-workflow",
    template_name: str = "mgs-pipeline",
) -> dict:
    """Submit a single pipeline workflow for a dataset.

    Args:
        dataset_name: Name of the dataset (without .zip extension)
        namespace: Kubernetes namespace
        service_account: Service account for the workflow
        template_name: Name of the WorkflowTemplate to use

    Returns:
        The created workflow object from the API
    """
    input_s3_file = f"s3://{BUCKET_SOURCE}/benchmark_source_jpeg_datasets/{dataset_name}.zip"
    output_s3_file = f"s3://{BUCKET_OUTPUT}/benchmark_preprocessed_jpeg_datasets/{dataset_name}.zip"

    workflow = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Workflow",
        "metadata": {
            "name": f"mgs-pipeline-{dataset_name.lower().replace('_', '-')}-{str(uuid.uuid4())[:6]}",
            "namespace": namespace,
        },
        "spec": {
            "serviceAccountName": service_account,
            "workflowTemplateRef": {"name": template_name},
            "arguments": {
                "parameters": [
                    {"name": "input_s3_file", "value": input_s3_file},
                    {"name": "output_s3_file", "value": output_s3_file},
                ]
            },
        },
    }

    result = api.create_namespaced_custom_object(
        group="argoproj.io",
        version="v1alpha1",
        namespace=namespace,
        plural="workflows",
        body=workflow,
    )
    return result


def submit_all_workflows(datasets: list[str] | None = None) -> list[dict]:
    """Submit workflows for all datasets (or a subset).

    Args:
        datasets: List of dataset names to process. If None, uses all DATASETS.

    Returns:
        List of created workflow objects
    """
    if datasets is None:
        datasets = DATASETS

    results = []
    for dataset in datasets:
        print(f"Submitting workflow for: {dataset}")
        result = submit_pipeline_workflow(dataset)
        results.append(result)
        print(f"  -> Submitted: {result['metadata']['name']}")

    return results


if __name__ == "__main__":
    print(f"Submitting {len(DATASETS)} workflows...")
    print(f"Skipping: GuitarAmp_Gibsson_OldStripes (already reconstructed)")
    print()

    workflows = submit_all_workflows()

    print()
    print(f"Total submitted: {len(workflows)}")
    print("Workflow names:")
    for wf in workflows:
        print(f"  - {wf['metadata']['name']}")
