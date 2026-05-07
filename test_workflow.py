from kubernetes import client, config
import uuid

config.load_kube_config()  # or load_incluster_config()
api = client.CustomObjectsApi()
workflow = {
    "apiVersion": "argoproj.io/v1alpha1",
    "kind": "Workflow",
    "metadata": {"name": f"hello-run-{str(uuid.uuid4())[:8]}", "namespace": "material-gaussians"},
    "spec": {
        "serviceAccountName": "product-apps-workflow",
        "workflowTemplateRef": {"name": "hello-template"}
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