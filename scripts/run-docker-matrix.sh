#!/usr/bin/env bash
set -euo pipefail

versions="${PYTHON_VERSIONS:-3.10 3.11 3.12 3.13 3.14}"

for version in ${versions}; do
  image="code-agnostic-test:py${version//./}"
  echo "==> Building Python ${version} test image"
  docker build \
    --build-arg "PYTHON_VERSION=${version}" \
    -f docker/test.Dockerfile \
    -t "${image}" \
    .

  echo "==> Running tests on Python ${version}"
  docker run --rm "${image}" "$@"
done
