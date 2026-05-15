#!/usr/bin/env bash
set -euo pipefail

REGISTRY="${REGISTRY:-192.168.0.8:5000}"
IMAGE_NAME="${IMAGE_NAME:-hedgefund-harness}"
TARGET="${TARGET:-app}"
PLATFORM="${PLATFORM:-}"
PUSH_LATEST="${PUSH_LATEST:-1}"

IMAGE="${REGISTRY}/${IMAGE_NAME}"
LATEST_TAG="${IMAGE}:latest"
TEMP_TAG="${IMAGE}:build-${$}"

BUILD_ARGS=(--target "${TARGET}" -t "${TEMP_TAG}")

if [[ -n "${PLATFORM}" ]]; then
  BUILD_ARGS+=(--platform "${PLATFORM}")
fi

echo "Building ${TEMP_TAG} from target '${TARGET}'..."
docker build "${BUILD_ARGS[@]}" .

IMAGE_ID="$(docker image inspect --format '{{.Id}}' "${TEMP_TAG}")"
HASH_VERSION="${IMAGE_ID#sha256:}"
HASH_VERSION="${HASH_VERSION:0:12}"
VERSION="${VERSION:-${HASH_VERSION}}"
VERSION_TAG="${IMAGE}:${VERSION}"

echo "Tagging ${TEMP_TAG} as ${VERSION_TAG}..."
docker tag "${TEMP_TAG}" "${VERSION_TAG}"

if [[ "${PUSH_LATEST}" == "1" || "${PUSH_LATEST}" == "true" ]]; then
  echo "Tagging ${TEMP_TAG} as ${LATEST_TAG}..."
  docker tag "${TEMP_TAG}" "${LATEST_TAG}"
fi

echo "Pushing ${VERSION_TAG}..."
docker push "${VERSION_TAG}"

if [[ "${PUSH_LATEST}" == "1" || "${PUSH_LATEST}" == "true" ]]; then
  echo "Pushing ${LATEST_TAG}..."
  docker push "${LATEST_TAG}"
fi

echo "Done. Published:"
echo "  ${VERSION_TAG}"
if [[ "${PUSH_LATEST}" == "1" || "${PUSH_LATEST}" == "true" ]]; then
  echo "  ${LATEST_TAG}"
fi
