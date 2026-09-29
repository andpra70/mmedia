#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"
./install.sh
docker compose up -d
docker compose --profile tools run --rm --no-deps bootstrap

urls=(
  http://localhost:8080/
  http://localhost:7878/
  http://localhost:8686/
  http://localhost:9696/
  http://localhost:9091/transmission/web/
)

if command -v google-chrome >/dev/null 2>&1; then
  google-chrome --new-window "${urls[@]}" >/dev/null 2>&1 &
elif command -v xdg-open >/dev/null 2>&1; then
  for url in "${urls[@]}"; do
    xdg-open "$url" >/dev/null 2>&1 &
  done
else
  printf 'Interfacce web:\n%s\n' "${urls[@]}"
fi
