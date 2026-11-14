# Driver NVIDIA

La ISO di RuscaLinux contiene anche il driver dal repository ufficiale NVIDIA
per Debian 13, con i moduli del kernel aperti, ma **si avvia e si installa
con i driver liberi**. Il driver NVIDIA si sceglie nel menu di avvio.

Il codice sta in `steps/40-nvidia.sh`, che `build.sh` esegue dopo i tre passi
standard. Le impostazioni sono in `release.conf` (`NVIDIA_PIN`, `NVIDIA_REPO`).

## Il menu di avvio

| Voce | Driver | Parametri aggiunti |
|---|---|---|
| Live system (amd64) — predefinita | liberi | `modprobe.blacklist=nvidia,nvidia_drm,nvidia_modeset,nvidia_uvm` |
| Live system (amd64) with NVIDIA driver | NVIDIA | `modprobe.blacklist=nouveau rusca.driver=nvidia` |
| Live system (amd64 fail-safe mode) | liberi | come la prima |
| Start installer | liberi | — |
| Start installer with NVIDIA driver | NVIDIA | `rusca.driver=nvidia` |

Le voci NVIDIA sono copie delle voci con i driver liberi, aggiunte subito
sotto da un hook binario nei menu GRUB (UEFI) e isolinux (BIOS). Il menu
avanzato dell'installer (“Advanced install options”) resta con i soli
driver liberi. Se live-build cambiasse il formato dei menu, la build lo
segnala con un'ATTENZIONE.

Tutto dipende da `rusca.driver=nvidia` sulla riga di avvio.

**Sessione live.** Con i driver liberi i moduli NVIDIA sono esclusi e il
pannello `nvidia-settings` è nascosto. Con il driver NVIDIA è nouveau a
essere escluso, e il servizio `ruscalinux-driver-mode`, prima che parta il
desktop, rende visibile il pannello e lo mette nella cartella Sistema.

**Installazione.** Se l'installer è partito dalla voce NVIDIA, il
`late_command` del preseed lascia un segno in `/tmp/ruscalinux-driver-nvidia`
e `/usr/lib/ruscalinux/nvidia-postinstall`, alla fine dell'installazione:

- **driver liberi:** rimuove driver, pannello e tutti i file NVIDIA di
  RuscaLinux dal sistema installato (il sistema è offline: apt rimuove
  soltanto, non scarica niente);
- **driver NVIDIA:** aggiunge a GRUB `modprobe.blacklist=nouveau
  rusca.driver=nvidia` e una seconda voce, “RuscaLinux with free drivers
  (without NVIDIA driver)”, da usare se il driver NVIDIA dà problemi. Con
  quella voce il pannello torna nascosto.

La scelta fatta durante l'installazione è definitiva, ed è voluto: chi
installa con i driver liberi non ha il driver NVIDIA sul disco, e per averlo
reinstalla con la voce “Start installer with NVIDIA driver”.

## Schede supportate

Il repository NVIDIA per Debian 13 parte dal ramo 590, che supporta solo GPU
**Turing e successive**: GTX 16, RTX 20, 30, 40 e 50, sia desktop sia
portatili. Le schede precedenti (Maxwell, Pascal, Volta: GTX 900 e 1000)
usano i driver liberi.

Le RTX 50 (Blackwell) funzionano solo con i moduli aperti, che sono quelli
che usiamo.

## Preparazione, una volta sola

**Chiave del repository NVIDIA.** Si scarica una volta, si registra la sua
impronta e si conserva in git. `build.sh` rifiuta di costruire se la chiave
non corrisponde all'impronta.

```sh
mkdir -p local/nvidia && cd local/nvidia
wget https://developer.download.nvidia.com/compute/cuda/repos/debian13/x86_64/cuda-keyring_1.1-1_all.deb
dpkg-deb -x cuda-keyring_1.1-1_all.deb /tmp/cuda-keyring     # estrae, non installa
cp /tmp/cuda-keyring/usr/share/keyrings/cuda-archive-keyring.gpg .
rm cuda-keyring_1.1-1_all.deb
gpg --show-keys cuda-archive-keyring.gpg     # proprietario: Kitmaker (Debian 13 Trixie) <kitmaker@nvidia.com>
sha256sum cuda-archive-keyring.gpg > SHA256SUMS
cd ../.. && git add local/nvidia
```

**Programmi in più sulla macchina di build:** `sudo apt install openssl
squashfs-tools`.

**Chiave di firma dei moduli (Secure Boot).** Alla prima build `build.sh`
la crea in `~/.local/share/ruscalinux/mok/` (oppure nella cartella indicata
da `RUSCALINUX_MOK_DIR`). Con questa chiave si firmano i moduli NVIDIA; nella
ISO entra solo il certificato pubblico,
`/usr/share/ruscalinux/nvidia/ruscalinux-mok.der`.

