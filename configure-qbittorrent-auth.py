#!/usr/bin/env python3
"""Synchronize qBittorrent WebUI credentials with the local .env file."""
import base64
import hashlib
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "qbittorrent/config/qBittorrent/qBittorrent.conf"


def compose_credentials():
    command = ["docker", "compose", "--profile", "tools", "config", "--format", "json"]
    output = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    import json

    environment = json.loads(output.stdout)["services"]["bootstrap"]["environment"]
    username = str(environment.get("QBITTORRENT_USERNAME", "admin")).strip()
    password = str(environment.get("QBITTORRENT_PASSWORD", ""))
    if not username or not password:
        raise SystemExit(
            "Imposta QBITTORRENT_USERNAME e QBITTORRENT_PASSWORD nel file .env"
        )
    return username, password


def set_preference(text, name, value):
    line = f"WebUI\\{name}={value}"
    pattern = rf"(?m)^WebUI\\{re.escape(name)}=.*$"
    if re.search(pattern, text):
        return re.sub(pattern, lambda _: line, text)
    section = re.search(r"(?m)^\[Preferences\]\s*$", text)
    if not section:
        raise SystemExit(f"Sezione [Preferences] assente in {CONFIG}")
    position = section.end()
    return text[:position] + "\n" + line + text[position:]


def main():
    username, password = compose_credentials()
    if not CONFIG.exists():
        raise SystemExit(f"Configurazione qBittorrent assente: {CONFIG}")

    subprocess.run(["docker", "compose", "stop", "qbittorrent"], cwd=ROOT, check=True)
    try:
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha512", password.encode(), salt, 100_000)
        encoded = '"@ByteArray({}:{})"'.format(
            base64.b64encode(salt).decode(), base64.b64encode(digest).decode()
        )
        text = CONFIG.read_text()
        text = set_preference(text, "Username", username)
        text = set_preference(text, "Password_PBKDF2", encoded)
        temporary = CONFIG.with_suffix(".conf.tmp")
        temporary.write_text(text)
        os.replace(temporary, CONFIG)
    finally:
        subprocess.run(["docker", "compose", "up", "-d", "qbittorrent"], cwd=ROOT, check=True)

    print("Credenziali WebUI di qBittorrent allineate a .env")


if __name__ == "__main__":
    main()
