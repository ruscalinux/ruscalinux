# ruscapiper-engine

Motore di sintesi vocale di RuscaLLisse: **Piper** (piper1-gpl), software esterno con licenza GPL-3.0 (<https://github.com/OHF-Voice/piper1-gpl>), compilato dal sorgente senza modificarne il codice, con **espeak-ng** (GPL-3.0) compilato dentro per i fonemi e l’**ONNX Runtime di Debian** (`libonnxruntime-dev`). Non c’è codice di rete e non c’è Python.

| File | Cosa contiene |
|---|---|
| `make-deb.sh` | Scarica, verifica, compila, prova e impacchetta l’ultima release stabile di Piper |
| `ultima-versione.sh` | Dice qual è l’ultima release stabile (o quella fissata a mano) |
| `CMakeLists.txt` | La build di RuscaLinux: `libpiper.so` dai file di Piper, senza modifiche, e `ruscapiper-stream` |
| `ruscapiper-stream.c` | Il programma che avvia RuscaLLisse (GPL-3.0, scritto da RuscaLinux) |
| `checksums/` | Impronta SHA-256 dei due archivi sorgente di ogni versione già costruita (la cartella nasce vuota e si riempie alla prima build) |
| `apparmor/usr.lib.ruscapiper-engine.ruscapiper-stream` | Profilo AppArmor, installato in modalità complain |

## Che cosa contiene il pacchetto

| File | A cosa serve |
|---|---|
| `/usr/lib/ruscapiper-engine/ruscapiper-stream` | Carica una voce una volta sola e la tiene aperta; riceve le frasi dallo standard input e scrive l’audio sullo standard output |
| `/usr/lib/ruscapiper-engine/libpiper.so` | La libreria C di Piper, con espeak-ng dentro |
| `/usr/lib/ruscapiper-engine/espeak-ng-data/` | I dati di espeak-ng (regole di pronuncia delle lingue) |
| `/usr/share/ruscapiper/voices/` | Cartella vuota per le voci installate dall’amministratore |

Le voci non fanno parte del pacchetto: ogni voce è la coppia `nome.onnx` e `nome.onnx.json`, che l’utente importa da RuscaLLisse (finisce in `~/.local/share/ruscapiper/voices/`). Ogni voce ha la propria licenza.

## Il protocollo di ruscapiper-stream

All’avvio, dopo aver caricato la voce, scrive `RPS1` e la versione del protocollo (u32, little endian, oggi 1). Poi legge **una riga per frase**:

```
ID<TAB>LENGTH_SCALE<TAB>TESTO\n
```

e per ogni frase scrive uno o più blocchi: l’intestazione `RPSC` seguita da sette u32 (identificativo, flag, frequenza, numero di campioni, numero di fonemi, numero di allineamenti), poi i campioni PCM a 16 bit, i fonemi (codici Unicode, gruppi separati da 0) e gli allineamenti (i32, campioni per fonema). Flag 1: ultimo blocco della frase. Flag 2: errore (la frase è persa, il programma resta aperto). Gli allineamenti sono ciò che fa muovere la bocca di Ellittica a tempo con la voce.

Prova a mano, con una voce scaricata:

```bash
printf '1\t1.0\tCiao, sono Ellittica.\n' | \
  /usr/lib/ruscapiper-engine/ruscapiper-stream --voice it_IT-paola-medium.onnx | wc -c
```

## Costruire il pacchetto

Dipendenze, una volta sola:

```bash
sudo apt install build-essential cmake pkg-config dpkg-dev wget git python3 \
                 libonnxruntime-dev libsonic-dev
```

Poi `./make-deb.sh`. La prima compilazione richiede qualche minuto; il risultato resta in `~/.cache/ruscalinux/ruscapiper-engine/` e le build successive rifanno solo il pacchetto.

## Quale versione di Piper ed espeak-ng

`make-deb.sh` costruisce sempre l’**ultima release stabile** di piper1-gpl (tag `vX.Y.Z` indicato da GitHub come “Latest”). Per una versione precisa:

```bash
RUSCAPIPER_PIPER_VERSION=1.8.0 ./make-deb.sh
```

espeak-ng **non** è quello di Debian: Piper usa `espeak_TextToPhonemesWithTerminator()`, che espeak-ng 1.52 (trixie) non ha. Si compila, come libreria statica, il commit che Piper fissa nel suo `libpiper/CMakeLists.txt` (`GIT_TAG`), con le stesse opzioni di Piper (niente audio, niente MBROLA, niente sonic).

## Controlli automatici

1. **Commit.** Il commit scritto in ciascun archivio deve essere quello del tag di Piper e quello fissato per espeak-ng.
2. **Impronta.** La prima volta che una versione viene costruita, le impronte SHA-256 dei due archivi vengono scritte in `checksums/`; le build successive devono trovare gli stessi archivi. I file nuovi vanno aggiunti al repository (`git add checksums/`).
3. **Età.** Una release uscita da meno di 14 giorni viene costruita lo stesso, con un avviso.
4. **ONNX Runtime.** Solo quello di Debian: la build non scarica niente.
5. **Niente rete.** La compilazione gira senza rete (`unshare -rn`). Binari e libreria non devono essere collegati a OpenSSL, libcrypto o curl, né richiedere `socket`, `connect`, `bind`, `listen`, `accept`, `getaddrinfo`, `gethostbyname`, `sendto` o `recvfrom`.
6. **API.** `libpiper.so` deve esportare le funzioni usate da `ruscapiper-stream` (`SIMBOLI_PIPER`).
7. **Prova.** `ruscapiper-stream` legge una frase con la voce di prova del sorgente (`tests/test_voice.onnx`, senza pesi veri) e deve rispondere con intestazioni e campioni corretti. Controlla che il programma funzioni; non dice nulla sulla qualità della voce.

## Rete e privacy

`ruscapiper-stream` non apre porte e non ha codice di rete: legge e scrive solo i propri flussi standard. Il testo delle frasi arriva dallo standard input, mai dalla riga di comando, e l’audio non viene mai scritto su disco. Il profilo AppArmor nega la rete, `.ssh`, `.gnupg` e `.config`.
