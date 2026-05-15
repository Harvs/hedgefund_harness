#!/usr/bin/env bash
set -euo pipefail

REGISTRY="${REGISTRY:-192.168.0.8:5000}"
IMAGE_NAME="${IMAGE_NAME:-hedgefund-harness}"
VERSION="${VERSION:-0.2.5}"
TARGET="${TARGET:-app}"
PLATFORM="${PLATFORM:-}"
PUSH_LATEST="${PUSH_LATEST:-1}"

IMAGE="${REGISTRY}/${IMAGE_NAME}"
VERSION_TAG="${IMAGE}:${VERSION}"
LATEST_TAG="${IMAGE}:latest"

BUILD_ARGS=(--target "${TARGET}" -t "${VERSION_TAG}")

if [[ "${PUSH_LATEST}" == "1" || "${PUSH_LATEST}" == "true" ]]; then
  BUILD_ARGS+=(-t "${LATEST_TAG}")
fi

if [[ -n "${PLATFORM}" ]]; then
  BUILD_ARGS+=(--platform "${PLATFORM}")
fi

echo "Building ${VERSION_TAG} from target '${TARGET}'..."
docker build "${BUILD_ARGS[@]}" .

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
