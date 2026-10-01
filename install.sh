#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"
command -v docker >/dev/null || { echo "Docker richiesto" >&2; exit 1; }
docker compose version >/dev/null || { echo "Docker Compose richiesto" >&2; exit 1; }
if [ "$(id -u):$(id -g)" != "1000:1000" ]; then
  echo "Questo stack richiede UID/GID 1000:1000" >&2; exit 1
fi
# Migra automaticamente i vecchi dati Jellyfin; non unire directory ambigue.
legacy=0
for part in config cache render-cache; do
  if [ -e "$part" ]; then
    if [ -e "jellyfin/$part" ]; then
      echo "Migrazione Jellyfin ambigua: esistono $part e jellyfin/$part" >&2
      exit 1
    fi
    legacy=1
  fi
done
if [ "$legacy" -eq 1 ]; then
  docker compose stop jellyfin
  mkdir -p jellyfin
  for part in config cache render-cache; do
    if [ -e "$part" ]; then
      mv "$part" "jellyfin/$part"
    fi
  done
  echo "Dati Jellyfin migrati in jellyfin/"
fi
mkdir -p jellyfin/config/data jellyfin/cache jellyfin/render-cache
mkdir -p media/movies media/music media/tvshows
mkdir -p downloads/complete/lidarr downloads/complete/radarr downloads/incomplete
mkdir -p transmission/config utorrent/settings qbittorrent/config/qBittorrent jackett/config prowlarr/config radarr/config lidarr/config
chmod 775 media media/movies media/music media/tvshows downloads downloads/complete downloads/incomplete downloads/complete/lidarr downloads/complete/radarr

if [ ! -f transmission/config/settings.json ]; then
  cp transmission/settings.json transmission/config/settings.json
fi

if [ ! -f qbittorrent/config/qBittorrent/qBittorrent.conf ]; then
  cp qbittorrent/qBittorrent.conf qbittorrent/config/qBittorrent/qBittorrent.conf
fi

printf 'Directory preparate. Avvia con ./go.sh\n'
