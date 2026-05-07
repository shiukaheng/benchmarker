from kubernetes import client, config
import uuid

config.load_kube_config()  # or load_incluster_config()
api = client.CustomObjectsApi()

workflow = {
    "apiVersion": "argoproj.io/v1alpha1",
    "kind": "Workflow",
    "metadata": {"name": f"mgs-pipeline-run-{str(uuid.uuid4())[:8]}", "namespace": "material-gaussians"},
    "spec": {
        "serviceAccountName": "product-apps-workflow",
        "workflowTemplateRef": {"name": "mgs-pipeline"},
        "arguments": {
            "parameters": [
                {
                    "name": "input_s3_file",
                    "value": "s3://material-gaussians-data-dev/benchmark_source_jpeg_datasets/GuitarAmp_Gibsson_OldStripes.zip"
                },
                {
                    "name": "output_s3_file",
                    "value": "s3://material-gaussians-data-dev/benchmark_preprocessed_jpeg_datasets/GuitarAmp_Gibsson_OldStripes.zip"
                }
            ]
        }
    },
}

result = api.create_namespaced_custom_object(
    group="argoproj.io",
    version="v1alpha1",
    namespace="material-gaussians",
    plural="workflows",
    body=workflow,
)
print(f"Submitted: {result['metadata']['name']}")
