#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"
./install.sh
docker compose up -d --remove-orphans
docker compose --profile tools run --rm --no-deps bootstrap

urls=(
  http://localhost:51000/
  http://localhost:51001/
  http://localhost:51002/
  http://localhost:51003/
  http://localhost:51004/transmission/web/
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
