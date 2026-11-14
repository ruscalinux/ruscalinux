# Come funziona questo repository

Manuale per chi mantiene RuscaLinux. Il [README](README.md) è la vetrina per
chi arriva da fuori; qui c'è tutto il resto.

Tre script, in ordine di utilizzo. Nessuno di essi decide *cosa* c'è dentro la
ISO: quello lo decidono i tre file in `steps/`.

| | |
|---|---|
| `release.conf` | Le impostazioni. **L'unico file dove è scritta la versione.** |
| `make-debs.sh` | Costruisce i pacchetti `.deb` da `branding/` e `tools/`. |
| `build.sh` | Costruisce la ISO. |
| `test.sh` | La avvia in QEMU per provarla. |

## Fare una nuova versione

```sh
vi release.conf     # VERSION="2.0"
./build.sh
./test.sh
```

Il driver NVIDIA segue il ramo scritto in `NVIDIA_PIN` (`"620"`): ogni
build prende l'ultima versione del ramo. Alla fine `build.sh` stampa la
versione installata (riga `nvidia`): prima di pubblicare controlla che sia
quella provata su hardware vero. La stessa versione finisce da sola nelle
note di rilascio e nei documenti per chi scarica (`@NVIDIA@`).

Poi si pubblica a mano: vedi più sotto.

Il numero di versione si scrive una volta sola. Da `release.conf` finisce nel
nome della ISO, nell'etichetta del volume, in `/etc/os-release`, in
`/etc/issue`, nel titolo dell'installer e nella sua immagine: sono i diciassette
punti dove prima andava scritto a mano.

## Il driver NVIDIA

La ISO contiene anche il driver dal repository ufficiale NVIDIA, ma si avvia
e si installa con i driver liberi. Il driver NVIDIA si sceglie nel menu di
avvio, con le voci “… with NVIDIA driver”. Se ne occupa
`steps/40-nvidia.sh`, che gira dopo gli altri tre passi.

Prima della prima build serve la chiave del repository NVIDIA in
`local/nvidia/`, e c'è una chiave di firma da conservare con cura: tutto è
spiegato in [`docs/NVIDIA.md`](docs/NVIDIA.md).

## Cosa serve sulla macchina

```sh
sudo apt install live-build python3 openssl squashfs-tools qemu-system-x86 qemu-utils ovmf
```

`openssl` e `squashfs-tools` servono al driver NVIDIA: il primo crea la
chiave di firma dei moduli, il secondo controlla che non finisca nella ISO.

`python3` serve agli script dei tool per controllare traduzioni e sorgenti.
La rete non serve più per preparare i pacchetti: si costruisce tutto qui.

## Cosa fa build.sh, in ordine

1. Controlla che ci siano `live-build`, `dpkg-deb` e `python3`, e che tu non
   sia root.
2. Lancia `make-debs.sh` se manca `local/extra_debs/` o se qualcosa in
   `branding/` o `tools/` è più recente dei pacchetti.
3. Verifica che ci sia un pacchetto per ogni utility di `tools/`.
4. Copia `steps/*.sh` in `.gen/` sostituendo `@VERSION@` col numero vero.
5. Esegue i tre step, che preparano `.work/`.
6. Lancia `lb build` e calcola lo sha256 della ISO.

7. Riempie i documenti del rilascio col nome del file, il peso, lo sha256 e il
   numero di pacchetti veri: `RELEASE-NOTES-<versione>.md` dal modello
   `RELEASE-NOTES.md`, e `README.md` e `INSTALL.md` dai modelli in `dist/`.

`./build.sh --config` si ferma dopo il punto 5: utile per controllare la
configurazione senza aspettare la build lunga.
`./build.sh --clean` cancella `.work` e `.gen` e basta.

## Le cartelle

