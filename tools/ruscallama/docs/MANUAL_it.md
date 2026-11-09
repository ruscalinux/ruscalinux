# RuscaLLama 1.99.2 — Manuale

**Versione** 1.99.2 · **Autore** Nunzio Curcuruto · **Distribuzione** RuscaLinux ([ruscalinux.org](https://www.ruscalinux.org/)) · **Licenza** GNU GPL v3 o successiva

RuscaLLama è una chat con modelli linguistici che girano **interamente su questo computer**. Il modello viene eseguito da **ruscallama-engine**, cioè llama.cpp: un componente esterno con licenza MIT, compilato per RuscaLinux.

Il motore Markdown comune include un componente esterno: la regola dell'evidenziato `==testo==`, porting del plugin [markdown-it-mark](https://github.com/markdown-it/markdown-it-mark) (licenza MIT, © Vitaly Puzrin e Alex Kocharin), in `rusca_markdown.py`.

---

## 1. Requisiti

- RuscaLinux o Debian Stable, GNOME;
- Python ≥ 3.10, GTK ≥ 4.18, libadwaita ≥ 1.7, GtkSourceView 5;
- il pacchetto `ruscallama-engine`;
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

- **Barra del titolo**: a sinistra **+** (nuova conversazione); al centro nome del programma e stato del motore; a destra il pulsante del pannello delle impostazioni e il menu principale.
- **Conversazione**: le risposte compaiono mentre vengono generate. I blocchi di codice sono evidenziati e hanno un pulsante per copiarli. Ogni risposta ha **Copia la risposta** e un menu per salvarla in Markdown o salvarne i blocchi di codice.
- **Ragionamento**: se è attivo, il ragionamento del modello compare in una sezione richiudibile sopra la risposta.
- **Barra in basso**: allegati, casella del messaggio, **Invia** (che diventa **Ferma** durante la risposta) e la velocità in token al secondo.
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

## 7. Scorciatoie da tastiera

| Tasti | Azione |
|---|---|
| Invio | Invia |
| Maiusc+Invio | A capo |
| Esc | Ferma la risposta |
| Ctrl+N | Nuova conversazione |
| Ctrl+O | Allega file |
| Ctrl+S | Salva la conversazione in Markdown |
| F9 | Impostazioni del modello |
| Ctrl++ / Ctrl+− / Ctrl+0 | Testo più grande / più piccolo / dimensione di sistema |
| Ctrl+? | Scorciatoie da tastiera |
| F10 | Menu principale |
| Ctrl+W / Ctrl+Q | Chiudi la finestra / Esci |

## 8. Privacy e sicurezza

- Il motore ascolta solo su **127.0.0.1**, su una porta libera scelta a ogni avvio.
- Ogni avvio genera una **chiave di accesso temporanea**, salvata in `$XDG_RUNTIME_DIR/ruscallama/` con permessi 0600: gli altri utenti del computer non possono usare il modello né leggere le conversazioni.
- Il motore è compilato **senza** la possibilità di scaricare nulla da internet.
- Le conversazioni non vengono salvate da sole: restano in memoria finché non le salvi tu.
- Il motore ha un profilo AppArmor (in modalità *complain*) che gli nega le cartelle più delicate della home.
- Le impostazioni sono in `~/.config/ruscallama/settings.json`.

Le risposte di un modello linguistico possono essere sbagliate: verifica le informazioni importanti.

## 9. Risoluzione dei problemi

| Problema | Cosa fare |
|---|---|
| «ruscallama-engine non è installato» | `sudo apt install ruscallama-engine` |
| Il motore si ferma subito | Apri **Registro del motore** dal menu: spesso manca memoria; prova un modello più piccolo, meno contesto o la memoria del contesto compressa |
| Molto lento | Accendi **Scheda grafica (Vulkan)**; controlla il numero di thread |
| Il driver grafico si blocca | Spegni **Scheda grafica (Vulkan)** |
| Con la scheda grafica il modello non si carica, senza sì | In **Scheda da usare** scegli la scheda dedicata: su un portatile con due schede il motore può usare quella sbagliata |
| Le immagini non partono | Serve un file `mmproj` accanto al modello e la **Visione** attiva |

Supporto: info@ruscalinux.org — La nota sull'uso di strumenti di intelligenza artificiale è nella finestra Informazioni e nel file `NOTA-IA.md` del repository.
