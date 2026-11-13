# RuscaCleaner — Manuale d'uso

**Versione** 1.99.3 · **Autore** Nunzio Curcuruto · **Distribuzione** RuscaLinux ([ruscalinux.org](https://www.ruscalinux.org/)) · **Licenza** GNU GPL v3 o successiva

---

## 1. Che cos'è

RuscaCleaner è un programma per il desktop GNOME che **rimuove dalla cartella home le tracce di attività**: miniature, file recenti, cronologie, appunti, indice di ricerca e cestino. Fa poche cose, le elenca tutte nella finestra e dichiara anche quelle che **non** fa.

---

## 2. Installazione

Requisiti: RuscaLinux o Debian Stable, GNOME, Python 3.10+, GTK 4.18+, libadwaita 1.7+.

```bash
sha256sum -c SHA256SUMS                                   # prima verifica l'integrità
sudo apt install ./ruscacleaner-ruscalinux_1.99.3_all.deb # installa anche le dipendenze
```

Per costruire il pacchetto dai sorgenti: `./make-deb.sh`. Pacchetto e `SHA256SUMS` vengono creati in `build-deb/`.

---

## 3. Cosa pulisce

| Voce | Cosa viene rimosso | Accesa all'avvio |
|---|---|---|
| **Miniature** | Anteprime di immagini e video: `~/.cache/thumbnails`, `~/.thumbnails` e le cache delle app Flatpak. Si rigenerano da sole. | ✅ |
| **File recenti** | L'elenco dei documenti aperti di recente (`recently-used.xbel`), app Flatpak incluse. | ✅ |
| **Cronologia degli appunti** | La cronologia salvata da GPaste e dall'estensione Clipboard Indicator. | ❌ |
| **Indice di ricerca** | `~/.cache/tracker3/files`: testo e dettagli che la ricerca di GNOME ha estratto dai tuoi file. Si ricostruisce da solo. | ❌ |
| **Metadati del gestore file** | `~/.local/share/gvfs-metadata`: note sui file aperti. | ❌ |
| **Registri di sessione** | `~/.xsession-errors` e i registri di Xorg, che possono contenere nomi di file. | ❌ |
| **Cestino** | File, metadati e cancellazioni interrotte nel cestino. | ❌ |
| **Cestino su altri dischi** | Le cartelle `.Trash-<uid>` delle chiavette e dei dischi secondari montati. | ❌ |

Nella riga espandibile **Cronologie di shell, strumenti ed editor** (tutte spente all'avvio):

| Voce | File |
|---|---|
| **Bash** | `~/.bash_history` |
| **Zsh** | `~/.zsh_history`, `~/.zhistory`, `~/.histfile`, `~/.local/share/zsh/history` |
| **Fish** | `~/.local/share/fish/fish_history` |
| **Strumenti da riga di comando** | Python, less, SQLite, PostgreSQL, MySQL, Node.js, Ruby (irb), Redis, R, Octave, gnuplot, Julia |
| **Editor** | Vim (`~/.viminfo`), Neovim (ShaDa), nano, Emacs (`recentf`, `history`): file aperti e ricerche |

Le cronologie delle shell vengono **azzerate**, non eliminate: il file conserva i suoi permessi.

**Perché queste impostazioni?** All'avvio è acceso solo ciò che si rigenera senza perdite. Tutto ciò che non si ricostruisce parte spento e va scelto da te, consapevolmente.

---

## 4. Uso della finestra

1. **Apri il programma.** Parte da sola un'analisi. L'elenco mostra solo le voci che hanno davvero qualcosa da rimuovere, ciascuna con la sua dimensione; se non c'è nulla, la finestra dice «Niente da pulire».
2. **Scegli** cosa pulire con gli interruttori. Le cronologie di shell, strumenti ed editor sono in un gruppo a parte. Il totale, nella barra in basso, si aggiorna a ogni modifica.
3. **Premi «Pulisci ora»** nella barra in basso. La finestra di conferma elenca **i percorsi reali dei file** e gli avvisi pertinenti, e ha **«Annulla»** come pulsante predefinito.
4. **Leggi l'esito** nella notifica in basso. Il pulsante **«Dettagli»** apre il registro: ogni elemento eliminato, ogni elemento saltato con il motivo e il totale liberato. Dopo la pulizia l'elenco si aggiorna da solo.

Il pulsante **⟳** in alto a sinistra ricalcola le dimensioni. Il menu in alto a destra contiene:

- **Solo simulazione:** prova senza cancellare nulla. Finché è attiva, una striscia in alto lo ricorda (con il pulsante «Disattiva») e il pulsante in basso diventa «Simula».
- **Cosa non fa:** i limiti dichiarati (§6.3).
- **Scorciatoie da tastiera** e **Informazioni** (versione, collegamenti a sito, supporto e licenza, nota di sviluppo).

La finestra non si chiude mentre è in corso una cancellazione.

La finestra segue lo stile chiaro o scuro di GNOME, ricorda la propria dimensione e si usa anche da tastiera:

| Tasti | Azione |
|---|---|
| F5 o Ctrl+R | Ricalcola le dimensioni |
| Ctrl+? | Scorciatoie da tastiera |
| F10 | Menu principale |
| Ctrl+W | Chiudi la finestra |
| Ctrl+Q | Esci |

---

## 5. Riga di comando

```
ruscacleaner              apre la finestra
ruscacleaner --list       elenca voci e dimensioni, non tocca nulla
ruscacleaner --dry-run    simula le voci predefinite, non cancella nulla
ruscacleaner --version    mostra la versione
```

Da riga di comando il programma **non cancella mai**: la cancellazione vera avviene solo dalla finestra, dopo la conferma. `--allow-root` disattiva una protezione (§7) e non va usato nell'uso normale.

---

## 6. Privacy

### 6.1 Tutto resta sul tuo computer
RuscaCleaner non ha funzioni di rete: nessun server, nessuna statistica, nessun account, nessun download. Il codice sorgente GPL permette a chiunque di verificarlo.

### 6.2 Cancellare non è distruggere per sempre
È una normale cancellazione, **non una cancellazione sicura**. Uno strumento forense, uno snapshot btrfs o un backup possono conservare ancora i vecchi dati. Se un file non deve più esistere in alcuna forma servono la cifratura del disco e una gestione attenta di snapshot e backup.

### 6.3 Cosa NON viene pulito
- **I dati dei browser** (cronologia, cookie, cache): i browser hanno strumenti propri, più completi.
- **Il journal di sistema**: richiede i permessi di amministratore.
- **Le statistiche d'uso delle app di GNOME Shell**: la Shell le tiene in memoria e le riscrive.
- **Le impostazioni delle singole applicazioni** (per esempio gli elenchi di file recenti dentro i loro file di configurazione).
- **`~/.ssh/known_hosts` e `~/.wget-hsts`**, conservati di proposito: proteggono le tue connessioni da sostituzioni di identità e da attacchi di declassamento.

### 6.4 Consigli per una pulizia efficace
Molti programmi riscrivono le proprie tracce quando si chiudono: pulirle con il programma aperto serve a poco. La finestra di conferma lo ricorda:
- chiudi le **applicazioni** prima di pulire i *file recenti*;
- chiudi i **terminali** (o esegui `history -c` in ciascuno) prima di pulire le cronologie delle shell, e chiudi **editor e strumenti** prima di pulire le loro;
- svuota il **gestore degli appunti** anche dal suo menu, o riavvialo;
- dopo aver pulito l'**indice di ricerca**, esci e rientra nella sessione;
- dopo aver pulito i **metadati del gestore file**, riavvia il gestore file;
- il *cestino su altri dischi* è visibile solo per i dischi **montati in quel momento**.

---

## 7. Sicurezza: protezioni integrate

1. **Rifiuta di girare come root** (sudo, su, pkexec, shell di root).
2. **Verifica che la home appartenga a te**, coprendo anche i casi che il solo controllo di `SUDO_USER` non vede.
3. **Resta nei confini**: solo la tua home e i cestini convalidati dei dischi montati (sotto `/media/<utente>`, `/run/media/<utente>` o `/media`, su un vero punto di mount, con nome `.Trash-<uid>` o `.Trash/<uid>`, di tua proprietà, non un collegamento).
4. **Non segue mai i collegamenti simbolici**: `lstat` per riconoscerli, `O_NOFOLLOW` quando azzera un file. Un collegamento viene saltato e segnalato.
5. **Controlla il proprietario di ogni elemento**: i file di altri utenti vengono saltati.
6. **Chiede sempre conferma** con i percorsi reali; il pulsante predefinito è "Annulla".
7. **Simulazione**: `--dry-run` e "Solo simulazione" mostrano tutto e non cancellano nulla.
8. **Nessun lavoro a metà**: la finestra non si chiude durante una cancellazione, un elemento che fallisce riguarda solo sé stesso e lo spazio annunciato è solo quello sparito davvero.
9. **Traduzioni sicure**: i file di lingua sono accettati solo come coppie testo→testo, i nomi dei file sono convalidati e i segnaposto si sostituiscono senza `str.format()`.
10. **Calcoli robusti**: le dimensioni si calcolano in modo iterativo, così cartelle molto profonde non bloccano il programma.

---

## 8. Lingue

L'interfaccia è tradotta nelle lingue dei RuscaLinux OS Tools: sono i file della cartella `lang/`. Le traduzioni diverse da italiano e inglese sono fatte con l'assistenza di strumenti di intelligenza artificiale: le correzioni dei madrelingua sono benvenute (info@ruscalinux.org).

La lingua segue le impostazioni di sistema (`LANGUAGE`, poi `LC_ALL`, `LC_MESSAGES`, `LANG`). Una variante regionale ripiega sulla sua lingua (`de_AT` → `de`). Hong Kong e Macao usano il cinese tradizionale (`zh_TW`), il resto del cinese il semplificato (`zh_CN`); lo slovacco usa il ceco. Ciò che manca torna all'inglese. Per provare una lingua: `LANGUAGE=en ruscacleaner`.

---

## 9. Domande frequenti

**Quanto spazio libero?** Miniature, indice di ricerca e cestino possono occupare molti GB; le cronologie pochi kB. Per molti il vero valore è togliere le tracce, non lo spazio.

**Posso annullare una pulizia?** No. Il programma non conserva copie.

**Serve una connessione a internet?** No, mai.

**Come verifico cosa farebbe, senza rischi?** `ruscacleaner --dry-run`, oppure l'interruttore "Solo simulazione".

---

## 10. Breve glossario

- **Home**: la tua cartella personale (`/home/tuo-nome`, indicata con `~`).
- **Collegamento simbolico**: un file che punta soltanto a un altro; seguirlo alla cieca è il modo classico di cancellare la cosa sbagliata.
- **Punto di mount**: il punto in cui un disco o una chiavetta si aggancia all'albero delle cartelle.
- **UID**: il numero che identifica un utente, usato per stabilire a chi appartiene un file.
- **Snapshot**: una fotografia del filesystem che conserva le versioni precedenti dei file.

---

## 11. Licenza, contatti e nota IA

- **Licenza:** GNU GPL v3 o successiva, senza alcuna garanzia.
- **Supporto:** info@ruscalinux.org
- **Nota IA:** si trova nella finestra Informazioni del programma e nel file `NOTA-IA.md` del repository.
