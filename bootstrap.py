#!/usr/bin/env python3
"""Idempotent local setup for the Arr services. Uses only Python's standard library."""
import json
import os
import secrets
import sqlite3
import urllib.parse
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

SERVICES = {'radarr': (7878, 3), 'lidarr': (8686, 1), 'prowlarr': (9696, 1)}


def key(name):
    path = Path(name) / 'config/config.xml'
    for _ in range(90):
        if path.exists():
            try:
                value = ET.parse(path).findtext('.//ApiKey')
                if value:
                    return value
            except ET.ParseError:
                pass
        time.sleep(2)
    raise RuntimeError(f'{name}: API key non disponibile')


def call(name, route, method='GET', payload=None):
    port, version = SERVICES[name]
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        f'http://127.0.0.1:{port}/api/v{version}/{route}', data=data,
        method=method, headers={'X-Api-Key': key(name), 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read()
        return json.loads(body) if body else None


def ready(name):
    for _ in range(90):
        try:
            call(name, 'system/status')
            return
        except (urllib.error.URLError, TimeoutError, ValueError):
            time.sleep(2)
    raise RuntimeError(f'{name}: API non raggiungibile')


def field(record, name, value):
    for item in record['fields']:
        if item['name'] == name:
            item['value'] = value
            return
    raise RuntimeError(f'Campo API assente: {name}')


def ensure(name, route, implementation, display, values, extras=None):
    existing = next((x for x in call(name, route) if x.get('name') == display), None)
    if existing:
        record = existing
    else:
        record = next(x for x in call(name, route + '/schema') if x['implementation'] == implementation).copy()
    record['name'] = display
    for field_name, value in values.items():
        field(record, field_name, value)
    if extras:
        record.update(extras)
    call(name, route + (f"/{record['id']}" if existing else ''), 'PUT' if existing else 'POST', record)
    print(f'{name}: {display} configurato')


def root(name, path):
    if path not in [x['path'] for x in call(name, 'rootfolder')]:
        call(name, 'rootfolder', 'POST', {'path': path})
    print(f'{name}: root {path}')


def setup_arr(name, path, category):
    root(name, path)
    ensure(name, 'downloadclient', 'Transmission', 'Transmission',
           {'host': 'transmission', 'port': 9091, 'urlBase': '/transmission/',
            category: name}, {'enable': True})
    if name == 'lidarr':
        naming = call(name, 'config/naming')
        if not naming['renameTracks']:
            naming['renameTracks'] = True
            call(name, 'config/naming', 'PUT', naming)


def setup_prowlarr():
    existing = {x['name'] for x in call('prowlarr', 'indexer')}
    schema = call('prowlarr', 'indexer/schema')
    for label, definition in [('The Pirate Bay', 'thepiratebay'),
                              ('YTS', 'yts'), ('TorrentDownload', 'torrentdownload'),
                              ('Nyaa.si', 'nyaasi')]:
        if label in existing:
            continue
        template = next((x for x in schema if any(
            f['name'] == 'definitionFile' and f.get('value') == definition
            for f in x.get('fields', []))), None)
        if not template:
            print(f'Prowlarr: definizione {label} non disponibile')
            continue
        template['name'] = label
        template['enable'] = True
        try:
            call('prowlarr', 'indexer', 'POST', template)
            print(f'Prowlarr: indexer {label} aggiunto')
        except urllib.error.HTTPError as error:
            print(f'Prowlarr: {label} non aggiunto (HTTP {error.code}); configurarlo dalla UI')
    for name in ('radarr', 'lidarr'):
        ensure('prowlarr', 'applications', name.capitalize(), name.capitalize(),
               {'prowlarrUrl': 'http://prowlarr:9696',
                'baseUrl': f'http://{name}:{SERVICES[name][0]}', 'apiKey': key(name)},
               {'enable': True, 'syncLevel': 'fullSync'})
    # Indexer availability and legality vary; add desired sources in the Prowlarr UI.
    try:
        call('prowlarr', 'command', 'POST', {'name': 'ApplicationIndexerSync'})
    except urllib.error.HTTPError:
        pass



def jelly_call(path, method='GET', payload=None, token=None):
    data = None if payload is None else json.dumps(payload).encode()
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'MediaBrowser Client="mmedia-bootstrap", Device="host", DeviceId="mmedia-bootstrap", Version="1", Token="{token}"'
    request = urllib.request.Request('http://127.0.0.1:8080/' + path,
                                     data=data, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read()
        return json.loads(body) if body else None


def setup_jellyfin():
    for _ in range(90):
        try:
            info = jelly_call('System/Info/Public')
            break
        except urllib.error.URLError:
            time.sleep(2)
    else:
        raise RuntimeError('Jellyfin: API non raggiungibile')
    secret_dir = Path('secrets')
    secret_dir.mkdir(mode=0o700, exist_ok=True)
    credential = secret_dir / 'jellyfin-admin.txt'
    if not info['StartupWizardCompleted']:
        password = secrets.token_urlsafe(24)
        credential.write_text('Utente: admin\nPassword: ' + password + '\n')
        credential.chmod(0o600)
        jelly_call('Startup/Configuration', 'POST',
                   {'UICulture': 'it-IT', 'MetadataCountryCode': 'IT',
                    'PreferredMetadataLanguage': 'it'})
        jelly_call('Startup/FirstUser')
        jelly_call('Startup/User', 'POST', {'Name': 'admin', 'Password': password})
        jelly_call('Startup/RemoteAccess', 'POST',
                   {'EnableRemoteAccess': True, 'EnableAutomaticPortMapping': False})
        jelly_call('Startup/Complete', 'POST', {})
        print('Jellyfin: amministratore creato; credenziali in secrets/jellyfin-admin.txt')
    token_file = secret_dir / 'jellyfin-api-key'
    if token_file.exists():
        token = token_file.read_text().strip()
    elif credential.exists():
        password = credential.read_text().split('Password: ', 1)[1].strip()
        session = jelly_call('Users/AuthenticateByName', 'POST',
                             {'Username': 'admin', 'Pw': password})
        auth_token = session['AccessToken']
        query = urllib.parse.urlencode({'app': 'mmedia-bootstrap'})
        jelly_call('Auth/Keys?' + query, 'POST', {}, auth_token)
        keys = jelly_call('Auth/Keys', token=auth_token)['Items']
        token = next(x['AccessToken'] for x in keys if x['AppName'] == 'mmedia-bootstrap')
        token_file.write_text(token)
        token_file.chmod(0o600)
    else:
        # Migration of an already installed stack; do not reset its administrator.
        db = Path('config/data/jellyfin.db')
        if not db.exists():
            raise RuntimeError('Jellyfin già inizializzato: manca una chiave API in secrets/jellyfin-api-key')
        with sqlite3.connect(f'file:{db}?mode=ro', uri=True) as connection:
            row = connection.execute('SELECT AccessToken FROM ApiKeys LIMIT 1').fetchone()
        if not row:
            raise RuntimeError('Jellyfin: crea una chiave API e salvala in secrets/jellyfin-api-key')
        token = row[0]
        token_file.write_text(token)
        token_file.chmod(0o600)
    folders = jelly_call('Library/VirtualFolders', token=token)
    for name, kind, path in [('Film', 'movies', '/media/movies'),
                             ('Musica', 'music', '/media/music')]:
        if not any(path in x.get('Locations', []) for x in folders):
            query = urllib.parse.urlencode({'name': name, 'collectionType': kind,
                                            'paths': path, 'refreshLibrary': 'true'})
            jelly_call('Library/VirtualFolders?' + query, 'POST',
                       {'LibraryOptions': {'PathInfos': [{'Path': path}]}}, token)
        print(f'Jellyfin: libreria {name} {path}')
    return token


def setup_notifications(token):
    for name in ('radarr', 'lidarr'):
        extras = {'onDownload': True, 'onUpgrade': True} if name == 'radarr' else {'onReleaseImport': True, 'onUpgrade': True}
        ensure(name, 'notification', 'MediaBrowser', 'Jellyfin',
               {'host': 'jellyfin', 'port': 8096, 'apiKey': token, 'updateLibrary': True}, extras)

def main():
    for name in SERVICES:
        ready(name)
    setup_arr('radarr', '/media/movies', 'movieCategory')
    setup_arr('lidarr', '/media/music', 'musicCategory')
    setup_prowlarr()
    token = setup_jellyfin()
    setup_notifications(token)
    print('Bootstrap completato. Controlla gli indexer in Prowlarr.')


if __name__ == '__main__':
    main()
