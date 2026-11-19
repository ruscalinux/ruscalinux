# RuscaLLama 1.99.3 — Manuale

**Versione** 1.99.3 · **Autore** Nunzio Curcuruto · **Distribuzione** RuscaLinux ([ruscalinux.org](https://www.ruscalinux.org/)) · **Licenza** GNU GPL v3 o successiva

RuscaLLama è una chat con modelli linguistici che girano **interamente su questo computer**. Il modello viene eseguito da **ruscallama-engine**, cioè llama.cpp: un componente esterno con licenza MIT, compilato per RuscaLinux. La vista **Immagini** crea immagini da una descrizione con **ruscadiffusion-engine**, cioè stable-diffusion.cpp, anch’esso con licenza MIT (sezione 7); la vista **Video** crea brevi video con lo stesso motore (sezione 8).

Il motore Markdown comune include un componente esterno: la regola dell'evidenziato `==testo==`, porting del plugin [markdown-it-mark](https://github.com/markdown-it/markdown-it-mark) (licenza MIT, © Vitaly Puzrin e Alex Kocharin; struttura in Python da markdown-it-py, © ExecutableBookProject), nel file a sé `markdown_it_mark.py`.

---

## 1. Requisiti

- RuscaLinux o Debian Stable, GNOME;
- Python ≥ 3.10, GTK ≥ 4.18, libadwaita ≥ 1.7, GtkSourceView 5;
- il pacchetto `ruscallama-engine`, e `ruscadiffusion-engine` per le immagini e i video;
- almeno un modello in formato **GGUF**.

Quanta memoria serve dipende dal modello: come regola pratica, un po' più della dimensione del file GGUF, più la memoria del contesto.

## 2. Dove mettere i modelli

RuscaLLama cerca i file `.gguf` in:

- `~/.local/share/ruscallama/models/` — i tuoi modelli (dalle impostazioni: **Apri la cartella dei modelli**);
- `/usr/share/ruscallama/models/` — modelli installati per tutti gli utenti.

Puoi anche scegliere un file in qualunque cartella con **Scegli un file…**. Accanto al modello possono stare:

- un file `mmproj-….gguf`: abilita la **Visione** (lettura delle immagini);
- una bozza `…mtp….gguf` piccola: abilita la **Decodifica speculativa**.

## 3. La finestra

- **Barra del titolo**: a sinistra **+** (nuova conversazione); al centro le tre viste, **Chat**, **Immagini** e **Video** (nelle finestre strette scendono in basso); a destra il pulsante del pannello delle impostazioni e il menu principale.
- **Conversazione**: le risposte compaiono mentre vengono generate. I blocchi di codice sono evidenziati e hanno un pulsante per copiarli. Ogni risposta ha **Copia la risposta** e un menu per salvarla in Markdown o salvarne i blocchi di codice.
- **Ragionamento**: se è attivo, il ragionamento del modello compare in una sezione richiudibile sopra la risposta.
- **Barra in basso**: allegati, casella del messaggio, **Invia** (che diventa **Ferma** durante la risposta); sotto, il modello caricato o lo stato del motore e la velocità in token al secondo.
- **Avvisi in alto**: motore mancante, nessun modello, caricamento in corso, impostazioni da applicare con un riavvio.

Il motore parte da solo al primo messaggio e si ferma alla chiusura della finestra.

## 4. Impostazioni del modello

Il pannello laterale (F9) ha quattro gruppi.

| Gruppo | Opzione | Effetto |
|---|---|---|
| Testo | Dimensione del testo | Dimensione della conversazione e del messaggio; anche con Ctrl++ e Ctrl+−, Ctrl+0 torna a quella di sistema |
| Modello | Modello | Scelta tra i GGUF trovati |
| Risposte | Stile | *Preciso*, *Equilibrato*, *Per ragionare*, *Creativo* o *Personalizzato* |
| Risposte | Ragionamento | Il modello pensa prima di rispondere; vale subito, senza riavvio |
| Risposte | Profondità del ragionamento | Bassa, media, alta |
| Risposte | Istruzioni per il modello | Il messaggio di sistema |
| Risposte | Parametri di campionamento | Temperatura, top-p, top-k, min-p, penalità, seme; cambiarne uno porta lo stile su *Personalizzato* |
| Motore | Scheda grafica (Vulkan) | Molto più veloce; spegnila se il driver dà problemi |
| Motore | Scheda da usare | Automatica, oppure una delle schede del computer. Nei portatili con due schede grafiche scegli quella dedicata (per esempio NVIDIA) |
| Motore | Thread della CPU | Consigliati tanti quanti i core fisici |
| Motore | Contesto | Token che il modello tiene a mente |
| Motore | Memoria del contesto | Precisione piena o compressa (consigliata) |
| Motore | Flash Attention | Automatica, attiva o disattiva |
| Motore | Visione, Decodifica speculativa | Disponibili solo con i file adatti accanto al modello |

Le opzioni del gruppo **Motore** valgono al riavvio del motore: quando ne cambi una, un avviso in alto offre **Riavvia il motore**.

## 5. Allegati

Con la graffetta (Ctrl+O) puoi allegare file di testo e codice (fino a 512 KB) e immagini (fino a 8 MB, solo con la Visione attiva). Il testo degli allegati viene aggiunto al messaggio.

## 6. Salvare

Dal menu principale: **Salva la conversazione in Markdown…** (Ctrl+S) o **in HTML…**. Dal menu di ogni risposta: **Salva la risposta in Markdown…** e **Salva i blocchi di codice…**, che scrive un file per blocco nella cartella scelta, senza mai sovrascrivere file esistenti.

## 7. Immagini

La vista **Immagini** (in alto, accanto a **Chat**; Alt+2) crea immagini da una descrizione, con un modello per immagini che gira su questo computer. Il motore è **ruscadiffusion-engine**, cioè stable-diffusion.cpp: un componente esterno con licenza MIT, compilato per RuscaLinux. Parte a ogni immagine e si chiude appena ha finito: non apre porte e non usa la rete.

### Il modello

La prima volta la vista Immagini mostra che cosa serve: un modello è fatto di **tre file** (il modello, il codificatore di testo e il VAE) da mettere insieme in una cartella. **Quali file scaricare?** elenca i file dei modelli consigliati con le pagine da cui scaricarli, e **Crea la cartella e aprila** prepara la cartella con il nome giusto: copia lì i tre file e il modello compare da solo. Se manca un file, o se hai copiato un file nella cartella dei modelli della chat, un avviso in alto lo dice.

Copialo in `~/.local/share/ruscadiffusion/models/` (pannello laterale → **Apri la cartella dei modelli**), oppure lascialo dov’è e scegli **Aggiungi una cartella…**: RuscaLLama ricorda la cartella senza copiare i file. Un modello può essere:

- **un file solo** `.safetensors`, `.gguf` o `.ckpt`, con tutto dentro: Stable Diffusion 1.5, SDXL, SD-Turbo, SDXL-Turbo;
- **una cartella** con il modello e i suoi componenti: per FLUX il modello, `ae.safetensors`, `clip_l` e `t5xxl`; per Z-Image il modello, `ae.safetensors` e il modello linguistico Qwen; per Stable Diffusion 3.5 anche `clip_g`.

RuscaLLama riconosce i file da solo e sceglie passi, CFG e campionatore consigliati per quel modello: vanno bene anche FLUX.2, Qwen-Image, Chroma e gli altri modelli recenti che stable-diffusion.cpp supporta. Per un inizio facile: **Z-Image-Turbo** (licenza Apache 2.0), che con 8 passi fa immagini di qualità e in versione Q3_K funziona anche con 4 GB di memoria video. Ogni modello ha la sua licenza.

### Creare un’immagine

1. Scrivi cosa vuoi vedere nella casella in basso. Più dettagli dai (soggetto, luogo, luce, stile), più l’immagine ti somiglierà.
2. Scegli **Quadrata**, **Orizzontale** o **Verticale**.
3. Premi **Genera** (Invio). Mentre lavora vedi un’anteprima che prende forma e il passo a cui è arrivato; **Ferma** (Esc) interrompe.

Clicca un’immagine per vederla grande. Dal suo menu: **Salva l’immagine…**, **Copia l’immagine**, **Allega alla conversazione** (per farla descrivere a un modello con la Visione), **Riusa il seme** (riparti dalla stessa immagine cambiando un po’ la descrizione), **Togli**.

Anche una risposta della chat può diventare una descrizione: menu della risposta → **Crea un’immagine da questa risposta**. Chiedi per esempio al modello di scrivere un prompt dettagliato in inglese, poi usalo.

Le immagini restano nel programma finché non lo chiudi: **salva quelle che vuoi tenere**. Alla chiusura RuscaLLama chiede conferma se ce ne sono di non salvate.

### Impostazioni delle immagini

Con la vista Immagini aperta, il pannello laterale (F9) mostra queste impostazioni.

| Gruppo | Opzione | Effetto |
|---|---|---|
| Modello per le immagini | Modello | Scelta tra i modelli trovati; sotto il nome, se è un file solo o una cartella |
| Modello per le immagini | Aggiungi una cartella…, Togli la cartella dall’elenco | Usa o dimentica una cartella di modelli; i file non si spostano |
| Immagine | Qualità | Veloce, Normale, Dettagliata: più passi, più dettagli, più tempo. Non vale per i modelli distillati (Turbo, schnell, klein…), che hanno un numero di passi fisso |
| Immagine | Immagini per volta | Da 1 a 4, con la stessa descrizione |
| Immagine | Da evitare | Ciò che non vuoi nell’immagine (prompt negativo); i modelli FLUX e Turbo ne tengono poco conto |
| Immagine | Scrivi la descrizione nel file | Spenta: il PNG salvato non contiene descrizione e impostazioni |
| Immagine | Impostazioni avanzate | Passi, aderenza alla descrizione (CFG), dimensione di base, campionatore, seme. 0, «Automatico» e −1 usano i valori consigliati per il modello (scritti sotto ogni voce) o un seme a caso |
| Motore delle immagini | Scheda grafica, Scheda da usare, Thread | Come per la chat. Con «Automatica» il motore sceglie la scheda dedicata; ciò che non ci sta resta nella RAM e passa sulla scheda a pezzi |
| Motore delle immagini | Codificatore di testo | Sulla stessa scheda, sul processore o su un’altra scheda. Con due schede (per esempio una NVIDIA con poca memoria e una Radeon integrata) mettilo sulla seconda: la prima resta tutta per il modello, che lavora a ogni passo |
| Motore delle immagini | Risparmia memoria | Tiene tutti i pesi nella RAM. Più lento: lasciala spenta, e provala solo se il motore si ferma per mancanza di memoria video |

## 8. Video

La vista **Video** (in alto, accanto a **Immagini**; Alt+3) crea brevi video, di qualche secondo, da una descrizione o da un’immagine di partenza. Usa lo stesso motore delle immagini, **ruscadiffusion-engine**, con un modello per i video: il video è un file AVI (Motion JPEG), che RuscaLLama riproduce da sé. Un video richiede molta più memoria e molto più tempo di un’immagine: con una scheda da 6 GB conta diversi minuti per una clip di 2 secondi a circa 480p.

### Il modello per i video

Come per le immagini, un modello per i video è fatto di **tre file**: il modello, il codificatore di testo (UMT5-XXL per Wan) e il VAE. Vanno nella stessa cartella dei modelli per immagini, `~/.local/share/ruscadiffusion/models/`, ognuno nella sua sottocartella: RuscaLLama riconosce da sé i modelli per i video e li mostra solo nella vista Video. **Quali file scaricare?** consiglia:

- **Wan2.2-TI2V-5B** (licenza Apache 2.0): la qualità migliore per una scheda di casa, da una descrizione o da un’immagine, 24 fotogrammi al secondo. Il VAE è `wan2.2_vae.safetensors`, non quello di Wan 2.1;
- **Wan2.1-T2V-1.3B** (licenza Apache 2.0): più leggero e veloce, solo da una descrizione, 16 fotogrammi al secondo.

Vanno bene anche Wan 2.1 e 2.2 da 14 miliardi di parametri (molto più lenti), HunyuanVideo 1.5 e LingBot-Video. Wan 2.2 A14B è fatto di due modelli, `HighNoise` e `LowNoise`, da mettere nella stessa cartella; Wan 2.1 I2V vuole anche `clip_vision_h.safetensors`. I modelli che partono da un audio o da un video (S2V, VACE, Animate) non funzionano con RuscaLLama: un avviso lo dice.

### Creare un video

1. Descrivi la scena **e il movimento**: chi o che cosa si muove, come, e cosa fa la telecamera.
2. Con i modelli che la usano compare il pulsante dell’**immagine di partenza** accanto alla casella: il video comincia da quell’immagine. Dalla vista Immagini, il menu di un’immagine → **Anima in un video** la porta qui.
3. Scegli il formato e premi **Crea il video**. Durante il lavoro vedi un fotogramma dell’anteprima, il passo e il tempo che manca; **Ferma** (Esc) interrompe.

Clicca un video per guardarlo. Dal suo menu: **Salva il video…** (nella cartella Video), **Apri nel lettore video**, **Riusa il seme**, **Togli**. Se GTK non sa riprodurre il video (mancano `libgtk-4-media-gstreamer` o `gstreamer1.0-plugins-good`) vedi un fotogramma e il pulsante per aprirlo nel lettore del sistema.

Si crea un video o un’immagine per volta: mentre una delle due viste lavora, l’altra aspetta.

### Impostazioni dei video

Le impostazioni della vista Video sono quelle delle immagini, con queste differenze:

| Opzione | Effetto |
|---|---|
| Durata | 2, 3 o 5 secondi. Il tempo e la memoria crescono più che in proporzione |
| Da evitare | Vuota: per Wan si usa il prompt negativo predefinito del modello |
| Impostazioni avanzate | Come per le immagini; la dimensione di base consigliata è 640 (circa 480p) |
| Motore (immagini e video) | Le stesse impostazioni della vista Immagini: cambiarle in una vista vale anche per l’altra. Con una scheda da 6 GB metti il **Codificatore di testo** sul processore |

## 9. Scorciatoie da tastiera

| Tasti | Azione |
|---|---|
| Alt+1 / Alt+2 / Alt+3 | Vista Chat / Immagini / Video |
| Invio | Invia (nella vista Immagini: Genera; nella vista Video: Crea il video) |
| Maiusc+Invio | A capo |
| Esc | Ferma la risposta, l’immagine o il video |
| Ctrl+N | Nuova conversazione |
| Ctrl+O | Allega file |
| Ctrl+S | Salva la conversazione in Markdown |
| F9 | Impostazioni del modello |
| Ctrl++ / Ctrl+− / Ctrl+0 | Testo più grande / più piccolo / dimensione di sistema |
| Ctrl+? | Scorciatoie da tastiera |
| F10 | Menu principale |
| Ctrl+W / Ctrl+Q | Chiudi la finestra / Esci |

## 10. Privacy e sicurezza

- Il motore ascolta solo su **127.0.0.1**, su una porta libera scelta a ogni avvio.
- Ogni avvio genera una **chiave di accesso temporanea**, salvata in `$XDG_RUNTIME_DIR/ruscallama/` con permessi 0600: gli altri utenti del computer non possono usare il modello né leggere le conversazioni.
- Il motore è compilato **senza** la possibilità di scaricare nulla da internet.
- Le conversazioni non vengono salvate da sole: restano in memoria finché non le salvi tu.
- Il motore ha un profilo AppArmor (in modalità *complain*) che gli nega le cartelle più delicate della home.
- Le impostazioni sono in `~/.config/ruscallama/settings.json`.

Per le immagini e i video:

- il motore delle immagini non ha codice di rete (niente server): parte, crea le immagini ed esce;
- la descrizione gli arriva in un file, non sulla riga di comando, dove la vedrebbero gli altri utenti del computer;
- le immagini e i video non salvati stanno in `~/.cache/ruscallama/images/` (permessi 0700) e si cancellano alla chiusura; l’immagine di partenza di un video viene copiata lì, e il motore non legge altro della home;
- il PNG salvato non contiene la descrizione, se non accendi **Scrivi la descrizione nel file**.

Le risposte di un modello linguistico possono essere sbagliate: verifica le informazioni importanti.

## 11. Risoluzione dei problemi

| Problema | Cosa fare |
|---|---|
| «ruscallama-engine non è installato» | `sudo apt install ruscallama-engine` |
| Il motore si ferma subito | Apri **Registro del motore** dal menu: spesso manca memoria; prova un modello più piccolo, meno contesto o la memoria del contesto compressa |
| Molto lento | Accendi **Scheda grafica (Vulkan)**; controlla il numero di thread |
| Il driver grafico si blocca | Spegni **Scheda grafica (Vulkan)** |
| Con la scheda grafica il modello non si carica, senza sì | In **Scheda da usare** scegli la scheda dedicata: su un portatile con due schede il motore può usare quella sbagliata |
| Le immagini non partono | Serve un file `mmproj` accanto al modello e la **Visione** attiva |
| «ruscadiffusion-engine non è installato» | `sudo apt install ruscadiffusion-engine` |
| Il modello per immagini non compare | Dev’essere `.safetensors`, `.gguf` o `.ckpt`; un modello in più file va in una cartella sua, con i suoi componenti |
| L’immagine non si crea | Menu principale → **Registro del motore delle immagini**: spesso manca memoria; accendi **Risparmia memoria**, scegli **Veloce** o un formato più piccolo |
| Il modello per video non compare | Dev’essere in una cartella sua con il VAE e il codificatore di testo; il nome del file o della cartella deve dire di che modello si tratta (Wan, HunyuanVideo, LingBot) |
| Il video non si crea | Menu principale → **Registro del motore dei video**: quasi sempre manca memoria; scegli 2 secondi, una dimensione di base più piccola, il codificatore di testo sul processore o **Risparmia memoria** |
| Il video non si vede | Installa `libgtk-4-media-gstreamer` e `gstreamer1.0-plugins-good`, oppure usa **Apri nel lettore video** |
| Immagini confuse o strane | Usa i valori consigliati (avanzate a 0 e «Automatico»); i modelli SD 1.5 lavorano a 512 px, SDXL e FLUX a 1024 |

Supporto: info@ruscalinux.org — La nota sull'uso di strumenti di intelligenza artificiale è nella finestra Informazioni e nel file `NOTA-IA.md` del repository.
