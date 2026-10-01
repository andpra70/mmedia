#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

server_config=jackett/config/Jackett/ServerConfig.json
plugin_config=qbittorrent/config/qBittorrent/nova3/engines/jackett.json
api_key=""

if [ -f "$plugin_config" ]; then
  api_key=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("api_key", ""))' "$plugin_config" 2>/dev/null || true)
  if [ -n "$api_key" ] && ! curl -fsS --max-time 10 \
      "http://127.0.0.1:51007/api/v2.0/indexers/all/results/torznab/api?apikey=${api_key}&t=caps" \
      >/dev/null; then
    api_key=""
  fi
fi

for _ in $(seq 1 60); do
  [ -n "$api_key" ] && break
  if [ -f "$server_config" ]; then
    api_key=$(sed -n 's/.*"APIKey"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$server_config" | head -n 1)
    if [ -n "$api_key" ]; then
      break
    fi
  fi
  sleep 1
done

if [ -z "$api_key" ]; then
  echo "API key di Jackett non disponibile dopo 60 secondi" >&2
  exit 1
fi

mkdir -p "$(dirname "$plugin_config")"
umask 077
printf '%s\n' \
  '{' \
  "    \"api_key\": \"$api_key\"," \
  '    "thread_count": 1,' \
  '    "tracker_first": false,' \
  '    "url": "http://jackett:9117"' \
  '}' > "$plugin_config"

echo "Plugin di ricerca Jackett configurato in qBittorrent"
