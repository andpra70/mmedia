#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

command -v docker >/dev/null || { echo "Docker richiesto" >&2; exit 1; }
docker compose version >/dev/null || { echo "Docker Compose richiesto" >&2; exit 1; }
command -v python3 >/dev/null || { echo "Python 3 richiesto per aggiornare la configurazione esistente" >&2; exit 1; }

for source in media downloads; do
  if [ -e "$source" ] && [ -e "data/$source" ]; then
    echo "Migrazione ambigua: esistono sia $source sia data/$source" >&2
    exit 1
  fi
done

echo "Arresto dello stack..."
docker compose down --remove-orphans

mkdir -p data
for source in media downloads; do
  if [ -e "$source" ]; then
    mv "$source" "data/$source"
    echo "Spostato $source in data/$source"
  fi
done

mkdir -p data/media/movies data/media/music data/media/tvshows
mkdir -p data/downloads/complete/radarr data/downloads/complete/lidarr data/downloads/incomplete
chmod 775 data data/media data/media/movies data/media/music data/media/tvshows \
  data/downloads data/downloads/complete data/downloads/incomplete \
  data/downloads/complete/radarr data/downloads/complete/lidarr

if [ -f transmission/config/settings.json ]; then
  python3 - transmission/config/settings.json <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
settings = json.loads(path.read_text())
settings.update({
    "download-dir": "/data/downloads/complete",
    "incomplete-dir": "/data/downloads/incomplete",
    "incomplete-dir-enabled": True,
    "ratio-limit": 0,
    "ratio-limit-enabled": True,
})
path.write_text(json.dumps(settings, indent=4, sort_keys=True) + "\n")
PY
  echo "Transmission configurato per fermarsi a rapporto 0"
fi

if [ -f qbittorrent/config/qBittorrent/qBittorrent.conf ]; then
  python3 - qbittorrent/config/qBittorrent/qBittorrent.conf <<'PY'
import configparser
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
config = configparser.RawConfigParser()
config.optionxform = str
config.read(path)
for section in ("BitTorrent", "Preferences"):
    if not config.has_section(section):
        config.add_section(section)
config.set("BitTorrent", r"Session\DefaultSavePath", "/data/downloads/complete")
config.set("BitTorrent", r"Session\TempPath", "/data/downloads/incomplete")
config.set("BitTorrent", r"Session\TempPathEnabled", "true")
config.set("BitTorrent", r"Session\GlobalMaxRatio", "0")
config.set("BitTorrent", r"Session\MaxRatioAction", "0")
config.set("Preferences", r"Downloads\SavePath", "/data/downloads/complete")
config.set("Preferences", r"Downloads\TempPath", "/data/downloads/incomplete")
config.set("Preferences", r"Downloads\TempPathEnabled", "true")
with path.open("w") as stream:
    config.write(stream, space_around_delimiters=False)
PY
  echo "qBittorrent configurato per fermarsi a rapporto 0"
fi

# Le configurazioni persistenti vengono conservate. install.sh crea soltanto quelle mancanti.
./install.sh

echo "Avvio dello stack e applicazione della configurazione..."
docker compose up -d --remove-orphans
./configure-qbittorrent-jackett.sh
docker compose --profile tools run --rm --no-deps bootstrap

echo "Migrazione completata. Stato dei servizi:"
docker compose ps
