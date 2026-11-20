# ruscavosk-engine

Motore di riconoscimento vocale di RuscaLLisse: la libreria `libvosk.so` di **Vosk** (vosk-api), software esterno con licenza Apache-2.0 (<https://github.com/alphacep/vosk-api>), compilata dal sorgente insieme a **Kaldi** e **OpenFst** nelle versioni di Alpha Cephei (Apache-2.0). Per il calcolo usa l’**OpenBLAS di Debian**. Non c’è codice di rete e non c’è Python.

| File | Cosa contiene |
|---|---|
| `make-deb.sh` | Scarica, verifica, compila, prova e impacchetta Vosk con Kaldi e OpenFst |
| `patches/kaldi-lapack.patch` | L’unica modifica: fa passare le chiamate LAPACK di Kaldi dalle macro di `lapack.h`, che aggiungono le lunghezze nascoste degli argomenti stringa richieste da LAPACK ≥ 3.9 (senza, Kaldi non compila con le intestazioni di Debian) |
| `checksums/` | Impronta SHA-256 dei tre archivi sorgente (si riempie alla prima build) |

## Che cosa contiene il pacchetto

| File | A cosa serve |
|---|---|
| `/usr/lib/ruscavosk-engine/libvosk.so` | La libreria di Vosk, con Kaldi e OpenFst dentro; RuscaLLisse la carica con `ctypes` |
| `/usr/share/ruscavosk/models/` | Cartella vuota per i modelli installati dall’amministratore |

I modelli non fanno parte del pacchetto: ogni modello è una cartella scaricata da <https://alphacephei.com/vosk/models>, che l’utente importa da RuscaLLisse (finisce in `~/.local/share/ruscavosk/models/`). Ogni modello ha la propria licenza.

## Costruire il pacchetto

Dipendenze, una volta sola:

```bash
sudo apt install build-essential dpkg-dev wget git python3 \
                 autoconf automake libtool zlib1g-dev \
                 libopenblas-serial-dev liblapacke-dev
```

Poi `./make-deb.sh`. La prima compilazione richiede una ventina di minuti (Kaldi è la parte lunga); il risultato resta in `~/.cache/ruscalinux/ruscavosk-engine/` e le build successive rifanno solo il pacchetto. Per la prova vera con un modello:

```bash
RUSCAVOSK_MODEL=~/vosk-model-small-it-0.22 ./make-deb.sh
```

## Quali versioni

Le versioni sono **fissate** in `make-deb.sh`: `VOSK_TAG` (oggi v0.3.50), `KALDI_COMMIT` (ramo `vosk` di alphacep/kaldi) e `OPENFST_COMMIT` (alphacep/openfst). Vosk non fissa la revisione di Kaldi: la sua ricetta (`travis/Dockerfile.manylinux`) usa la cima del ramo `vosk`. Per questo non c’è `ultima-versione.sh`: le versioni si cambiano a mano, provando RuscaLLisse, e alla prima build le impronte nuove finiscono in `checksums/`.

La compilazione segue la ricetta di Vosk: OpenFst con le estensioni `far`, `ngram` e `lookahead`; Kaldi solo per `online2` e `rnnlm`, con `-O3`; `libvosk.so` con il Makefile di Vosk, Kaldi e OpenFst statici dentro. Cambia il calcolo: invece di compilare OpenBLAS 0.3.20 e CLAPACK, si usa OpenBLAS di Debian nella variante senza thread, collegato dinamicamente.

## Controlli automatici

1. **Commit.** Il commit scritto in ciascun archivio deve essere quello fissato.
2. **Impronta.** La prima volta, le impronte SHA-256 dei tre archivi vengono scritte in `checksums/`; le build successive devono trovare gli stessi archivi. I file nuovi vanno aggiunti al repository (`git add checksums/`).
3. **Niente rete.** La compilazione gira senza rete (`unshare -rn`). La libreria non deve essere collegata a OpenSSL, libcrypto o curl, né richiedere `socket`, `connect`, `bind`, `listen`, `accept`, `getaddrinfo`, `gethostbyname`, `sendto` o `recvfrom`, e non deve avere RUNPATH.
4. **API.** `libvosk.so` deve esportare le funzioni usate da RuscaLLisse (`SIMBOLI_VOSK`).
5. **Prova.** La libreria si carica con `ctypes` e rifiuta, senza cadere, un modello che non esiste. Se c’è un modello (`RUSCAVOSK_MODEL`, o il primo in `~/.local/share/ruscavosk/models/`), lo apre e gli fa riconoscere un secondo di silenzio.

## Rete, thread e privacy

La libreria lavora dentro il processo di RuscaLLisse, sull’audio che riceve in memoria: nessun processo, nessuna porta, niente file audio. RuscaLLisse imposta `OPENBLAS_NUM_THREADS=1` prima di caricarla: se sul sistema è scelta la variante di OpenBLAS con i thread, il calcolo resta comunque su un thread, come nella ricetta di Vosk.

Kaldi sa leggere un file come uscita di un comando, se il nome finisce con `|` (la funzione `popen` è anche nella libreria già compilata di Vosk): non è codice di rete, ma un modello costruito apposta potrebbe far eseguire un comando. I modelli si prendono da fonti fidate.
