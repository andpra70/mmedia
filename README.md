# mmedia: Jellyfin, torrent e libreria multimediale

Questo stack usa **Jellyfin** per riprodurre, **Prowlarr** per gestire gli indexer, **Radarr** per i film, **Lidarr** per la musica e **Transmission** per scaricare. **Nginx** è il punto di accesso web a tutte le interfacce.

Usa soltanto torrent e contenuti che hai il diritto di scaricare e condividere.

## Preparazione e avvio

Servono Docker Engine con `docker compose` e un utente autorizzato a usare Docker. I servizi che scrivono file sono configurati con UID e GID `1000`; controlla con `id -u` e `id -g` che corrispondano al tuo utente. In caso contrario, modifica UID/GID nel Compose e i permessi delle directory.

```bash
./install.sh
./go.sh
```

`install.sh` crea le directory e prepara le impostazioni iniziali di Transmission. `go.sh` avvia i container e apre le cinque interfacce nel browser. I dati Jellyfin sono sotto `jellyfin/`; `install.sh` migra automaticamente le vecchie directory `config/`, `cache/` e `render-cache/` se presenti. Per arrestare: `docker compose down`. Per controllare: `docker compose ps` e `docker compose logs -f NOME_SERVIZIO`.

### Interfacce web

| Applicazione | URL locale | Uso |
| --- | --- | --- |
| Jellyfin | [http://localhost:8080/](http://localhost:8080/) | Guarda film e ascolta musica |
| Radarr | [http://localhost:7878/](http://localhost:7878/) | Cerca e gestisce film |
| Lidarr | [http://localhost:8686/](http://localhost:8686/) | Cerca e gestisce artisti e album |
| Prowlarr | [http://localhost:9696/](http://localhost:9696/) | Configura e prova gli indexer |
| Transmission | [http://localhost:9091/transmission/web/](http://localhost:9091/transmission/web/) | Controlla i download |

Le porte web sono pubblicate sul server **solo su `127.0.0.1`**. Nginx condivide anche la rete del container WireGuard ed è raggiungibile dagli utenti VPN all'indirizzo `10.13.13.1`. Verso Internet si espone solo WireGuard sulla porta UDP `51820`; non inoltrare le cinque porte web nel router. La porta BitTorrent `51413` TCP/UDP è pubblicata per Transmission e serve ai peer, non alla UI.

### Accesso remoto tramite NAT e WireGuard

1. Assegna al server un indirizzo LAN stabile e inoltra nel router **solo UDP `51820`** verso tale indirizzo. Se usi un firewall host, consenti UDP `51820`. Con CGNAT la connessione in ingresso richiede un IP pubblico o un'alternativa come una rete privata gestita.
2. Avvia lo stack con `./install.sh` e `./go.sh`. WireGuard crea il primo profilo client in `wireguard/config/peer1/peer1.conf` e un QR nella stessa cartella. **Il file e il QR contengono una chiave privata: non condividerli pubblicamente.** La configurazione non viene stampata nei log (`LOG_CONFS=false`).
3. Installa l'[app ufficiale WireGuard](https://www.wireguard.com/install/) sul telefono o computer remoto. Importa il profilo `.conf` oppure scansiona il QR. Il profilo è per un solo dispositivo; per aggiungerne altri aumenta `PEERS` nel Compose e ricrea il container WireGuard.
4. In assenza di un dominio, `SERVERURL=auto` prova a inserire l'IP pubblico attuale nel profilo. Apri il profilo e verifica che la riga `Endpoint = IP_PUBBLICO:51820` sia corretta. Se non lo è, imposta `WIREGUARD_ENDPOINT=IP_PUBBLICO` in un file `.env` accanto al Compose, poi ricrea WireGuard e reimporta il profilo. Quando l'IP pubblico cambia, aggiorna l'endpoint nel client o usa un DDNS.
5. Da una rete esterna, disattiva il Wi-Fi del telefono, attiva la VPN e apri i link qui sotto. Il tunnel è configurato in modalità split: solo la subnet `10.13.13.0/24` passa nella VPN.

| Applicazione | URL dopo la connessione VPN |
| --- | --- |
| Jellyfin | `http://10.13.13.1:8080/` |
| Radarr | `http://10.13.13.1:7878/` |
| Lidarr | `http://10.13.13.1:8686/` |
| Prowlarr | `http://10.13.13.1:9696/` |
| Transmission | `http://10.13.13.1:9091/transmission/web/` |

Questi URL usano HTTP **all'interno del tunnel cifrato WireGuard**. Mantieni le credenziali delle applicazioni e proteggi i file in `wireguard/config/`. Un browser sulla LAN che non è sul server deve attivare la VPN per usare gli stessi URL; `localhost` funziona solo sul server.

## Ricerca e integrazione già configurate

Le cartelle principali sono già impostate in Radarr (`/media/movies`) e Lidarr (`/media/music`). Entrambe le applicazioni usano Transmission sulla rete Docker con il percorso RPC `/transmission/`. Prowlarr è collegato alle due applicazioni e sincronizza gli indexer: puoi cercare direttamente da **Radarr** o **Lidarr** senza copiare manualmente gli URL Torznab. I connettori **Emby / Jellyfin** in Radarr e Lidarr sono configurati per chiedere l’aggiornamento della libreria dopo l’importazione o l’aggiornamento di un file. Se rigeneri la chiave API di Jellyfin, aggiornala in **Settings → Connect → Jellyfin** in entrambe le applicazioni.

Gli indexer pubblici aggiunti e testati dal server sono **YTS** per i film, **The Pirate Bay** e **LimeTorrents** come fonti generiche, **Torrent Downloads** come alternativa generica, **MixtapeTorrent** per musica e **Nyaa.si** per contenuti anime e musica. Radarr e Lidarr accettano soltanto gli indexer che restituiscono risultati nelle rispettive categorie: l'elenco effettivo compare in *Settings → Indexers* di ciascuna app. Lidarr ora usa **MixtapeTorrent**, **Nyaa.si**, **NoNaMe Club**, **Torrent9** e **TorrentDownload**. La disponibilità di un album dipende dai risultati restituiti e dal profilo qualità: una ricerca può trovare release e scartarle se non corrispondono all’album o al formato richiesto. Per musica di altri generi, aggiungi in Prowlarr un tracker musicale a cui hai accesso e usa *Test* e *Sync App Indexers*.

Gli indexer possono diventare irraggiungibili o cambiare indirizzo nel tempo. In **Prowlarr → Indexers** puoi rieseguire *Test*; in **System → Status** trovi gli errori. Se aggiungi un nuovo indexer, Prowlarr lo sincronizza automaticamente con Radarr e Lidarr quando le categorie sono compatibili. Usa soltanto fonti e contenuti che hai diritto di scaricare e condividere.

Per controllare i collegamenti: in **Radarr/Lidarr → Settings → Download Clients** verifica Transmission, e in **Prowlarr → Settings → Apps** verifica Radarr e Lidarr. Gli URL tra container usano i nomi Docker `transmission`, `radarr`, `lidarr`, `prowlarr`; nel browser continua a usare gli URL della tabella sopra. In **Jellyfin** verifica le librerie `/media/movies` e `/media/music` e abilita la scansione periodica se necessario.

## Flusso quotidiano: cercare un film

1. Apri [Radarr](http://localhost:7878/) e cerca il titolo con *Add New*.
2. Scegli il film e la cartella principale `/media/movies`. Puoi usare la ricerca automatica oppure aprire la ricerca interattiva per scegliere un risultato disponibile negli indexer di Prowlarr.
3. Radarr invia il torrent a Transmission. Segui l'avanzamento nella [sua interfaccia](http://localhost:9091/transmission/web/). I dati parziali restano in `downloads/incomplete`, invisibile a Jellyfin.
4. Transmission trasferisce il torrent completato in `downloads/complete`; Radarr lo importa in `media/movies` e può continuare a lasciare la copia di download per il seeding.
5. Apri [Jellyfin](http://localhost:8080/) e aggiorna la libreria se il film non compare subito.

## Flusso quotidiano: cercare musica

1. Apri [Lidarr](http://localhost:8686/) e cerca l'artista. Seleziona gli album desiderati e la cartella principale `/media/music`.
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

Radarr e Lidarr copiano o collegano i file nella libreria. Non impostare la destinazione di Transmission direttamente in `media/movies` o `media/music`: i client torrent possono continuare a usare i file per il seeding e Jellyfin deve vedere solo la libreria importata. Se un servizio mostra *Permission denied*, verifica proprietà e permessi delle directory host con `ls -ln` e confrontali con UID/GID `1000:1000`.

## Come funziona Nginx

La configurazione è in [`nginx/default.conf`](nginx/default.conf). Ogni porta esterna inoltra l'intera richiesta a un servizio sulla rete Docker:

```text
localhost:8080  → nginx → jellyfin:8096
localhost:7878  → nginx → radarr:7878
localhost:8686  → nginx → lidarr:8686
localhost:9696  → nginx → prowlarr:9696
localhost:9091  → nginx → transmission:9091
```

Nginx condivide il namespace di rete di WireGuard, così ascolta anche su `10.13.13.1`. Usa `proxy_pass` e passa gli header dell'host e del client. La route Jellyfin supporta WebSocket e streaming. La root sulla porta 9091 reindirizza alla UI `/transmission/web/`. Una porta per applicazione permette di usare le UI senza cambiare le loro *URL Base*. Se preferisci un unico dominio con percorsi come `/radarr/`, devi impostare la corrispondente *URL Base* in Radarr, Lidarr, Prowlarr e Jellyfin e cambiare le route Nginx; un semplice `proxy_pass` con prefisso rimosso non basta per tutte le risorse web.

Jellyfin ora è sulla rete Docker, anziché in `network_mode: host`: l'accesso web e lo streaming passano da Nginx; funzioni basate su discovery/multicast come DLNA possono richiedere una configurazione di rete aggiuntiva. Per app e TV Jellyfin, dopo aver attivato la VPN, usa l'URL `http://10.13.13.1:8080/`.

## Collegamenti alla documentazione

- [Transmission Docker](https://docs.linuxserver.io/images/docker-transmission/)
- [Prowlarr Docker](https://docs.linuxserver.io/images/docker-prowlarr/)
- [Radarr Docker](https://docs.linuxserver.io/images/docker-radarr/)
- [Lidarr Docker](https://docs.linuxserver.io/images/docker-lidarr/)
- [Jellyfin reverse proxy](https://jellyfin.org/docs/general/post-install/networking/reverse-proxy/)
- [WireGuard Docker](https://docs.linuxserver.io/images/docker-wireguard/)

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
2. Copia le impostazioni iniziali di Transmission; avvia Jellyfin, Transmission, Prowlarr, Radarr, Lidarr, WireGuard e Nginx.
3. Aspetta che le API locali siano disponibili; crea in Radarr `/media/movies` e in Lidarr `/media/music` come cartelle radice.
4. Configura Transmission in Radarr e Lidarr usando `transmission:9091`, RPC `/transmission/` e le categorie `radarr` e `lidarr`; attiva la rinomina dei brani in Lidarr per creare cartelle per album.
5. Aggiunge, se le definizioni sono disponibili, alcuni indexer pubblici (The Pirate Bay, YTS, TorrentDownload, Nyaa.si), collega Prowlarr a Radarr e Lidarr e sincronizza gli indexer configurati. Se un indexer non è disponibile, stampa un avviso e prosegue.
6. Completa la prima configurazione di Jellyfin, aggiunge le librerie Film e Musica e collega Radarr e Lidarr a Jellyfin per richiedere una scansione dopo gli import.
7. Pubblica le cinque UI su `127.0.0.1` e sulla VPN `10.13.13.1` tramite Nginx. Le applicazioni comunicano sulla rete Compose con i nomi `jellyfin`, `transmission`, `prowlarr`, `radarr`, `lidarr`.

### Da completare sul nuovo host

- In Prowlarr, controlla gli indexer preconfigurati con **Indexers → Test** e aggiungi gli altri a cui hai accesso. Gli indexer pubblici possono cambiare URL o non rispondere; quelli privati richiedono le tue credenziali. La sincronizzazione verso Radarr e Lidarr è già configurata.
- Per l'accesso remoto, inoltra sul router la porta UDP `51820` al nuovo host e importa il profilo `wireguard/config/peer1/peer1.conf` nell'app WireGuard. Se l'IP pubblico rilevato è errato, imposta `WIREGUARD_ENDPOINT` in `.env` e ricrea il container. Questa operazione dipende dal router e non può essere fatta dal repository.
- Se devi migrare film, musica, torrent o database dalla vecchia macchina, copia separatamente `media/`, `downloads/` e le directory di configurazione con i container fermi. Un clone Git crea un'installazione nuova, senza il catalogo e i file della vecchia macchina.
- Verifica l'avvio con `docker compose ps`, poi prova una ricerca in Radarr/Lidarr e controlla che un download completato venga importato in `media/` e appaia in Jellyfin.

### Cosa mettere in Git

| In Git | Fuori da Git |
| --- | --- |
| `docker-compose.yml`, `go.sh`, `install.sh`, `bootstrap.py`, `nginx/default.conf`, `transmission/settings.json`, `README.md`, `.gitignore` | `.env`, `secrets/`, `jellyfin/`, `media/`, `downloads/`, `transmission/config/`, `prowlarr/config/`, `radarr/config/`, `lidarr/config/`, `wireguard/config/`, log e database |

Le directory escluse contengono password, chiavi API, chiavi private VPN, configurazioni personali, database e contenuti multimediali. `.gitignore` impedisce nuovi inserimenti accidentali, ma **non rimuove segreti già presenti nella cronologia Git**: se questo repository è stato pubblicato, rigenera password, token e chiavi VPN e bonifica la cronologia prima di condividerlo di nuovo. I file runtime sono stati tolti dall'indice Git senza cancellare le copie locali.
