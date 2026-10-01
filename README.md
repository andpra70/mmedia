# mmedia: Jellyfin, torrent e libreria multimediale

Questo stack usa **Jellyfin** per riprodurre, **Prowlarr** e **Jackett** per gestire gli indexer, **Radarr** per i film, **Lidarr** per la musica e **Transmission**, **uTorrent** o **qBittorrent** per scaricare.

Usa soltanto torrent e contenuti che hai il diritto di scaricare e condividere.

## Preparazione e avvio

Servono Docker Engine con `docker compose` e un utente autorizzato a usare Docker. I servizi che scrivono file sono configurati con UID e GID `1000`; controlla con `id -u` e `id -g` che corrispondano al tuo utente. In caso contrario, modifica UID/GID nel Compose e i permessi delle directory.

```bash
./install.sh
./go.sh
```

`install.sh` crea le directory e prepara le impostazioni iniziali dei client torrent. `go.sh` avvia i container e apre le otto interfacce nel browser. I dati Jellyfin sono sotto `jellyfin/`; `install.sh` migra automaticamente le vecchie directory `config/`, `cache/` e `render-cache/` se presenti. Per arrestare: `docker compose down`. Per controllare: `docker compose ps` e `docker compose logs -f NOME_SERVIZIO`.

Se aggiorni una vecchia installazione, `go.sh` rimuove il container WireGuard ormai orfano. L'eventuale directory locale `wireguard/` non viene cancellata automaticamente perché contiene chiavi private: dopo avere verificato che non ti serva più, eliminala manualmente con attenzione.

### Interfacce web

