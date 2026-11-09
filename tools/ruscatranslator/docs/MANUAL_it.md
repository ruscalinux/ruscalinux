# RuscaTranslator 1.99.2 — Manuale

**Versione** 1.99.2 · **Autore** Nunzio Curcuruto · **Distribuzione** RuscaLinux ([ruscalinux.org](https://www.ruscalinux.org/)) · **Licenza** GNU GPL v3 o successiva

RuscaTranslator traduce documenti **Markdown** tra le ventisei lingue ufficiali di RuscaLinux con un modello linguistico che gira **su questo computer**, tramite **ruscallama-engine** (llama.cpp, componente esterno con licenza MIT). Titoli, elenchi, tabelle, codice e link restano intatti.

Il motore Markdown comune include un componente esterno: la regola dell'evidenziato `==testo==`, porting del plugin [markdown-it-mark](https://github.com/markdown-it/markdown-it-mark) (licenza MIT, © Vitaly Puzrin e Alex Kocharin), in `rusca_markdown.py`.

Lingue: inglese, cinese semplificato, cinese tradizionale, spagnolo, hindi, arabo, portoghese brasiliano, portoghese europeo, russo, giapponese, tedesco, francese, italiano, coreano, indonesiano, turco, polacco, olandese, ucraino, ceco, vietnamita, svedese, rumeno, ungherese, greco, finlandese. La lingua di partenza si può rilevare in automatico: dall'alfabeto per cinese, giapponese, coreano, arabo, hindi, greco, russo e ucraino, dalle parole e dalle lettere più frequenti per le altre. Su testi molto brevi o misti il rilevamento può sbagliare, e tra varianti vicine (cinese semplificato e tradizionale, portoghese brasiliano ed europeo) sceglie in base a caratteri e forme tipiche: in quei casi conviene scegliere la lingua a mano.

---

## 1. Requisiti

- RuscaLinux o Debian Stable, GNOME;
- Python ≥ 3.10, GTK ≥ 4.18, libadwaita ≥ 1.7, GtkSourceView 5;
- il pacchetto `ruscallama-engine` e un modello **GGUF** in `~/.local/share/ruscallama/models/` o in `/usr/share/ruscallama/models/`. È consigliato un modello **Gemma 4 MoE**, che RuscaTranslator sceglie da solo se lo trova.

## 2. Tradurre un documento

1. **Apri** il documento (Ctrl+O), oppure trascinalo nel riquadro **Originale**, oppure incolla il testo.
2. Scegli la **lingua di partenza** (o lascia **Rileva la lingua**), la **lingua d'arrivo** e il **tipo di testo**.
3. Premi **Traduci** (Ctrl+Invio). La traduzione compare nel riquadro di destra mentre viene scritta; la barra in basso mostra a che parte del documento si è arrivati, con **Ferma** (Esc).
4. Rileggi e correggi la traduzione direttamente nel riquadro, poi **Salva** (Ctrl+S). Il nome proposto è `documento.<lingua>.md`.

Il motore parte da solo alla prima traduzione e si ferma alla chiusura della finestra. Il documento viene diviso in parti di circa 6000 caratteri, mai dentro un blocco di codice.

## 3. Tipo di testo

| Tipo | Quando usarlo |
|---|---|
| Generale | Testi qualsiasi |
| Saggistica | Saggi, articoli, testi argomentativi: connettivi e tono accademico |
| Letteratura | Narrativa e poesia: immagini, ritmo e registro |
| Dialoghi | Parlato: interiezioni, registro colloquiale |

Il tipo di testo cambia le istruzioni al modello e, tra italiano e inglese, quali correzioni finali si applicano.

## 4. Conoscenza linguistica (italiano ↔ inglese)

Tra italiano e inglese RuscaTranslator aggiunge un **RAG linguistico** (`raglin.py`). Si spegne nelle **Preferenze** (Ctrl+,).

- **Base di conoscenza**: idiomi, falsi amici, pragmatica, terminologia, connettivi, metafore, convenzioni. Per ogni parte del documento, le voci pertinenti vengono passate al modello come suggerimenti.
- **Glossario del documento**: i termini ricorrenti vengono tradotti una volta e tenuti uguali in tutto il documento.
- **Memoria di traduzione**: quando salvi una traduzione rivista, le coppie di paragrafi diventano riferimenti per le traduzioni future (solo se il numero di paragrafi coincide).
- **Spia dei residui**: se in una parte resta testo nella lingua di partenza, quella parte viene ritradotta una volta.
- **Correzioni finali**: poche correzioni dichiarate e di portata generale, per esempio *smart working* → *remote work*. Non toccano mai codice, link e HTML; alcune valgono solo per certi tipi di testo.

Puoi aggiungere voci tue in `~/.config/ruscatranslator/rag/personale.json`. Il formato è descritto in `README-RAG.md`, nella documentazione del pacchetto.

## 5. Preferenze

| Opzione | Effetto |
|---|---|
| Dimensione del testo | Dimensione del testo nei due riquadri; anche con Ctrl++ e Ctrl+−, Ctrl+0 torna a quella di sistema |
| Modello | Scelta tra i GGUF trovati, o un file qualunque |
| Scheda grafica (Vulkan) | Molto più veloce; spenta per impostazione predefinita perché alcuni driver si bloccano |
| Scheda da usare | Automatica, oppure una delle schede del computer. Nei portatili con due schede grafiche scegli quella dedicata (per esempio NVIDIA) |
| Thread della CPU | Consigliati tanti quanti i core fisici |
| Contesto | 8192 basta per le parti da 6000 caratteri |
| Conoscenza linguistica | Il RAG descritto sopra |

Le opzioni del motore valgono al riavvio: un avviso in alto offre **Riavvia il motore**.

## 6. Scorciatoie da tastiera

| Tasti | Azione |
|---|---|
| Ctrl+O | Apri |
| Ctrl+S / Ctrl+Maiusc+S | Salva / Salva come |
| Ctrl+Invio | Traduci |
| Esc | Ferma |
| Ctrl+I | Scambia le lingue |
| Ctrl+, | Preferenze |
| Ctrl++ / Ctrl+− / Ctrl+0 | Testo più grande / più piccolo / dimensione di sistema |
| Ctrl+? | Scorciatoie da tastiera |
| F10 | Menu principale |
| Ctrl+W / Ctrl+Q | Chiudi la finestra / Esci |

## 7. Privacy

- Il motore ascolta solo su **127.0.0.1**, su una porta libera, con una **chiave temporanea** in `$XDG_RUNTIME_DIR/ruscallama/` (permessi 0600).
- Nessun testo viene inviato su internet; il motore non sa scaricare nulla.
- Dove restano i dati: impostazioni e voci personali in `~/.config/ruscatranslator/`; memoria di traduzione e glossari in `~/.local/share/ruscatranslator/`. Si possono cancellare in qualunque momento.

La traduzione è automatica: per testi legali, medici o da pubblicare serve una revisione umana.

## 8. Risoluzione dei problemi

| Problema | Cosa fare |
|---|---|
| «ruscallama-engine non è installato» | `sudo apt install ruscallama-engine` |
| «Nessun modello trovato» | Copia un GGUF in `~/.local/share/ruscallama/models/` o sceglilo nelle Preferenze |
| Il motore si ferma subito | **Registro del motore** dal menu: spesso manca memoria |
| Traduzione lenta | Prova la **Scheda grafica (Vulkan)** |
| Con la scheda grafica il modello non si carica, senza sì | In **Scheda da usare** scegli la scheda dedicata: su un portatile con due schede il motore può usare quella sbagliata |
| Parti rimaste nella lingua originale | Ritraduci, o correggile a mano prima di salvare |

Supporto: info@ruscalinux.org — La nota sull'uso di strumenti di intelligenza artificiale è nella finestra Informazioni e nel file `NOTA-IA.md` del repository.