- **Fanne una copia di riserva.** Se la perdi, ogni utente che ha registrato
  il vecchio certificato dovrà registrare il nuovo.
- **Non metterla mai in git** e non copiarla nel repository.
- L'hook la cancella dal sistema della ISO, e `build.sh` controlla che non ci
  sia.
- L'hook stesso la contiene, in base64: `build.sh` lo cancella da `.work/`
  quando finisce, anche se la build si ferma per un errore. Con
  `./build.sh --config` resta, per poterlo leggere: `./build.sh --clean` lo
  cancella.

## Scegliere la versione del driver

`NVIDIA_PIN` in `release.conf` è il suffisso del pacchetto
`nvidia-driver-pinning-*`:

- un ramo (`620`) segue gli aggiornamenti di quel ramo: **è la scelta di
  RuscaLinux**, così ogni build prende l'ultima versione con le sue
  correzioni;
- una versione esatta (`620.70.06`) fissa il driver: serve solo se una
  versione nuova del ramo desse problemi.

Con il ramo, due build fatte in giorni diversi possono avere driver diversi.
Per questo, prima di pubblicare, si controlla la riga `nvidia` che
`build.sh` stampa alla fine: deve essere la versione provata su hardware
vero. Se è cambiata dopo le prove, si riprova o si fissa per quella build la
versione provata. Conviene che la versione sia pubblicata da almeno due
settimane. Le versioni disponibili si vedono nell'indice del repository
(`NVIDIA_REPO`), cercando i file `nvidia-driver-pinning-*`.
(llama.cpp invece segue da solo l'ultima release stabile: vedi
`tools/ruscallama-engine/README.md`.)

La versione davvero installata nella ISO la legge `build.sh` dal file
`.packages` e la scrive al posto di `@NVIDIA@` nelle note di rilascio e nei
documenti per chi scarica.

**Aggiornamenti di sicurezza.** Il sistema installato non ha repository:
il driver resta quello della ISO. Quando NVIDIA pubblica un bollettino di
sicurezza che riguarda il ramo in uso (<https://www.nvidia.com/en-us/security/>),
si aggiorna `NVIDIA_PIN` e si pubblica una nuova ISO.

## Componente CUDA e nvidia-smi

Il driver per il desktop non comprende `nvidia-smi`. Dal ramo 590 il
pacchetto `nvidia-smi` del repository NVIDIA è vuoto (pacchetto di
transizione): il programma sta in `nvidia-driver-cuda`, la componente CUDA
del driver, che contiene anche ciò che serve ai programmi CUDA e OpenCL
(Blender, DaVinci Resolve…). Non è il CUDA Toolkit per sviluppatori.

La ISO la include per default. Con `NVIDIA_CUDA="no"` in `release.conf` la si
esclude e la ISO diventa più piccola; la build stampa quanto pesa
(“Componente CUDA: … pacchetti, circa … MB installati”). RuscaLLama e
RuscaTranslator non ne hanno bisogno: usano Vulkan.

## Il pannello NVIDIA

Con il driver NVIDIA, `nvidia-settings` compare nella cartella **Sistema**
della griglia delle applicazioni, non nella pagina principale. Con i driver
liberi non compare: nella sessione live è nascosto, sul sistema installato
non c'è.

GNOME Shell crea le cartelle Sistema e Utilità al primo accesso di ogni
utente, con un elenco fisso di applicazioni, e la cartella Sistema non tiene
conto delle categorie dei file `.desktop`. Per questo
`/usr/lib/ruscalinux/nvidia-settings-in-sistema`, avviato all'accesso da
`/etc/xdg/autostart/`, aggiunge il pannello all'elenco dopo che GNOME l'ha
creato. Lo fa una volta sola per utente (il segno è in
`~/.config/ruscalinux/`): se l'utente sposta il pannello, resta dove l'ha
messo.

Perché la griglia non resti con un posto vuoto, ogni nuovo utente nasce con
il pannello nascosto anche nella propria cartella
(`/etc/skel/.local/share/applications/nvidia-settings.desktop`): GNOME
dispone la griglia senza il pannello. Lo script lo mette nella cartella
Sistema e solo dopo toglie quel file, così il pannello compare direttamente
nella cartella. Qualche secondo dopo, come ulteriore sicurezza, azzera le
posizioni salvate delle icone (`org.gnome.shell app-picker-layout`) e GNOME
le ridispone in ordine alfabetico.

Il pannello è nascosto da un file con lo stesso nome in
`/usr/local/share/applications/` (`Hidden=true`), che ha la precedenza su
quello del pacchetto. Il servizio `ruscalinux-driver-mode` lo toglie o lo
rimette a ogni avvio, secondo la riga di avvio.

Con Wayland nvidia-settings mostra meno pagine che con X11: le impostazioni
dei monitor si fanno da Impostazioni → Schermi di GNOME.

## PC desktop e portatili con grafica ibrida

**Desktop.** Il monitor è collegato alla scheda NVIDIA: GNOME gira sulla
NVIDIA, con Wayland. Per la sospensione con Wayland l'hook imposta
`NVreg_PreserveVideoMemoryAllocations=1` e attiva i servizi
`nvidia-suspend`/`nvidia-resume`/`nvidia-hibernate`; senza queste due cose
GDM disattiva Wayland sulle schede NVIDIA. La memoria video si salva in
`/var/tmp`, perché su trixie `/tmp` è in RAM.

**Portatili ibridi** (per esempio Ryzen + RTX). Lo schermo interno è
collegato alla grafica integrata: GNOME gira su quella e la scheda NVIDIA si
accende solo per i programmi che la chiedono (“Avvia usando la scheda grafica
dedicata”, nel menu delle applicazioni; serve `switcheroo-control`, incluso
in ogni caso). Su molti portatili l'uscita HDMI è collegata alla NVIDIA: con
i driver liberi il monitor esterno funziona solo se nouveau lo gestisce.

I servizi NVIDIA hanno una condizione: partono solo se il driver è caricato.
Con i driver liberi systemd li salta e la sospensione funziona normalmente.

## Secure Boot

I moduli sono firmati con la chiave RuscaLinux, non con quella di Debian. Con
Secure Boot attivo si caricano solo dopo aver registrato il certificato, una
volta per computer. Si può fare dalla sessione live avviata con il driver
NVIDIA o dal sistema installato:

```sh
sudo mokutil --import /usr/share/ruscalinux/nvidia/ruscalinux-mok.der
```

`mokutil` chiede una password da usare una volta sola. Al riavvio compare
MokManager (schermata blu): **Enroll MOK → Continue → Yes**, si scrive la
password e si riavvia. In alternativa si disattiva Secure Boot nel firmware.

Finché il certificato non è registrato, la voce NVIDIA parte lo stesso: il
desktop usa la grafica integrata (portatili ibridi) o una grafica di base
senza accelerazione (desktop).

Sui portatili **Acer** l'opzione Secure Boot nel BIOS (F2 all'accensione)
resta grigia finché non si imposta una password supervisore nella scheda
Security.

