#!/usr/bin/env sh
set -eu

docker compose run --rm api pytest
docker compose run --rm frontend npm run test
