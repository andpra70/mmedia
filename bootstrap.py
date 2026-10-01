#!/usr/bin/env python3
"""Idempotent local setup for the Arr services. Uses only Python's standard library."""
import http.client
import copy
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

SERVICES = {'radarr': (51001, 3), 'lidarr': (51002, 1), 'prowlarr': (51003, 1)}
INTERNAL_PORTS = {'radarr': 7878, 'lidarr': 8686, 'prowlarr': 9696}


def qbittorrent_credentials():
    username = os.environ.get('QBITTORRENT_USERNAME', 'admin').strip()
    password = os.environ.get('QBITTORRENT_PASSWORD', '')
    if not username or not password:
        raise RuntimeError(
            'qBittorrent: imposta QBITTORRENT_USERNAME e QBITTORRENT_PASSWORD '
            'nel file .env; la password deve coincidere con quella della WebUI')
    return username, password


def check_qbittorrent_login(username, password):
    data = urllib.parse.urlencode({'username': username, 'password': password}).encode()
    request = urllib.request.Request(
        'http://127.0.0.1:51006/api/v2/auth/login', data=data, method='POST',
        headers={'Referer': 'http://127.0.0.1:51006/'})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status = response.status
            result = response.read().decode('utf-8', errors='replace').strip()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError(
            f'qBittorrent: WebUI non raggiungibile sulla porta 51006 ({error})') from error
    # qBittorrent <= 5.2.3 returned ``200 Ok.``; 5.2.4 returns an empty 204.
    if not (result == 'Ok.' or (status == 204 and not result)):
        raise RuntimeError(
            'qBittorrent: accesso rifiutato. Imposta una password permanente nella '
            'WebUI e riporta esattamente le stesse credenziali nel file .env')


def setup_qbittorrent_client(name, category_field, category):
    username, password = qbittorrent_credentials()
    check_qbittorrent_login(username, password)
    ensure(name, 'downloadclient', 'QBittorrent', 'qBittorrent',
           {'host': 'qbittorrent', 'port': 51006, 'useSsl': False,
            'urlBase': '', 'username': username, 'password': password,
            category_field: category}, {'enable': True})

    # Le vecchie installazioni configuravano Transmission. Disabilitarlo evita
    # che Arr continui a sceglierlo al posto di qBittorrent.
    for client in call(name, 'downloadclient'):
        if client.get('name') == 'Transmission' and client.get('enable', True):
            client['enable'] = False
            call(name, f"downloadclient/{client['id']}", 'PUT', client)
            print(f'{name}: Transmission disabilitato')


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


def wait_for(label, probe):
    """Wait for services while their proxy and API are starting."""
    deadline = time.monotonic() + 300
    last_error = None
    while time.monotonic() < deadline:
        try:
            return probe()
        except (urllib.error.URLError, http.client.RemoteDisconnected,
                http.client.BadStatusLine, ConnectionResetError,
                BrokenPipeError, TimeoutError, ValueError) as error:
            if isinstance(error, urllib.error.HTTPError) and error.code not in (429, 502, 503, 504):
                raise
            last_error = error
            time.sleep(2)
    raise RuntimeError(f'{label}: API non raggiungibile dopo 5 minuti ({last_error})')


def ready(name):
    wait_for(name, lambda: call(name, 'system/status'))
    print(f'{name}: API pronta', flush=True)


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
    target = route + (f"/{record['id']}" if existing else '')
    method = 'PUT' if existing else 'POST'
    try:
        call(name, target, method, record)
    except urllib.error.HTTPError as error:
        detail = error.read().decode('utf-8', errors='replace')[:2000]
        raise RuntimeError(
            f'{name}: configurazione {display} rifiutata (HTTP {error.code}): {detail}') from error
    print(f'{name}: {display} configurato')


def root(name, path):
    if path not in [x['path'] for x in call(name, 'rootfolder')]:
        payload = {'path': path}
        if name == 'lidarr':
            quality = call(name, 'qualityprofile')
            metadata = call(name, 'metadataprofile')
            if not quality or not metadata:
                raise RuntimeError('Lidarr: profili qualità o metadati non disponibili')
            payload.update({'name': 'Musica',
                            'defaultQualityProfileId': quality[0]['id'],
                            'defaultMetadataProfileId': metadata[0]['id'],
                            'defaultTags': []})
        try:
            call(name, 'rootfolder', 'POST', payload)
        except urllib.error.HTTPError as error:
            detail = error.read().decode('utf-8', errors='replace')[:1200]
            raise RuntimeError(f'{name}: impossibile creare {path} (HTTP {error.code}): {detail}') from error
    print(f'{name}: root {path}')


