# ruscawhisper-engine

Motore di riconoscimento vocale di RuscaDubbing: **whisper.cpp**, software esterno con licenza MIT (<https://github.com/ggml-org/whisper.cpp>), compilato dal sorgente con il backend Vulkan e senza codice di rete. È fatto come `ruscallama-engine`: stesse regole, stessi controlli, stesse dipendenze di compilazione.

| File | Cosa contiene |
|---|---|
| `make-deb.sh` | Scarica, verifica, compila, prova e impacchetta l’ultima release stabile di whisper.cpp |
| `ultima-versione.sh` | Dice qual è l’ultima release stabile (o quella fissata a mano) |
| `checksums/whisper.cpp-v<versione>.tar.gz.sha256` | Impronta dell’archivio sorgente di ogni versione già costruita (la cartella nasce alla prima build) |
| `apparmor/usr.lib.ruscawhisper-engine.whisper-cli` | Profilo AppArmor, installato in modalità complain |

## Che cosa contiene il pacchetto

| Programma | A cosa serve |
|---|---|
| `/usr/lib/ruscawhisper-engine/whisper-cli` | Legge un file audio e scrive la trascrizione: lo avvia RuscaDubbing, una volta per ogni file |
| `/usr/lib/ruscawhisper-engine/whisper-bench` | Misura la velocità di un modello, dal terminale |

Non c’è `whisper-server`: RuscaDubbing non apre porte, nemmeno su 127.0.0.1. Il motore parte, trascrive un file ed esce.

I modelli non fanno parte del pacchetto. Sono file **ggml** (`.bin`), per esempio `ggml-large-v3-turbo.bin`, che l’utente copia in `~/.local/share/ruscawhisper/models/` o l’amministratore in `/usr/share/ruscawhisper/models/`. Ogni modello ha la propria licenza.

## Costruire il pacchetto

Dipendenze, una volta sola (le stesse di `ruscallama-engine`):

```bash
sudo apt install build-essential cmake pkg-config dpkg-dev wget git \
                 libvulkan-dev glslc spirv-headers
```

Poi `./make-deb.sh` (lo lancia anche `make-debs.sh` della distribuzione). La prima compilazione di ogni versione richiede qualche minuto; il risultato resta in `~/.cache/ruscalinux/ruscawhisper-engine/` e le build successive rifanno solo il pacchetto.

`RUSCAWHISPER_BACKEND=cpu ./make-deb.sh` compila senza Vulkan, per le prove.

## Quale versione di whisper.cpp

`make-deb.sh` costruisce sempre l’**ultima release stabile**: quella che GitHub indica come “Latest”, con un tag `vX.Y.Z`. `ultima-versione.sh` la cerca con l’API di GitHub, poi con il rinvio di `releases/latest`, poi con `git ls-remote` (con `GITHUB_TOKEN` nell’ambiente il limite dell’API sale).

`build.sh` fa lo stesso controllo: se è uscita una release più nuova di quella impacchettata, ricostruisce i pacchetti anche se in `tools/` non è cambiato nulla.

Per costruire una versione precisa (ad esempio quella precedente, se l’ultima dà problemi):

```bash
RUSCAWHISPER_WHISPER_VERSION=1.9.4 ./make-deb.sh
```

Senza rete si usa la versione più recente già scaricata e registrata, con un avviso.

## Controlli automatici

1. **Commit.** Il commit scritto nell’archivio deve essere quello a cui punta il tag su GitHub (i tag di whisper.cpp sono annotati: conta il commit puntato).
2. **Impronta.** La prima volta che una versione viene costruita, la sua impronta SHA-256 viene scritta in `checksums/`; le build successive della stessa versione devono trovare lo stesso archivio. Il file nuovo va aggiunto al repository (`git add`).
3. **Età.** Una release uscita da meno di 14 giorni viene costruita lo stesso, con un avviso: prova RuscaDubbing prima di pubblicare la ISO.
4. **Librerie incluse.** whisper.cpp tiene le librerie di altri autori in `examples/`, accanto ai propri file. Se in `examples/` compare un file che non è negli elenchi `SORGENTI_WHISPER` e `TERZI_DICHIARATI` la build si ferma: se è una libreria va dichiarata nel file `copyright` (in `make-deb.sh`) e nelle specifiche.
5. **Niente rete.** La compilazione gira senza rete (`unshare -rn`). I binari non devono essere collegati a OpenSSL, libcrypto o curl, e tra i simboli che richiedono non devono esserci `socket`, `connect`, `bind`, `listen`, `accept`, `getaddrinfo`, `gethostbyname`, `sendto` o `recvfrom`.
6. **Opzioni.** `whisper-cli --help` deve elencare tutte le opzioni usate da RuscaDubbing (`OPZIONI_USATE` in `make-deb.sh`). Quando il programma comincia a usare un’opzione nuova, va aggiunta all’elenco.
7. **Prova.** Il motore appena compilato trascrive l’audio di prova del sorgente (`samples/jfk.wav`) con il modello di prova (`models/for-tests-ggml-tiny.bin`, senza pesi: il testo è vuoto) e deve scrivere il JSON della trascrizione. Controlla che il binario parta e arrivi in fondo; non dice nulla sulla qualità del riconoscimento, che dipende dal modello.

## Rete e privacy

| Opzione | Effetto |
|---|---|
| `WHISPER_BUILD_SERVER=OFF` | Niente `whisper-server`, quindi niente cpp-httplib |
| `WHISPER_CURL=OFF` | Niente libcurl |
| `WHISPER_SDL2=OFF` | Niente microfono: si trascrivono solo file |
| `WHISPER_COMMON_FFMPEG=OFF` | Il motore non è collegato alle librerie di FFmpeg: video e altri formati li converte RuscaDubbing con il comando `ffmpeg` di Debian |

Gli script `models/download-*.sh` del sorgente non vengono impacchettati.