Questa sezione va riportata nelle istruzioni per chi scarica la ISO.

## Prove prima di un rilascio

QEMU non ha una GPU NVIDIA: `./test.sh` verifica che le voci ci siano e che
il desktop parta con tutte. Il resto va provato su hardware vero, almeno un
desktop e un portatile ibrido.

**Driver liberi**

1. Il desktop parte; `lsmod | grep nvidia` non mostra niente; il pannello
   NVIDIA non c'è nella griglia delle applicazioni.
2. Installazione con “Start installer”: sul sistema installato
   `dpkg -l | grep nvidia` non mostra pacchetti installati e nel menu GRUB
   non ci sono voci NVIDIA.

**Driver NVIDIA**

3. `nvidia-smi` mostra la scheda; in Impostazioni → Sistema → Informazioni la
   sessione è Wayland; il pannello NVIDIA è nella cartella Sistema.
4. Portatile ibrido: `switcherooctl list` mostra due schede; un programma
   avviato con la scheda dedicata compare in `nvidia-smi`; a desktop fermo
   `/sys/bus/pci/devices/<indirizzo>/power/runtime_status` della NVIDIA dice
   `suspended`.
5. Monitor esterno.
6. Sospensione e ripresa, con un programma aperto sulla NVIDIA.
7. RuscaLLama con un modello: `llama-server` compare in `nvidia-smi`. Sui
   portatili ibridi controlla che usi la NVIDIA e non la grafica integrata:
   `/usr/lib/ruscallama-engine/llama-server --list-devices`.
8. Secure Boot attivo: registrazione del certificato con `mokutil`, poi
   `nvidia-smi`.
9. Installazione con “Start installer with NVIDIA driver” e ripetizione dei
   punti 3–7; nel menu GRUB c'è “RuscaLinux with free drivers (without NVIDIA
   driver)”, e con quella voce il pannello è nascosto.

## Da verificare alla prima build

Questi punti dipendono dalla versione di live-build e dai pacchetti NVIDIA
del momento. La build stampa un messaggio per ognuno:

- “Menu GRUB (live)”, “Menu GRUB (installer)” e le righe isolinux: le voci
  NVIDIA sono state aggiunte;
- “Modulo nvidia per …: firmato”: DKMS o l'hook hanno firmato i moduli;
- “Pannello NVIDIA: nvidia-settings.desktop presente”;
- “Blacklist di nouveau neutralizzato: …”: i file dei pacchetti NVIDIA che
  escludevano nouveau;
- “Controllo chiave privata: assente dalla ISO”.
