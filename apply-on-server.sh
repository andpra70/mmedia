#!/bin/bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Uso: $0 /percorso/remoto/mmedia" >&2
  exit 1
fi

remote_dir=$1
printf -v quoted_remote_dir '%q' "$remote_dir"

ssh -t server "cd $quoted_remote_dir && git pull --ff-only && ./migrate-data-layout.sh"
