# ruscadiffusion-engine

Motore di generazione delle immagini e dei video di RuscaLLama: **stable-diffusion.cpp**, software esterno con licenza MIT (<https://github.com/leejet/stable-diffusion.cpp>), compilato dal sorgente con il backend Vulkan e senza codice di rete. È fatto come `ruscawhisper-engine`: stesse regole, stessi controlli, stesse dipendenze di compilazione.

| File | Cosa contiene |
|---|---|
| `make-deb.sh` | Scarica, verifica, compila, prova e impacchetta l’ultima release di stable-diffusion.cpp |
| `ultima-versione.sh` | Dice qual è l’ultima release (o quella fissata a mano) |
| `checksums/stable-diffusion.cpp-<tag>.sha256` | Impronte dei due archivi sorgente di ogni versione già costruita (stable-diffusion.cpp e la sua copia di ggml) |
| `apparmor/usr.lib.ruscadiffusion-engine.sd-cli` | Profilo AppArmor, installato in modalità complain |

## Che cosa contiene il pacchetto

| Programma | A cosa serve |
|---|---|
| `/usr/lib/ruscadiffusion-engine/sd-cli` | Legge un modello e una descrizione e scrive le immagini PNG o un video AVI (Motion JPEG, con `-M vid_gen`): lo avvia RuscaLLama, una volta per ogni generazione |

Non c’è `sd-server`: RuscaLLama non apre porte per le immagini, nemmeno su 127.0.0.1. Il motore parte, crea le immagini ed esce. ggml e stable-diffusion.cpp sono compilati dentro `sd-cli`: un solo file, senza librerie private.

I modelli non fanno parte del pacchetto. Si copiano in `~/.local/share/ruscadiffusion/models/` (o, per tutti gli utenti, in `/usr/share/ruscadiffusion/models/`), oppure si usano da un’altra cartella con **Aggiungi una cartella…** di RuscaLLama, senza copiarli:

| Tipo | Esempi | Come si mette |
|---|---|---|
| Un file solo, con tutto dentro | Stable Diffusion 1.5 e 2.1, SDXL, SD-Turbo, SDXL-Turbo | Il file `.safetensors`, `.gguf` o `.ckpt` |
| Una cartella di file | Z-Image, FLUX.1, FLUX.2, Qwen-Image, Stable Diffusion 3.5, Chroma e gli altri di `docs/models/` di stable-diffusion.cpp | Una cartella con il modello di diffusione, il VAE (`ae.safetensors`, `flux2_ae.safetensors`…) e i codificatori di testo (`clip_l`, `clip_g`, `t5xxl`, o il modello linguistico, come Qwen3-4B per Z-Image e FLUX.2-klein) |

I modelli per i video (Wan 2.1 e 2.2, HunyuanVideo 1.5, LingBot-Video) sono sempre una cartella di file: il modello di diffusione, il suo VAE (`wan_2.1_vae`, `wan2.2_vae`…) e il codificatore di testo (`umt5-xxl` per Wan); per Wan 2.2 A14B anche il secondo modello (`HighNoise`), per Wan 2.1 I2V `clip_vision_h`. Il video si scrive in AVI Motion JPEG con il codice di sd-cli stesso: non servono libwebm né altre librerie.

RuscaLLama riconosce i file dal nome e, per i `.safetensors`, dai nomi dei tensori scritti nell’intestazione. Ogni modello ha la propria licenza, che l’utente deve rispettare.

## Costruire il pacchetto

Dipendenze, una volta sola (le stesse di `ruscallama-engine`):

```bash
sudo apt install build-essential cmake pkg-config dpkg-dev wget git \
                 libvulkan-dev glslc spirv-headers
```

Poi `./make-deb.sh` (lo lancia anche `make-debs.sh` della distribuzione). La prima compilazione di ogni versione richiede parecchi minuti; il risultato resta in `~/.cache/ruscalinux/ruscadiffusion-engine/` e le build successive rifanno solo il pacchetto.

`RUSCADIFFUSION_BACKEND=cpu ./make-deb.sh` compila senza Vulkan, per le prove.

## Quale versione di stable-diffusion.cpp

stable-diffusion.cpp non ha numeri di versione `X.Y.Z`: ogni release è un tag `master-<numero>-<commit>` (per esempio `master-1106-532d2c1`) e il numero cresce a ogni release. `make-deb.sh` costruisce sempre quella che GitHub indica come “Latest”. `ultima-versione.sh` la cerca con l’API di GitHub, poi con il rinvio di `releases/latest`, poi con `git ls-remote` (il numero più alto; con `GITHUB_TOKEN` nell’ambiente il limite dell’API sale).

`build.sh` fa lo stesso controllo: se è uscita una release più nuova di quella impacchettata, ricostruisce i pacchetti anche se in `apps/` non è cambiato nulla. stable-diffusion.cpp pubblica una release a ogni modifica, quindi capiterà spesso.

Per costruire una versione precisa (ad esempio una precedente, se l’ultima dà problemi), il tag intero o solo il numero:

```bash
RUSCADIFFUSION_SD_VERSION=master-1104-5dcfa79 ./make-deb.sh
RUSCADIFFUSION_SD_VERSION=1104 ./make-deb.sh
```

Senza rete si usa la versione più recente già scaricata e registrata, con un avviso.

## Controlli automatici

1. **Due archivi.** stable-diffusion.cpp usa una propria copia di ggml (<https://github.com/leejet/ggml>) come sottomodulo git, e gli archivi di GitHub non contengono i sottomoduli. Il commit di ggml non si sceglie: è quello registrato nel sorgente di stable-diffusion.cpp per quel tag, letto con `git` (si scaricano solo le cartelle, non i file). La build si ferma se il sottomodulo arriva da un altro indirizzo.
2. **Commit.** Il commit scritto in ciascun archivio deve essere quello atteso: il commit del tag su GitHub per stable-diffusion.cpp (e deve cominciare con le cifre scritte nel nome del tag), il commit del sottomodulo per ggml.
3. **Impronte.** La prima volta che una versione viene costruita, le impronte SHA-256 dei due archivi (e il commit di ggml, nel nome del secondo) vengono scritte in `checksums/`; le build successive della stessa versione devono trovare gli stessi archivi. Il file nuovo va aggiunto al repository (`git add`).
4. **Età.** Una release uscita da meno di 14 giorni viene costruita lo stesso, con un avviso: prova la generazione delle immagini di RuscaLLama prima di pubblicare la ISO.
5. **Librerie incluse.** stable-diffusion.cpp tiene le librerie di altri autori in `thirdparty/`. Se compare un file o una cartella che non è nell’elenco `TERZI_DICHIARATI` la build si ferma: va dichiarata nel file `copyright` (in `make-deb.sh`) e nelle specifiche.
6. **Niente rete.** La compilazione gira senza rete (`unshare -rn`). Il binario non deve essere collegato a OpenSSL, libcrypto o curl, e tra i simboli che richiede non devono esserci `socket`, `connect`, `bind`, `listen`, `accept`, `getaddrinfo`, `gethostbyname`, `sendto` o `recvfrom`.
7. **Opzioni.** `sd-cli --help` deve elencare tutte le opzioni usate da RuscaLLama (`OPZIONI_USATE` in `make-deb.sh`). Quando il programma comincia a usare un’opzione nuova, va aggiunta all’elenco.
8. **Prova.** Il motore appena compilato deve dire la sua versione (`--version`) ed elencare le schede (`--list-devices`, una riga `nome<TAB>descrizione` per scheda: è il formato che legge RuscaLLama). Il sorgente non contiene un modello di prova: la generazione vera si prova con RuscaLLama.

## Rete e privacy

| Opzione | Effetto |
|---|---|
| Si compila solo `sd-cli` | Niente `sd-server`, quindi niente cpp-httplib e niente interfaccia web |
| `SD_RPC=OFF`, `GGML_RPC=OFF` | Niente backend RPC (`--rpc-servers`): il motore non può usare schede di altri computer |
| `SD_SERVER_BUILD_FRONTEND=OFF` | Niente pnpm né pacchetti JavaScript scaricati durante la build |
| `SD_WEBP=OFF`, `SD_WEBM=OFF` | Niente libwebp e libwebm (sottomoduli non inclusi): le immagini sono PNG |

RuscaLLama passa la descrizione al motore in un file (`--prompt-file`) nella sua cartella di lavoro `~/.cache/ruscallama/images/` (permessi 0700), non sulla riga di comando, dove la vedrebbe chiunque con `ps`.
