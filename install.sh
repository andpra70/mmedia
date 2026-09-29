#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"
command -v docker >/dev/null || { echo "Docker richiesto" >&2; exit 1; }
docker compose version >/dev/null || { echo "Docker Compose richiesto" >&2; exit 1; }
if [ "$(id -u):$(id -g)" != "1000:1000" ]; then
  echo "Questo stack richiede UID/GID 1000:1000" >&2; exit 1
fi
mkdir -p config/data cache render-cache
mkdir -p media/movies media/music media/tvshows
mkdir -p downloads/complete/lidarr downloads/complete/radarr downloads/incomplete
mkdir -p transmission/config prowlarr/config radarr/config lidarr/config wireguard/config
chmod 700 wireguard/config
chmod 775 media media/movies media/music media/tvshows downloads downloads/complete downloads/incomplete downloads/complete/lidarr downloads/complete/radarr

if [ ! -f transmission/config/settings.json ]; then
  cp transmission/settings.json transmission/config/settings.json
fi

printf 'Directory preparate. Avvia con ./go.sh\n'