| | |
|---|---|
| `steps/` | **I tre script che determinano la ISO.** Sono i tuoi. |
| `branding/` | Sorgenti: logo, icone, sfondi, caratteri, generatori HTML. |
| `tools/` | Le applicazioni di RuscaLinux, una cartella ciascuna. |
| `local/` | File che live-build usa direttamente (splash, logo). |
| `.work/` | Dove lavora live-build. Si rigenera, non sta in git. |
| `.gen/` | Gli script di `steps/` col numero di versione dentro. |

## Aggiungere un'applicazione

Crea `tools/<nome>/` con dentro uno script `make-deb.sh` che:

- si lancia dalla sua cartella, senza argomenti;
- ha la versione scritta dentro di sé, uguale a `VERSION` di `release.conf`;
- scrive un solo `.deb` in `build-deb/` (per esempio
  `<nome>-ruscalinux_1.99.3_all.deb`);
- produce un pacchetto Debian che si chiama `<nome>`, come la cartella.

Nient'altro. `make-debs.sh` scorre `tools/*/` e costruisce quello che trova;
`build.sh` pretende poi un pacchetto con quel nome e si ferma se manca.
Nessuno script nomina le applicazioni, quindi aggiungerne una non richiede
di modificare niente.

Se la versione di un tool non coincide con quella di RuscaLinux,
`make-debs.sh` costruisce lo stesso ma lo segnala alla fine. Quando qualcosa
fallisce mostra le ultime righe; il resto è in `local/make-debs.log`.

## Pubblicare

Tutto a mano. Sono quattro passi, un paio di volte l'anno.

**1. SourceForge** — <https://sourceforge.net/projects/ruscalinux/files/>
Crea la cartella con il numero di versione e caricaci dentro i cinque file che
`build.sh` ha lasciato in `.work/`:

- la ISO
- `SHA256SUMS`
- `ruscalinux-<versione>-amd64.packages` (l'elenco dei pacchetti installati)
- `README.md` e `INSTALL.md` (le istruzioni per chi scarica)

Poi imposta la ISO come download predefinito per Linux.

**2. Git**

```sh
git add -A
git commit -m "Release 2.0"
git tag -a v2.0 -m "RuscaLinux 2.0"
git push origin main --tags
```

**3. GitHub** — <https://github.com/ruscalinux/ruscalinux/releases/new>
Tag `v2.0`, titolo `RuscaLinux 2.0`, e nel testo incolla il contenuto di
`RELEASE-NOTES-2.0.md`. Allega `SHA256SUMS`, non la ISO: quella sta su
SourceForge.

**4. Sito** — aggiorna versione, nome del file e sha256 nella pagina download.

Il checksum **copialo**, non riscriverlo: sta in `RELEASE-NOTES-2.0.md` ed è
lungo 64 caratteri. Se lo sbagli, la verifica fallisce a chiunque scarichi e
non ricevi alcun segnale — te lo dice solo qualcuno che scrive per lamentarsi.

## I documenti per chi scarica

`dist/README.md` e `dist/INSTALL.md` sono i due file pubblicati su SourceForge
accanto alla ISO. Sono **modelli**: al posto della versione, del nome del file,
del checksum e del numero di pacchetti contengono `@VERSION@`, `@ISO@`,
`@SHA256@`, `@PACCHETTI@` e `@NVIDIA@`, che `build.sh` sostituisce con i valori veri.

Erano ventitré punti da correggere a mano a ogni rilascio, in due lingue. Ora
si modificano solo quando cambia il *contenuto* — un'applicazione aggiunta,
una sezione riscritta — mai per un cambio di versione.

Il numero di pacchetti non è scritto da nessuna parte: lo conta `build.sh` dal
file `.packages` che live-build produce insieme alla ISO.

## Le novità di ogni versione

Prima di lanciare `build.sh`, apri `RELEASE-NOTES.md` e riscrivi la sezione
**Highlights**. È l'unica parte scritta a mano: versione, nome del file, peso,
checksum e data li mette `build.sh`, quindi le note non possono mai
contraddire la ISO che hai davvero costruito.
