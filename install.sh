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
if [ -e media ] || [ -e downloads ]; then
  echo "Layout precedente rilevato: esegui prima ./migrate-data-layout.sh" >&2
  exit 1
fi
mkdir -p data/media/movies data/media/music data/media/tvshows
mkdir -p data/downloads/complete data/downloads/incomplete
mkdir -p qbittorrent/config/qBittorrent jackett/config
chmod 775 data data/media data/media/movies data/media/music data/media/tvshows \
  data/downloads data/downloads/complete data/downloads/incomplete \
  data/downloads/complete

if [ ! -f qbittorrent/config/qBittorrent/qBittorrent.conf ]; then
  cp qbittorrent/qBittorrent.conf qbittorrent/config/qBittorrent/qBittorrent.conf
fi

printf 'Directory preparate. Avvia con ./go.sh\n'
