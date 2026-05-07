#!/bin/bash
# Tag existing material-gaussians-latest images with benchmark-latest

REGION="eu-west-2"
ACCOUNT="223952452436"

REPOS=(
    "m-xr/material-gaussians-mgs-normalizer"
    "m-xr/material-gaussians-sfm"
    "m-xr/material-gaussians-postprocess-sfm"
)

for REPO in "${REPOS[@]}"; do
    echo "Tagging $REPO..."

    # Get the manifest of the existing material-gaussians-latest tag
    MANIFEST=$(aws ecr batch-get-image \
        --repository-name "$REPO" \
        --region "$REGION" \
        --image-ids imageTag=material-gaussians-latest \
        --query 'images[0].imageManifest' \
        --output text 2>/dev/null)

    if [ -z "$MANIFEST" ] || [ "$MANIFEST" == "None" ]; then
        echo "  ERROR: Could not find material-gaussians-latest tag for $REPO"
        continue
    fi

    # Put the new benchmark-latest tag with the same manifest
    aws ecr put-image \
        --repository-name "$REPO" \
        --region "$REGION" \
        --image-tag benchmark-latest \
        --image-manifest "$MANIFEST" \
        --output text >/dev/null 2>&1

    if [ $? -eq 0 ]; then
        echo "  SUCCESS: Tagged $REPO:benchmark-latest"
    else
        echo "  ERROR: Failed to tag $REPO"
    fi
done

echo "Done!"