def migrate_library_paths(name, old_root, new_root):
    route = 'movie' if name == 'radarr' else 'artist'
    changed = 0
    for item in call(name, route):
        old_path = item.get('path', '')
        if old_path == old_root or old_path.startswith(old_root + '/'):
            item['path'] = new_root + old_path[len(old_root):]
            call(name, f"{route}/{item['id']}?moveFiles=false", 'PUT', item)
            changed += 1
    if changed:
        print(f'{name}: migrati {changed} percorsi da {old_root} a {new_root}')
    old = next((x for x in call(name, 'rootfolder') if x['path'] == old_root), None)
    if old:
        call(name, f"rootfolder/{old['id']}", 'DELETE')
        print(f'{name}: rimossa root obsoleta {old_root}')


def migrate_collection_paths(old_root, new_root):
    changed = 0
    for collection in call('radarr', 'collection'):
        if collection.get('rootFolderPath') == old_root:
            collection['rootFolderPath'] = new_root
            call('radarr', f"collection/{collection['id']}", 'PUT', collection)
            changed += 1
    if changed:
        print(f'radarr: migrate {changed} collezioni da {old_root} a {new_root}')


def setup_arr(name, path, category):
    root(name, path)
    old_path = '/media/movies' if name == 'radarr' else '/media/music'
    migrate_library_paths(name, old_path, path)
    if name == 'radarr':
        migrate_collection_paths(old_path, path)
    setup_qbittorrent_client(name, category, name)
    media = call(name, 'config/mediamanagement')
    if 'copyUsingHardlinks' in media:
        media['copyUsingHardlinks'] = True
        call(name, 'config/mediamanagement', 'PUT', media)
    downloads = call(name, 'config/downloadclient')
    downloads['enableCompletedDownloadHandling'] = True
    if 'removeCompletedDownloads' in downloads:
        downloads['removeCompletedDownloads'] = True
    call(name, 'config/downloadclient', 'PUT', downloads)
    print(f'{name}: hardlink, import completati e rimozione download abilitati')
    if name == 'lidarr':
        naming = call(name, 'config/naming')
        if not naming['renameTracks']:
            naming['renameTracks'] = True
            call(name, 'config/naming', 'PUT', naming)


def setup_prowlarr():
    existing = {x['name'] for x in call('prowlarr', 'indexer')}
    schema = call('prowlarr', 'indexer/schema')
    profiles = call('prowlarr', 'appprofile')
    if not profiles:
        raise RuntimeError('Prowlarr: nessun profilo applicativo disponibile')

    # Il catalogo cambia a ogni aggiornamento di Prowlarr. Selezionarlo a runtime
    # evita una lista statica destinata a diventare incompleta o obsoleta.
    public_torrents = sorted(
        (x for x in schema
         if str(x.get('protocol', '')).lower() == 'torrent'
         and str(x.get('privacy', '')).lower() == 'public'),
        key=lambda x: x.get('name', '').casefold())
    added = 0
    skipped = 0
    failed = 0
    for source in public_torrents:
        label = source.get('name')
        if not label:
            continue
        if label in existing:
            skipped += 1
            continue
        template = copy.deepcopy(source)
        template['name'] = label
        template['enable'] = True
        template['appProfileId'] = profiles[0]['id']
        try:
            call('prowlarr', 'indexer', 'POST', template)
            existing.add(label)
            added += 1
            print(f'Prowlarr: indexer {label} aggiunto')
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            failed += 1
            reason = f'HTTP {error.code}' if isinstance(error, urllib.error.HTTPError) else str(error)
            print(f'Prowlarr: {label} non aggiunto ({reason})')
    print(f'Prowlarr: indexer pubblici: {added} aggiunti, {skipped} già presenti, {failed} non disponibili')

    setup_qbittorrent_client('prowlarr', 'category', 'prowlarr')

    for name in ('radarr', 'lidarr'):
        ensure('prowlarr', 'applications', name.capitalize(), name.capitalize(),
               {'prowlarrUrl': 'http://prowlarr:9696',
                'baseUrl': f'http://{name}:{INTERNAL_PORTS[name]}', 'apiKey': key(name)},
               {'enable': True, 'syncLevel': 'fullSync'})
    # Indexer availability and legality vary; add desired sources in the Prowlarr UI.
    try:
        call('prowlarr', 'command', 'POST', {'name': 'ApplicationIndexerSync'})
    except urllib.error.HTTPError:
        pass



def jelly_call(path, method='GET', payload=None, token=None):
    data = None if payload is None else json.dumps(payload).encode()
    authorization = 'MediaBrowser Client="mmedia-bootstrap", Device="host", DeviceId="mmedia-bootstrap", Version="1"'
    if token:
        authorization += f', Token="{token}"'
    headers = {'Content-Type': 'application/json', 'Authorization': authorization}
    request = urllib.request.Request('http://127.0.0.1:51000/' + path,
                                     data=data, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read()
        return json.loads(body) if body else None


def setup_jellyfin():
    info = wait_for('Jellyfin', lambda: jelly_call('System/Info/Public'))
    print('Jellyfin: API pronta', flush=True)
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
        db = Path('jellyfin/config/data/jellyfin.db')
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
    setup_jellyfin()
    print('Bootstrap Jellyfin completato.')


if __name__ == '__main__':
    main()