| Applicazione | URL locale | Uso |
| --- | --- | --- |
| Jellyfin | [http://localhost:51000/](http://localhost:51000/) | Guarda film e ascolta musica |
| Radarr | [http://localhost:51001/](http://localhost:51001/) | Cerca e gestisce film |
| Lidarr | [http://localhost:51002/](http://localhost:51002/) | Cerca e gestisce artisti e album |
| Prowlarr | [http://localhost:51003/](http://localhost:51003/) | Configura e prova gli indexer |
| Transmission | [http://localhost:51004/transmission/web/](http://localhost:51004/transmission/web/) | Controlla i download |
| uTorrent | [http://localhost:51005/gui/](http://localhost:51005/gui/) | Client torrent alternativo |
| qBittorrent | [http://localhost:51006/](http://localhost:51006/) | Client torrent alternativo |
| Jackett | [http://localhost:51007/](http://localhost:51007/) | Indexer per la ricerca integrata di qBittorrent |

Le porte web sono pubblicate su tutte le interfacce della host (`0.0.0.0`) nell'intervallo `51000-51007`. Le porte BitTorrent `51413` (Transmission), `51414` (uTorrent) e `51415` (qBittorrent), TCP/UDP, restano pubblicate per il traffico peer e non sono UI. Limita l'accesso con il firewall della host e con le regole del router.

### Accesso remoto tramite NAT o VPN del router

Assegna al server un indirizzo LAN stabile. Dal router puoi inoltrare le porte necessarie verso lo stesso numero sulla host, oppure raggiungerle tramite la VPN gestita dal router usando `http://IP_LAN_SERVER:PORTA`. Non c'è più un container WireGuard nello stack.

Le UI usano HTTP e non devono essere esposte indiscriminatamente su Internet. Preferisci la VPN del router; se usi NAT, limita gli indirizzi sorgente quando possibile, abilita le credenziali delle applicazioni e valuta un reverse proxy TLS/autenticato davanti alle UI. Inoltra `51413` TCP/UDP soltanto se vuoi rendere Transmission raggiungibile dai peer. Con CGNAT il port forwarding in ingresso non è normalmente disponibile.

## Ricerca e integrazione già configurate

Le cartelle principali sono già impostate in Radarr (`/media/movies`) e Lidarr (`/media/music`). Radarr, Lidarr e Prowlarr usano Transmission sulla rete Docker con il percorso RPC `/transmission/`; Prowlarr usa la categoria `prowlarr` per i grab manuali dalla propria pagina di ricerca. Prowlarr è collegato alle due applicazioni e sincronizza gli indexer: puoi cercare direttamente da **Radarr** o **Lidarr** senza copiare manualmente gli URL Torznab. I connettori **Emby / Jellyfin** in Radarr e Lidarr sono configurati per chiedere l’aggiornamento della libreria dopo l’importazione o l’aggiornamento di un file. Se rigeneri la chiave API di Jellyfin, aggiornala in **Settings → Connect → Jellyfin** in entrambe le applicazioni.

Durante il bootstrap viene letto il catalogo della versione di Prowlarr installata e vengono tentati **tutti gli indexer torrent pubblici** configurabili senza account. Quelli già presenti sono conservati; tracker privati e semi-privati vengono ignorati perché richiedono credenziali. Un indexer non raggiungibile, non valido o bloccato nella rete del server viene segnalato senza interrompere l'installazione. Radarr e Lidarr ricevono soltanto gli indexer con categorie compatibili: l'elenco effettivo compare in *Settings → Indexers* di ciascuna app. La disponibilità di un contenuto dipende comunque dai risultati restituiti e dal profilo qualità.

Gli indexer possono diventare irraggiungibili o cambiare indirizzo nel tempo. In **Prowlarr → Indexers** puoi rieseguire *Test*; in **System → Status** trovi gli errori. Se aggiungi un nuovo indexer, Prowlarr lo sincronizza automaticamente con Radarr e Lidarr quando le categorie sono compatibili. Usa soltanto fonti e contenuti che hai diritto di scaricare e condividere.

Per controllare i collegamenti: in **Radarr/Lidarr → Settings → Download Clients** verifica Transmission, e in **Prowlarr → Settings → Apps** verifica Radarr e Lidarr. Gli URL tra container usano i nomi Docker `transmission`, `radarr`, `lidarr`, `prowlarr`; nel browser continua a usare gli URL della tabella sopra. In **Jellyfin** verifica le librerie `/media/movies` e `/media/music` e abilita la scansione periodica se necessario.

## Flusso quotidiano: cercare un film

1. Apri [Radarr](http://localhost:51001/) e cerca il titolo con *Add New*.
2. Scegli il film e la cartella principale `/media/movies`. Puoi usare la ricerca automatica oppure aprire la ricerca interattiva per scegliere un risultato disponibile negli indexer di Prowlarr.
3. Radarr invia il torrent a Transmission. Segui l'avanzamento nella [sua interfaccia](http://localhost:51004/transmission/web/). I dati parziali restano in `downloads/incomplete`, invisibile a Jellyfin.
4. Transmission trasferisce il torrent completato in `downloads/complete`; Radarr lo importa in `media/movies` e può continuare a lasciare la copia di download per il seeding.
5. Apri [Jellyfin](http://localhost:51000/) e aggiorna la libreria se il film non compare subito.

## Flusso quotidiano: cercare musica

1. Apri [Lidarr](http://localhost:51002/) e cerca l'artista. Seleziona gli album desiderati e la cartella principale `/media/music`.
2. Avvia la ricerca automatica o scegli un risultato con la ricerca interattiva. Gli indexer arrivano da Prowlarr.
3. Controlla il torrent in Transmission. Finché è incompleto rimane in `downloads/incomplete`.
4. Finché il torrent è in coda o sta scaricando, `media/music` resta vuota. Solo dopo il completamento Transmission lo lascia in `/downloads/complete/lidarr` e Lidarr importa l’album in `media/music`; il connettore chiede quindi a Jellyfin di aggiornare la libreria. La coda di Transmission è configurata per un massimo di 10 download simultanei.

Lidarr gestisce soprattutto artisti e album; per un singolo brano è più pratico un download manuale in Transmission, selezionando poi la destinazione e organizzando i file prima di renderli visibili a Jellyfin.

## Cartelle e permessi

| Host | Nei container | Scopo |
| --- | --- | --- |
| `downloads/incomplete` | `/downloads/incomplete` | Torrent in corso; non montata in Jellyfin |
| `downloads/complete` | `/downloads/complete` | Torrent finiti; le categorie `radarr/` e `lidarr/` sono create da `install.sh` e condivise tra i tre container |
| `media/movies` | `/media/movies` | Libreria film; Jellyfin la legge soltanto |
| `media/music` | `/media/music` | Libreria musica; Jellyfin la legge soltanto |
| `jellyfin/config`, `jellyfin/cache`, `jellyfin/render-cache` | `/config`, `/cache`, `/config/data/render-cache` | Dati Jellyfin persistenti |
| `*/config` | `/config` | Stato dei nuovi servizi |
| `utorrent/settings` | `/utorrent/settings` | Configurazione persistente di uTorrent |
| `qbittorrent/config` | `/config` | Configurazione persistente di qBittorrent |
| `jackett/config` | `/config` | Configurazione e API key persistenti di Jackett |

uTorrent usa `/data/incomplete` durante il download e sposta i torrent terminati in `/data/complete`; sul sistema host corrispondono rispettivamente a `downloads/incomplete` e `downloads/complete`. La WebUI parte con utente `admin` e password vuota: impostane subito una dalle preferenze prima di consentire accessi dalla rete.

qBittorrent usa `/downloads/incomplete` durante il download e `/downloads/complete` al termine. Al primo avvio genera una password temporanea per l'utente `admin`: recuperala con `docker compose logs qbittorrent` e cambiala dalle impostazioni della WebUI.

Il plugin Jackett della ricerca integrata di qBittorrent viene configurato automaticamente da `go.sh`: usa `http://jackett:9117` sulla rete Compose e la API key generata localmente in `jackett/config`. Prima di cercare, aggiungi e prova gli indexer desiderati dalla UI di Jackett sulla porta `51007`.

Radarr e Lidarr copiano o collegano i file nella libreria. Non impostare la destinazione di Transmission direttamente in `media/movies` o `media/music`: i client torrent possono continuare a usare i file per il seeding e Jellyfin deve vedere solo la libreria importata. Se un servizio mostra *Permission denied*, verifica proprietà e permessi delle directory host con `ls -ln` e confrontali con UID/GID `1000:1000`.

## Come funziona Nginx

La configurazione è in [`nginx/default.conf`](nginx/default.conf). Ogni porta esterna inoltra l'intera richiesta a un servizio sulla rete Docker:

```text
host:51000  → nginx:8080 → jellyfin:8096
host:51001  → nginx:7878 → radarr:7878
host:51002  → nginx:8686 → lidarr:8686
host:51003  → nginx:9696 → prowlarr:9696
host:51004  → nginx:9091 → transmission:9091
host:51005  → nginx:8081 → utorrent:8080
host:51006  → qbittorrent:51006
host:51007  → jackett:9117
```

Nginx pubblica le prime sei UI; qBittorrent espone direttamente `51006` perché la sua protezione CSRF richiede che la porta WebUI interna ed esterna coincidano. Le route Nginx usano `proxy_pass` e passano gli header dell'host e del client; quella Jellyfin supporta WebSocket e streaming. Le root sulle porte pubbliche `51004` e `51005` reindirizzano rispettivamente alle UI di Transmission e uTorrent.

Jellyfin è sulla rete Docker, anziché in `network_mode: host`: l'accesso web e lo streaming passano da Nginx; funzioni basate su discovery/multicast come DLNA possono richiedere una configurazione di rete aggiuntiva. Per app e TV Jellyfin usa `http://IP_SERVER:51000/`.

## Collegamenti alla documentazione

- [Transmission Docker](https://docs.linuxserver.io/images/docker-transmission/)
- [uTorrent Docker](https://hub.docker.com/r/ekho/utorrent/)
- [qBittorrent Docker](https://docs.linuxserver.io/images/docker-qbittorrent/)
- [Jackett Docker](https://docs.linuxserver.io/images/docker-jackett/)
- [Prowlarr Docker](https://docs.linuxserver.io/images/docker-prowlarr/)
- [Radarr Docker](https://docs.linuxserver.io/images/docker-radarr/)
- [Lidarr Docker](https://docs.linuxserver.io/images/docker-lidarr/)
- [Jellyfin reverse proxy](https://jellyfin.org/docs/general/post-install/networking/reverse-proxy/)

## Installazione riproducibile da Git

Su un host Linux con Docker Engine, plugin Compose e un utente con UID/GID `1000:1000` abilitato a usare Docker. Python sull’host non è necessario: il bootstrap usa l’immagine `python:3.12-alpine`.

```bash
git clone <URL_DEL_REPOSITORY> mmedia
cd mmedia
./go.sh
```

`go.sh` esegue `install.sh`, avvia Compose e lancia `bootstrap.py` nel servizio Docker temporaneo `bootstrap` (profilo `tools`, rete host, solo durante la configurazione). Lo script può essere rilanciato: verifica le configurazioni esistenti e aggiorna i collegamenti senza ricreare account o librerie. Al primo avvio Jellyfin crea l'utente `admin` con password casuale, salvata **solo localmente** in `secrets/jellyfin-admin.txt` (permessi 600). Conservala in un gestore di password. La chiave API per i collegamenti è in `secrets/jellyfin-api-key` e non va pubblicata. Se Jellyfin era già configurato, lo script mantiene l'utente esistente e usa una chiave API locale; non ne cambia la password.

### Operazioni eseguite automaticamente

1. Verifica Docker, Compose e UID/GID 1000:1000; crea le directory `downloads`, `media` e quelle di configurazione con i permessi necessari.
2. Copia le impostazioni iniziali di Transmission e qBittorrent; avvia Jellyfin, i tre client torrent, Prowlarr, Radarr, Lidarr e Nginx.
3. Aspetta che le API locali siano disponibili; crea in Radarr `/media/movies` e in Lidarr `/media/music` come cartelle radice.
4. Configura Transmission in Radarr, Lidarr e Prowlarr usando `transmission:9091` e RPC `/transmission/`, con le categorie `radarr`, `lidarr` e `prowlarr`; attiva la rinomina dei brani in Lidarr per creare cartelle per album.
5. Tenta di aggiungere tutte le definizioni torrent pubbliche disponibili nel catalogo installato di Prowlarr, collega Prowlarr a Radarr e Lidarr e sincronizza gli indexer configurati. Se un indexer non è disponibile, stampa un avviso e prosegue.
6. Completa la prima configurazione di Jellyfin, aggiunge le librerie Film e Musica e collega Radarr e Lidarr a Jellyfin per richiedere una scansione dopo gli import.
7. Pubblica le UI sulle porte host `51000-51007`; qBittorrent e Jackett usano direttamente `51006` e `51007`, le altre passano da Nginx. Le applicazioni comunicano sulla rete Compose usando i rispettivi nomi di servizio.

### Da completare sul nuovo host

- In Prowlarr, controlla gli indexer preconfigurati con **Indexers → Test** e aggiungi gli altri a cui hai accesso. Gli indexer pubblici possono cambiare URL o non rispondere; quelli privati richiedono le tue credenziali. La sincronizzazione verso Radarr e Lidarr è già configurata.
- Per l'accesso remoto, configura sul router la sua VPN oppure inoltra soltanto le porte host necessarie (`51000-51007`) all'indirizzo LAN del server. Questa operazione dipende dal router e non può essere fatta dal repository.
- Se devi migrare film, musica, torrent o database dalla vecchia macchina, copia separatamente `media/`, `downloads/` e le directory di configurazione con i container fermi. Un clone Git crea un'installazione nuova, senza il catalogo e i file della vecchia macchina.
- Verifica l'avvio con `docker compose ps`, poi prova una ricerca in Radarr/Lidarr e controlla che un download completato venga importato in `media/` e appaia in Jellyfin.

### Cosa mettere in Git

| In Git | Fuori da Git |
| --- | --- |
| `docker-compose.yml`, `go.sh`, `install.sh`, `configure-qbittorrent-jackett.sh`, `bootstrap.py`, `nginx/default.conf`, `transmission/settings.json`, `qbittorrent/qBittorrent.conf`, `README.md`, `.gitignore` | `.env`, `secrets/`, `jellyfin/`, `media/`, `downloads/`, `transmission/config/`, `utorrent/settings/`, `qbittorrent/config/`, `jackett/config/`, `prowlarr/config/`, `radarr/config/`, `lidarr/config/`, log e database |

Le directory escluse contengono password, chiavi API, configurazioni personali, database e contenuti multimediali. `.gitignore` impedisce nuovi inserimenti accidentali, ma **non rimuove segreti già presenti nella cronologia Git**: se questo repository è stato pubblicato, rigenera password e token e bonifica la cronologia prima di condividerlo di nuovo. I file runtime sono stati tolti dall'indice Git senza cancellare le copie locali.
