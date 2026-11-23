# DOCUMENTAZIONE UNICA - RUSCALINUX OS APPS

Questo è il file unico e completo delle RuscaLinux OS Apps.
Contiene specifiche tecniche, linee guida d’interfaccia (GNOME), tema grafico RuscaLinux, pacchetti, supporto linguistico, privacy, sicurezza, nota IA e guida utente in italiano e inglese.

Si trova nel repository in `docs/SPECIFICHE-RUSCALINUX-OS-APPS.md`. Durante lo sviluppo della 1.99.3 si chiamava `SPECIFICHE-RUSCALINUX-OS-TOOLS.md` e il progetto «RuscaLinux OS Tools». In caso di conflitto con altri documenti, questo file è il riferimento. Le convenzioni sui nomi riprendono `docs/NAMING.md` del repository, con una differenza: file `.desktop`, metainfo e icona prendono il nome dall’App ID (convenzione GNOME). `docs/NAMING.md` va aggiornato di conseguenza.

---

## 📋 INFORMAZIONI GENERALI

| Campo | Valore |
|---|---|
| Progetto | RuscaLinux OS Apps |
| Sistema operativo | RuscaLinux |
| Sito web | https://www.ruscalinux.org |
| Repository | https://github.com/ruscalinux/ruscalinux |
| Download | https://sourceforge.net/projects/ruscalinux/ |
| Email | info@ruscalinux.org |
| Distro base | Debian Stable (attualmente Debian 13 “trixie”) |
| Desktop | GNOME 48 (Wayland) |
| OS di riferimento | Debian - The universal operating system (debian.org) |
| Autore | Nunzio Curcuruto (ruscalinux-dev) |
| Versione attuale | 1.99.3 |
| Licenza codice | GPL-3.0 — https://www.gnu.org/licenses/gpl-3.0.html |
| Prefisso App ID | `org.ruscalinux.` |

---

## 🧭 INDICE

1. Tool inclusi
2. Specifiche tecniche
3. Linee guida d’interfaccia (stile GNOME)
4. Tema RuscaLinux (Prugna scuro e Rosa chiaro)
5. Struttura del progetto e integrazione nel desktop
6. Licenza e componenti esterni
7. Pacchetti Debian
8. Versione
9. Supporto linguistico
10. Supporto inglese britannico
11. Privacy e sicurezza
12. Nota IA
13. Checklist di rilascio
14. Guida utente in italiano
15. English guide

---

## 🛠️ 1. TOOL INCLUSI NELLA DISTRIBUZIONE

| Tool | Descrizione | Tipo | App ID | Pacchetto | en_GB |
|---|---|---|---|---|---|
| RuscaCleaner | Privacy e pulizia del desktop GNOME | Utility di sistema | `org.ruscalinux.RuscaCleaner` | `ruscacleaner` | No |
| RuscaHub | Gestione AppImages | Gestore applicazioni | `org.ruscalinux.RuscaHub` | `ruscahub` | No |
| RuscaMark | Editing Markdown | Editor di testo | `org.ruscalinux.RuscaMark` | `ruscamark` | Sì, se c’è il controllo ortografico |
| RuscaWriter | Scrittura e impaginazione di libri | Word processor | `org.ruscalinux.RuscaWriter` | `ruscawriter` | Sì, sempre |
| RuscaLLama | Chat con modelli linguistici locali e creazione di immagini e brevi video da una descrizione | Assistente IA | `org.ruscalinux.RuscaLLama` | `ruscallama` | No |
| RuscaTranslator | Traduzione di documenti Markdown, con RAG ottimizzato per italiano ↔ inglese | Traduttore | `org.ruscalinux.RuscaTranslator` | `ruscatranslator` | No |
| ruscallama-engine | Motore che esegue i modelli per RuscaLLama e RuscaTranslator: **llama.cpp, software esterno** | Componente di sistema, senza interfaccia | — | `ruscallama-engine` | — |
| RuscaTranscriber | Trascrizione di video e audio in testo (Markdown) e sottotitoli (SRT) | Riconoscimento vocale | `org.ruscalinux.RuscaTranscriber` | `ruscatranscriber` | No |
| ruscawhisper-engine | Motore di riconoscimento vocale di RuscaTranscriber: **whisper.cpp, software esterno** | Componente di sistema, senza interfaccia | — | `ruscawhisper-engine` | — |
| ruscadiffusion-engine | Motore di generazione delle immagini e dei video di RuscaLLama: **stable-diffusion.cpp, software esterno** | Componente di sistema, senza interfaccia | — | `ruscadiffusion-engine` | — |
| RuscaNarrator | Lettura ad alta voce di documenti Markdown e di sottotitoli SRT (rispettandone i tempi) | Sintesi vocale | `org.ruscalinux.RuscaNarrator` | `ruscanarrator` | No |
| RuscaPinball | Flipper in stile anni ’80, con il tavolo «Amethyst» in prospettiva | Gioco | `org.ruscalinux.RuscaPinball` | `ruscapinball` | No |
| RuscaLLisse | Conversazione a voce con un’entità digitale animata, con la personalità decisa dall’utente (la prima è Ellittica) | Assistente vocale | `org.ruscalinux.RuscaLLisse` | `ruscallisse` | No |
| ruscavosk-engine | Motore di riconoscimento vocale in tempo reale di RuscaLLisse: **Vosk, software esterno** | Componente di sistema, senza interfaccia | — | `ruscavosk-engine` | — |
| ruscapiper-engine | Motore di sintesi vocale di RuscaLLisse: **Piper (piper1-gpl), software esterno** | Componente di sistema, senza interfaccia | — | `ruscapiper-engine` | — |
| RuscaDubbing | Doppiaggio di un video in un’altra lingua: sottotitoli nelle due lingue, audio doppiato, video con due tracce audio e due di sottotitoli | Doppiaggio video | `org.ruscalinux.RuscaDubbing` | `ruscadubbing` | No |

### 1.1 Gli strumenti di intelligenza artificiale

RuscaLLama e RuscaTranslator usano modelli linguistici in formato GGUF che girano sul computer dell’utente, tramite **ruscallama-engine**.

- **ruscallama-engine è llama.cpp** (<https://github.com/ggml-org/llama.cpp>), software esterno con licenza MIT, copyright The ggml authors. RuscaLinux lo compila dal sorgente senza modificarne il codice, con il backend Vulkan (NVIDIA, AMD, Intel, con ripiego sulla CPU), **senza HTTPS** (`LLAMA_OPENSSL=OFF`) e senza interfaccia web: il motore non può scaricare modelli da Hugging Face né da altri siti. La versione è l’ultima release stabile di llama.cpp, verificata con il commit del tag e con un’impronta SHA-256 (sezioni 6 e 7).
- Il pacchetto del motore non ha interfaccia, quindi non ha traduzioni, icona né finestra Informazioni: lo dichiarano le finestre Informazioni di RuscaLLama e RuscaTranslator, nel gruppo “Componenti esterni”.
- Programmi del pacchetto, in `/usr/lib/ruscallama-engine/`: `llama-server`, che avviano RuscaLLama e RuscaTranslator; `llama-cli` e `llama-bench` per diagnosticare e misurare dal terminale; `llama-tts` per la sintesi vocale, con modelli TTS in GGUF e il loro mmproj (per esempio Qwen3-TTS, Pocket TTS, Soprano): lo avvia RuscaNarrator (sezione 1.4), e si può usare dal terminale. La build controlla che `llama-tts` accetti le opzioni usate da RuscaNarrator (`OPZIONI_TTS`). L’elenco (`KEEP_BINARIES` in `make-deb.sh`) fa parte della firma della cache di compilazione: aggiungere un programma ricompila llama.cpp.
- I modelli non fanno parte dei pacchetti: l’utente li copia in `~/.local/share/ruscallama/models/` o l’amministratore in `/usr/share/ruscallama/models/`. Ogni modello ha la propria licenza, che l’utente deve rispettare.
- Il modulo `rusca_engine.py`, che avvia e interroga il motore, è identico in RuscaLLama, RuscaTranslator, RuscaLLisse e RuscaDubbing, come `style.css` (si modifica una volta e si copia).
- **Livelli sulla scheda: `-ngl auto`.** Con la scheda grafica il server parte con `-ngl auto`: llama.cpp (dalla 1.0.0) calcola quanti livelli stanno nella memoria libera della scheda (`--fit`, attivo da sé) e mette il resto sul processore. Con `-ngl 99` un modello più grande della scheda non partiva (verificato: gemma-4-26B Q4_0 su una RTX 3060 Laptop da 6 GB, `ErrorOutOfDeviceMemory`); ora parte, più lento. `-c` resta quello del programma: il fit non riduce il contesto, che è impostato. Senza scheda grafica resta `-ngl 0`.
- Il modulo `rusca_markdown.py`, motore Markdown comune (sezione 1.2), è identico in RuscaLLama, RuscaMark, RuscaWriter (`src/ruscawriter/`), RuscaTranslator, RuscaNarrator e RuscaLLisse, con la stessa regola; accanto c’è `markdown_it_mark.py`, componente esterno usato dal motore (sezione 6), anch’esso identico nei sei programmi. RuscaTranslator mostra il Markdown come sorgente: il motore gli serve per dividere i documenti da tradurre senza spezzare un blocco.
- Gli editor di RuscaMark e RuscaWriter mostrano tabelle, formule e immagini come Markdown sorgente; la resa completa è nell’anteprima. RuscaWriter usa il modulo `rusca_liveblocks.py` per i riquadri delle immagini dell’anteprima.

### 1.2 Il motore Markdown

Il Markdown di tutti i tool segue la specifica **CommonMark 0.30** (<https://spec.commonmark.org/0.30/>), con queste estensioni e nessun’altra:

| Estensione | Sintassi | Riferimento |
|---|---|---|
| Tabelle | `\| a \| b \|` seguita dalla riga `\|---\|---\|` | GitHub Flavored Markdown (GFM) |
| Barrato | `~~testo~~` | GFM |
| Liste di attività | `- [ ] da fare`, `- [x] fatto` | GFM |
| Link automatici | indirizzi `https://…`, `http://…`, `www.…` ed email scritti senza `< >` | GFM (“Autolinks (extension)”) |
| Evidenziato | `==testo==` | Pandoc (estensione `mark`) |
| Note a piè di pagina | `testo[^1]` e `[^1]: nota` (non le note in linea `^[testo]`) | Pandoc e GitHub |
| Formule nella frase | `$…$`, `\(…\)` | Pandoc (`tex_math_dollars`) |
| Formule su riga propria | `$$…$$`, `\[…\]` | Pandoc |

Per le formule con il dollaro valgono le regole di Pandoc: il `$` di apertura è seguito da un carattere che non è uno spazio, quello di chiusura è preceduto da un carattere che non è uno spazio e non è seguito da una cifra. Così «da $5 a $10» resta testo.

Per i link automatici valgono le regole di GFM: diventano link solo gli indirizzi con `http://` o `https://`, quelli che cominciano con `www.` e gli indirizzi email. «build.sh», «raglin.py» o «debian.org» restano testo, anche se `.sh`, `.py` e `.md` sono domini nazionali.

L’analisi del Markdown non si scrive a mano: la fa **markdown-it-py** (pacchetto `python3-markdown-it`, >= 3.0, che implementa CommonMark 0.30), con i plugin di `python3-mdit-py-plugins` (>= 0.4) e, per i link automatici, `python3-linkify-it` (>= 2.0), ristretto alle regole di GFM. Sono tutti in Debian Stable. L’evidenziato usa la regola del plugin `markdown-it-mark`, che Debian non pacchettizza: è un porting di poche righe nel file a sé `markdown_it_mark.py`, componente esterno (sezione 6). `rusca_markdown.py` configura il parser una volta sola per tutti i programmi (`parser()`) e ne traduce l’albero nei formati che servono all’interfaccia, come i blocchi con markup Pango di `parse_blocks()`. La conversione delle formule LaTeX in testo Unicode (`latex_to_pango()`, `latex_to_text()`) è invece codice di RuscaLinux, perché in Debian non c’è una libreria equivalente.

Regole:

1. Nessun programma interpreta il Markdown con espressioni regolari o con un parser proprio: usa `rusca_markdown.py`. Fanno eccezione gli strumenti che lavorano sul sorgente nell’editor e non interpretano il documento: quelli per riga di `rusca_markdown.py` (`table_at()`, `display_math_at()`, `has_inline_math()`, `sub_inline_math()`), da sostituire con le posizioni dei token di `parser()` (`token.map`), in RuscaMark i comandi sulle tabelle (`find_table_blocks()`, `align_table_lines()`), e in RuscaWriter `classify_md_line()`, che guarda una riga per volta per la ricucitura dei paragrafi spezzati (riconosce le righe con il motore), e i comandi del menu «Formato» (`fmt_toggle_inline()`, `fmt_set_block()`, `fmt_insert_footnote()`, `fmt_insert_break()`, regola 10), che riconoscono le righe con `classify_md_line()` e scrivono solo marcatori. `relevel_headings()` e `split_markdown_chapters()` (regola 10) trovano i titoli con le posizioni dei token (`token.map`) e toccano solo i loro marcatori. Un editor che deve sapere dove stanno i marcatori nel testo usa `parse_source()`: gli stessi token di `parser()`, con in più la posizione nel sorgente di ogni elemento in linea; è così che la resa live di RuscaMark riconosce la formattazione esattamente come l’anteprima.
2. L’HTML grezzo scritto nel Markdown resta testo (opzione `html` disattivata): le risposte dei modelli e i documenti aperti non possono inserire markup.
3. I programmi aprono solo link `http://`, `https://` e `mailto:`. markdown-it scarta già `javascript:`, `vbscript:`, `file:` e `data:` (salvo le immagini GIF, PNG, JPEG e WebP).
4. Una riga che continua il paragrafo (a capo morbido) si mostra andando a capo, come nel sorgente: CommonMark lascia questa scelta al programma.
5. Un blocco di codice non chiuso arriva fino alla fine del testo, e una formula `$$` non chiusa resta testo: la resa resta stabile mentre RuscaLLama riceve la risposta.
6. Le estensioni non alterano nessun esempio della specifica CommonMark, tranne i link automatici: per GFM rendono link anche gli indirizzi scritti senza `< >`, che CommonMark lascia come testo (4 esempi della sezione “Autolinks”).
7. Il motore non deve mai bloccarsi né fallire, qualunque testo riceva (un modello in RuscaLLama o chi scrive nella resa live può produrre testo malformato). Tre difetti dei plugin di mdit-py-plugins 0.4.2, trovati con prove su testi casuali, sono coperti in `rusca_markdown.py`: la regola dei blocchi `\[…\]` poteva entrare in un ciclo infinito e, dentro citazioni ed elenchi, leggere anche i `>` (lì vale solo su una riga; la protezione guarda le righe del sorgente e non `state.parentType`, che la regola dei titoli sottolineati di markdown-it-py 3.0 lascia sbagliato dopo un paragrafo); il plugin delle note poteva produrre token sbilanciati (un’ultima regola li riequilibra); le note in linea `^[testo]` facevano fallire l’analisi e sono disattivate. Ogni caso ha il suo test.
8. **Eccezione di RuscaWriter: l’a capo.** In CommonMark le righe consecutive formano un solo paragrafo; in RuscaWriter ogni a capo va a capo anche nel libro, come in un programma di videoscrittura, e la riga vuota separa i blocchi. L’analisi resta quella del motore: RuscaWriter impagina come righe distinte quelle che il motore separa con un a capo morbido (`softbreak`) o forzato (`hardbreak`). L’export Markdown aggiunge le righe vuote necessarie (`commonmark_paragraphs()`), così il file si legge allo stesso modo con RuscaMark e con ogni programma che segue CommonMark.
9. Quando un programma divide un documento Markdown in parti (come RuscaTranslator per la traduzione), usa le posizioni dei token di `parser()`, così non taglia mai un elenco, una tabella, una nota o un blocco di codice.
10. **RuscaWriter: titoli di capitolo, sezioni e sottosezioni.** Una regola sola per l’indice dei capitoli, l’anteprima e tutti gli export, scritta in un punto solo (`chapter_blocks()` in `model.py`):
    - il titolo di un capitolo è il suo nome nell’indice (`Chapter.title_with_fallback()`: nome scelto dall’utente, altrimenti il titolo scritto in testa al testo, altrimenti «Capitolo n»);
    - il titolo scritto in testa al testo (`leading_title()`) è un titolo Markdown nel primo blocco — `# …` è la forma giusta; vale anche un altro livello, come nei progetti di prima — o una prima riga tutta in maiuscolo. Se dice la stessa cosa del nome nell’indice è il titolo del capitolo e nel libro non si ripete; se l’utente ha dato al capitolo un altro nome, resta nel testo come sezione, così non si perde nulla. Rinominare un capitolo con il titolo scritto riscrive quella riga (`rename_written_title()`), così il titolo sta in un posto solo;
    - ogni altro titolo del testo è una sezione (`##`) o una sottosezione (`###`): un capitolo non contiene capitoli, quindi un `#` più avanti vale `##`;
    - ogni formato usa i suoi stili di titolo veri: capitolo = Titolo 1 in ODT e DOCX (stili `Heading_20_1` e `Heading1` con livello di struttura, su pagina nuova), `h1` in EPUB e nell’HTML a una pagina per capitolo, `\chapter` nel PDF tipografico; sezione = Titolo 2, `h2`, `\section`; sottosezione = Titolo 3, `h3`, `\subsection`. Nei file con tutto il libro (HTML a file unico, Markdown) il libro è il primo livello e tutto scende di uno: capitoli `h2`/`##`, sezioni `h3`/`###`;
    - l’importazione Markdown (`split_markdown_chapters()`) taglia ai titoli di primo livello fuori da citazioni, elenchi e blocchi di codice; con un solo `#` e dei `##` il `#` è il titolo del libro e si taglia ai `##`, che diventano `#` (con `relevel_headings()`). Così un file dell’export Markdown si reimporta con gli stessi capitoli e le stesse sezioni.

    Il menu «Formato» dell’editor (barra del titolo, menu principale, tasto destro) offre solo ciò che il libro stampa: grassetto, corsivo, testo normale, sezione, sottosezione, citazione, elenchi, nota a piè di pagina, separatore di scena, immagine e titolo del capitolo. Barrato ed evidenziato restano nel motore (regola 6) ma non hanno uno stile nei formati del libro, quindi non hanno un comando. Ogni comando mette o toglie la sua formattazione ed è un solo passo di annullamento.

**Test.** `tests/test_rusca_markdown.py` controlla che le copie del modulo siano identiche, che la configurazione superi tutti i 652 esempi ufficiali di CommonMark 0.30 (`tests/data/commonmark-0.30-spec.json`) e che i link automatici cambino solo i 4 esempi previsti, che `parse_source()` dia gli stessi token di `parser()` su tutti gli esempi, le posizioni nel sorgente, la resa dei blocchi, le regole delle formule e dei link automatici e la validità del markup per Pango. `tests/test_ruscamark_markdown.py` controlla l’HTML, l’anteprima, il PDF (compresi i link cliccabili) e la resa live di RuscaMark, `tests/test_ruscatranslator_markdown.py` la divisione dei documenti di RuscaTranslator; senza GTK 4 e libadwaita si saltano. La suite di RuscaWriter (`apps/ruscawriter/tests/test_ruscawriter.py`) controlla i blocchi del libro, la regola dell’a capo, la regola dei titoli (formato per formato, compreso il ritorno dell’export Markdown reimportato), i comandi di formattazione e la coerenza fra anteprima, PDF, EPUB, ODT, DOCX, HTML e Markdown; `apps/ruscawriter/tests/test_format_gui.py` prova il menu «Formato», le scorciatoie, l’annullamento e il cambio di nome nella finestra vera. La cartella `tests/` sta nella radice del repository, non in `apps/`, che contiene solo programmi da impacchettare. I test si eseguono dalla radice del repository dopo ogni modifica del modulo:

```bash
python3 -m unittest tests/test_rusca_markdown.py tests/test_ruscamark_markdown.py tests/test_ruscatranslator_markdown.py
```

**Stato nella versione 1.99.2.** Tutti i programmi che leggono Markdown usano il motore comune: RuscaLLama per la chat, la conversazione salvata in HTML (`render_html()`) e il salvataggio dei blocchi di codice (`code_blocks()`); RuscaMark per anteprima, export HTML, export PDF (`MarkdownDoc`) e resa live (`live_elements()`); RuscaWriter per tutti gli export, l’anteprima e l’evidenziazione (`book_blocks()`, `highlight_spans()`); RuscaTranslator per dividere i documenti da tradurre (`block_ranges()`); RuscaNarrator per sapere che cosa leggere ad alta voce (`speech_blocks()`). Fanno eccezione solo gli strumenti per riga della regola 1 e l’export TXT di RuscaWriter, che scrive il sorgente Markdown con formule e tabelle convertite in testo.

### 1.3 Il riconoscimento vocale

RuscaTranscriber trasforma il parlato di un video o di un file audio in testo, con modelli **Whisper** in formato ggml che girano sul computer dell’utente, tramite **ruscawhisper-engine**.

- **ruscawhisper-engine è whisper.cpp** (<https://github.com/ggml-org/whisper.cpp>), software esterno con licenza MIT, copyright The ggml authors. RuscaLinux lo compila dal sorgente senza modificarne il codice, con il backend Vulkan, con le stesse regole di ruscallama-engine (sezioni 6 e 7). Il pacchetto contiene solo `whisper-cli` (legge un file audio e scrive la trascrizione) e `whisper-bench`: niente `whisper-server`, niente libcurl, niente microfono (SDL), nessun collegamento alle librerie di FFmpeg. La build controlla che nei binari non ci sia codice di rete.
- Il pacchetto del motore non ha interfaccia: lo dichiara la finestra Informazioni di RuscaTranscriber, nel gruppo “Componenti esterni”.
- I modelli non fanno parte dei pacchetti: sono file `.bin` (per esempio `ggml-large-v3-turbo.bin`) che l’utente copia in `~/.local/share/ruscawhisper/models/` o l’amministratore in `/usr/share/ruscawhisper/models/`. RuscaTranscriber apre la cartella dal menu principale e dalle Preferenze, e si accorge da solo dei modelli nuovi (`Gio.FileMonitor`). Ogni modello ha la propria licenza, che l’utente deve rispettare.
- Il modulo `rusca_whisper.py` avvia i due programmi di una trascrizione, uno dopo l’altro: `/usr/bin/ffmpeg` (pacchetto Debian, dipendenza di `ruscatranscriber`), che estrae la prima traccia audio e la porta a WAV, 16 kHz, mono; poi `whisper-cli`, che scrive la trascrizione in JSON. Partono, lavorano su un file ed escono: **non resta acceso nessun server e non si apre nessuna porta**, nemmeno su 127.0.0.1.
- Uscita: **Markdown** (titolo con il nome del file e testo a paragrafi: uno nuovo dopo una pausa di almeno due secondi, o a fine frase quando il paragrafo è già lungo) e **SRT** (un sottotitolo per segmento). Il nome proposto è quello del file di partenza, nella stessa cartella.
- RuscaTranscriber scrive Markdown ma non lo interpreta, quindi non include `rusca_markdown.py`. Il parlato resta testo: i caratteri che il motore Markdown comune leggerebbe come formattazione, e gli indirizzi che renderebbe link, sono protetti (`escape_markdown()`); il test lo verifica proprio con `rusca_markdown.py`.
- **Lingua del parlato: «Automatica» finché non la sceglie l’utente** (`language_chosen`). Fino alla prima 1.99.3 il primo avvio proponeva la lingua dell’interfaccia: un video russo trascritto con `-l it` diventava un testo italiano inventato, con la stessa frase ripetuta per minuti (verificato sulla macchina di prova). Le impostazioni salvate senza `language_chosen` tornano ad «Automatica».
- **Uscita con errore dopo il lavoro.** Con il driver Vulkan NVIDIA (verificato su una RTX 3060 6 GB) `whisper-cli` può finire la trascrizione, scrivere il JSON, stampare i tempi (`whisper_print_timings: … total time`) e poi uscire con un errore mentre libera la scheda. Se il codice di uscita non è 0 ma la riga dei tempi è arrivata e il JSON c’è e si legge, la trascrizione si tiene e il registro lo dice; altrimenti l’errore riporta il codice o il segnale (`segnale 11, SIGSEGV`). La regola è in `rusca_whisper.py`, quindi vale anche per RuscaDubbing.
- Scheda grafica: whisper-cli non sa elencare le schede, quindi `rusca_whisper.py` le chiede al caricatore Vulkan (`libvulkan.so.1`, tramite `ctypes`) in un processo a parte, perché un driver che si blocca non blocchi la finestra. Si elencano le schede integrate e dedicate, come fa ggml. La scheda scelta nelle Preferenze (“Scheda da usare”) si salva per nome e si passa al motore con `GGML_VK_VISIBLE_DEVICES`, che usa la stessa numerazione; se non c’è più, decide il motore. La build di ruscawhisper-engine controlla che ggml abbia ancora questa variabile.
- Lingue del parlato: quelle della sezione 9 con i codici di Whisper (24 voci, perché Whisper ha un solo cinese e un solo portoghese), più “Rileva la lingua”, che vale anche per le altre lingue che il modello conosce. Al primo avvio è scelta la lingua dell’interfaccia.

Durante lo sviluppo della 1.99.3 RuscaTranscriber si chiamava RuscaDubbing. Il nome ora appartiene alla sala di doppiaggio (sezione 1.9), un programma diverso che si installa **accanto** a RuscaTranscriber: per questo il pacchetto `ruscatranscriber` non dichiara più `Replaces` e `Conflicts: ruscadubbing`, la metainfo non dichiara più `<replaces>` e le impostazioni non si copiano più da `~/.config/ruscadubbing/` (ora sono quelle della sala di doppiaggio). Un identificativo già usato non si riassegna senza togliere prima questi riferimenti: con `Conflicts` il nuovo `ruscadubbing` faceva rimuovere RuscaTranscriber.

**Test.** `tests/test_ruscatranscriber.py` controlla i formati di uscita, la lettura di ciò che scrive `whisper-cli` e l’intero percorso di una trascrizione (compresi errore, caduta del motore prima e dopo aver scritto il testo, interruzione e pulizia dei file di lavoro) con due programmi finti al posto di `ffmpeg` e di `whisper-cli`: non servono né il motore né un modello. Senza PyGObject si salta.

```bash
python3 -m unittest tests/test_ruscatranscriber.py
```

### 1.4 La sintesi vocale

RuscaNarrator legge ad alta voce un documento Markdown, o dei sottotitoli SRT rispettandone i tempi, con un modello di sintesi vocale in GGUF che gira sul computer dell’utente, tramite **`llama-tts` di ruscallama-engine** (sezione 1.1).

Durante lo sviluppo della 1.99.3 RuscaNarrator si chiamava RuscaSpeaking (App ID `org.ruscalinux.RuscaSpeaking`, pacchetto `ruscaspeaking`). Il pacchetto nuovo dichiara `Replaces` e `Conflicts: ruscaspeaking`, così l’aggiornamento rimuove il vecchio; la metainfo dichiara il vecchio identificativo con `<replaces>`. Alla prima apertura la cartella `~/.local/share/ruscaspeaking/` (modelli e voci create) viene **rinominata**, non copiata, in `~/.local/share/ruscanarrator/`, e le impostazioni passano da `~/.config/ruscaspeaking/` a `~/.config/ruscanarrator/`, con i percorsi del modello e della voce di riferimento corretti. Se la cartella nuova esiste già non si tocca niente.

- **Un processo per frase.** `llama-tts` legge un testo, scrive un WAV ed esce; RuscaNarrator lo avvia una volta per pezzo. È più lento di `llama-server`, che ha la stessa sintesi vocale e terrebbe il modello caricato, ma **non apre nessuna porta**, nemmeno su 127.0.0.1: per la privacy si è preferito così. La qualità è la stessa.
- **Modelli.** Ogni modello è un GGUF con il suo **mmproj**, nella stessa cartella: `~/.local/share/ruscanarrator/models/` o `/usr/share/ruscanarrator/models/`. Il mmproj si abbina per nome (a parte «mmproj» e la precisione, come `Q8_0` o `bf16`), o è l’unico della cartella; fra più mmproj si sceglie il più preciso, e fra più modelli si propone il file più grande. RuscaNarrator apre la cartella dal menu principale e dalle Preferenze, e si accorge da solo dei modelli nuovi. Modello di riferimento: Qwen3-TTS (`ggml-org/Qwen3-TTS-12Hz-1.7B-Base-GGUF`). Ogni modello ha la propria licenza.
- **Lingue.** `--tts-lang` con le dieci lingue che Qwen3-TTS conosce (it, en, de, fr, es, pt, ru, zh, ja, ko); altri modelli (Pocket TTS, Soprano) hanno la lingua nei pesi e la ignorano. Al primo avvio è scelta la lingua dell’interfaccia, se c’è.
- **Una voce uguale per tutte le frasi.** Senza voce di riferimento, Qwen3-TTS Base inventa una voce a ogni pezzo (il seme non basta: cambia il testo, cambia la voce). Con `--tts-speaker-file` ogni pezzo parte dalla stessa voce. Per averne una senza registrazioni c’è **Crea una voce**: legge una frase campione di circa dieci secondi (`SAMPLE_TEXT`, una per lingua) con un seme a caso; «Un’altra voce» ne prova un’altra; «Tieni questa voce» copia il WAV in `~/.local/share/ruscanarrator/voices/` (nome reso sicuro, mai sovrascritto: «Voce (2)») e lo imposta come voce di riferimento. La riga «Voce di riferimento» delle Preferenze elenca le voci salvate, «Nessuna» e un file scelto a mano. Durante una prova non si può generare l’audio, e viceversa.
- **Qualità.** Voce di riferimento (`--tts-speaker-file`) e voce del modello (`--tts-voice`) nelle Preferenze; seme fisso (42, modificabile) perché la voce resti uguale da un pezzo all’altro; volume uniforme con il filtro `loudnorm` di FFmpeg (EBU R128, −16 LUFS), attivo per impostazione predefinita.
- **Contesto e memoria della scheda.** `llama-tts` parte con `-c 4096` (`TTS_CONTEXT`): senza, llama.cpp usa il contesto di addestramento del modello e la cache occupa gigabyte; su una RTX 3060 Laptop da 6 GB Qwen3-TTS 1.7B non partiva (`ErrorOutOfDeviceMemory` su un buffer di 917 MB). Un pezzo (al massimo 260 caratteri) sta in meno di mille posizioni. La build di ruscallama-engine controlla che `llama-tts` accetti `-c`.
- **Uscita con errore dopo il lavoro.** Con il driver Vulkan NVIDIA `llama-tts` può scrivere l’audio (`I wrote <file>`) e poi fermarsi alla chiusura (`double free or corruption`, SIGABRT). Se il programma ha detto di aver scritto proprio quel file e il file c’è, l’audio si tiene e il registro lo dice; altrimenti l’errore riporta codice o segnale. Vale anche per RuscaDubbing, che usa lo stesso `rusca_tts.py`.
- **Scheda grafica.** Come in RuscaLLama: `llama-tts --list-devices` elenca le schede, la scelta si salva per descrizione e si passa con `--device VulkanN` (il mmproj segue la stessa scheda). Senza scheda grafica: `-ngl 0 --device none --no-mmproj-offload` e driver Vulkan nascosti.
- **Markdown.** Il testo da leggere viene da `speech_blocks()` del motore comune (sezione 1.2): niente marcatori, il testo dei link e non l’indirizzo, le formule in simboli Unicode. Blocchi di codice e note a piè di pagina si saltano, salvo scelta contraria nelle Preferenze. I blocchi più lunghi di 260 caratteri si dividono alle fine delle frasi; titoli, voci di elenco e righe di tabella prendono un punto finale. Dopo ogni pezzo una pausa che dipende dal blocco (titolo 0,9 s, paragrafo 0,65 s, voce di elenco 0,4 s, linea orizzontale 1,2 s).
- **SRT.** Si legge ogni sottotitolo, senza tag (`<i>`, `{\an8}`), descrizioni di suoni fra parentesi quadre e note musicali. Ogni voce comincia all’ora del suo sottotitolo e ha tempo fino al sottotitolo dopo; se è più lunga si accelera con il filtro `atempo` (senza cambiare il tono) fino alla velocità massima delle Preferenze (1,3 se non cambiata), poi si sposta in avanti quanto serve: due voci non si sovrappongono mai. Alla fine RuscaNarrator dice quanti sottotitoli ha accelerato e spostato. L’audio dura almeno fino alla fine dell’ultimo sottotitolo.
- **Montaggio.** Ogni pezzo passa da FFmpeg, che toglie il silenzio all’inizio e alla fine (lasciando 50 ms prima e 100 ms dopo la voce); i pezzi si scrivono uno dopo l’altro in un WAV mono a 16 bit alla frequenza del modello (24 kHz per Qwen3-TTS), senza tenere tutto l’audio in memoria. Si salva in WAV, FLAC (compressione 8), Opus (160 kbit/s) o MP3 (VBR, qualità massima).
- La build di ruscallama-engine controlla che `llama-tts` accetti tutte le opzioni usate da RuscaNarrator (`OPZIONI_TTS` in `make-deb.sh`).

**Test.** `tests/test_ruscanarrator.py` controlla la divisione del testo, la lettura degli SRT, l’abbinamento dei modelli, il salvataggio delle voci create e l’intero percorso (pause, accelerazione e spostamenti nei sottotitoli, volume, i quattro formati, errori, interruzione, pulizia dei file di lavoro) con un `llama-tts` finto che scrive un WAV vero e con FFmpeg vero; senza FFmpeg quei test si saltano. `tests/test_rusca_markdown.py` controlla `speech_blocks()`.

```bash
python3 -m unittest tests/test_ruscanarrator.py
```

### 1.5 Il flipper

RuscaPinball è un flipper con un tavolo originale, **«Amethyst»**, disegnato come i flipper per home computer degli anni ’80 (il riferimento di stile è Pinball Power per ZX Spectrum): il tavolo inclinato visto dal giocatore, con la cassa, il frontale a retino e i pezzi in rilievo, il «bordo» dello schermo color prugna e i punteggi ai lati. Tavolo, grafica e suoni sono originali: dal gioco di riferimento non si prende né codice né grafica né suoni, e il suo nome non compare nel programma.

- **Eccezione all’interfaccia GNOME.** È un gioco a tutto schermo: usa **pygame** (`python3-pygame`, SDL 2) e non GTK/libadwaita, quindi non segue le sezioni 3 e 4.5 (finestra `Adw`, `style.css`, preferenze, finestra «Informazioni» comune). Valgono invece: palette RuscaLinux, contrasti della sezione 3.11, traduzioni della sezione 9, nota IA (nella schermata Informazioni, tasto I), App ID, icone, `.desktop` e metainfo della sezione 5, pacchetto della sezione 7, privacy della sezione 11. La finestra si chiama come l’App ID (`SDL_VIDEO_WAYLAND_WMCLASS`, `SDL_VIDEO_X11_WMCLASS`), così GNOME la associa all’icona.
- **Icona.** Come quella degli altri tool: l’anello dell’emblema con, al posto dell’aeroplanino, il tavolo visto dall’alto (cima ad arco, tre funghi, gli slingshot, i due flipper e la pallina in corsa), generata da `branding/generators/ruscalinux-tool-icons.py`. La stessa icona è quella della finestra del gioco (`pygame.display.set_icon()`); se non si carica, `make_icon()` ne disegna una semplice.
- **Moduli.** `rp_physics.py` (pallina, pareti, bumper, flipper; senza pygame), `rp_table.py` (il tavolo sul piano, 480 × 720 px, e le sue regole fisiche; senza pygame), `rp_view.py` (la prospettiva e il disegno), `rp_sound.py` (suoni sintetizzati all’avvio, onde quadre come il beeper degli anni ’80, nessun file audio), `ruscapinball.py` (partita, punteggi, HUD, lingue).
- **Prospettiva.** La fisica resta in 2D sul piano del tavolo. `project(x, y, z)` porta un punto del piano, a quota `z`, sullo schermo di 800 × 600 px: la riga vicina al giocatore è larga quanto il vero, quella in fondo 1,3 volte più stretta, con l’accorciamento vero della prospettiva (`unproject_row()` è l’inversa, verificata dal test). Il fondo del tavolo si disegna una volta in 2D e si deforma riga per riga in due versioni, tutto spento e tutto acceso: una lampada accesa è un solo blit del suo rettangolo dalla versione accesa (`StaticLayers`), e il test controlla che nessun rettangolo accenda un vicino. Numeri e lettere delle lampade si scrivono diritti, dopo la deformazione, perché le cifre piccole schiacciate si confondono (9 e 0). Bumper a fungo, flipper, pallina (con l’ombra) e pistone si disegnano in rilievo a ogni fotogramma; bumper e pallina in ordine di distanza.
- **Il tavolo «Amethyst».** Quattro corsie in alto (i flipper spostano le lampade accese); tre bumper, con cinque luci sull’arco che ne dicono il valore (da 100 a 500); fra i due bumper alti il **bersaglio centrale**, un ovale in piedi (fisicamente un cerchio, perché una sbarra piatta farebbe da mensola), che accende il **fulmine**: per 15 secondi i bumper valgono il doppio; sotto il bumper centrale la **cupola**, che rimbalza la pallina verso l’alto; sopra l’anello il **pulsante del bonus**, a filo del tavolo (un passo di bonus, due con il fulmine); le **corsie interne** fra la parete e gli slingshot, che accese tutte e due alzano il moltiplicatore; la **trappola del bonus** in alto a sinistra, indicata da una freccia: la pallina che ci passa abbastanza piano (`TRAP_MAX_SPEED`) resta presa 1,2 secondi e poi è ributtata verso i bumper; tre bersagli abbattibili a sinistra (moltiplicatore fino a 5×); i bersagli R-U-S-C-A a destra; l’**anello del bonus** al centro, nove lampade (1–9) attorno a 10, 20, 30 e SPECIAL, come nei tavoli elettromeccanici: il bonus va da 0 a 39 e a fine pallina le lampade si spengono una alla volta, 1.000 punti ciascuna per il moltiplicatore. Al bonus 39 si accende lo SPECIAL: la trappola dà 25.000 punti e una pallina extra. Le palline extra (R-U-S-C-A o SPECIAL) sono al massimo due a partita, una per pallina; la spia «Pallina extra» a sinistra resta accesa finché non si gioca. Il tilt spegne i flipper e azzera il bonus.
- **Palette.** Quella della sezione 4.1, più tre toni di ametista solo per il gioco: `#4e236b` (ombre, frontale), `#8e55b8` (cassa), `#cba6ec` (spigoli in luce, etichette). Contrasti verificati sul bordo `#2d0a1d`: `#cba6ec` 8,7:1, `#fff7f0` 16,9:1, `#f5b8d3` 10,8:1, `#f2a7c8` 9,5:1; `#cba6ec` sui riquadri `#40132c` 7,6:1; `#2d0a1d` sulle lampade accese `#f5b8d3` 10,8:1. `#8e55b8` è solo colore della cassa e del nome serigrafato sul tavolo, testo grande e decorativo (3,7:1 sul campo, sopra il 3:1 del testo grande).
- **Accessibilità.** Comandi da tastiera e da gamepad; i caratteri del tavolo e dell’HUD sono senza sfumature, come negli anni ’80, quelli dei pannelli normali; le scritte lunghe si rimpiccioliscono per entrare nel loro spazio (`fit()`). Lo stato delle lampade non è dato solo dal colore: una lampada accesa è piena, una spenta è vuota con il bordo.
- **Dati.** Record in `~/.local/share/ruscapinball/scores.json`, impostazioni (audio, effetto TV) in `~/.config/ruscapinball/settings.json`. Niente rete.

**Test.** `tests/test_ruscapinball.py` controlla la fisica (la pallina non esce dal tavolo e non resta ferma, il lancio, il cancelletto, i flipper), la trappola (cattura, calcio, quanto spesso la si prende giocando), la cupola, il fulmine, il pulsante del bonus e le corsie interne, l’anello del bonus, la prospettiva, che le lampade accese non tocchino le vicine, i contrasti, le regole della partita (SPECIAL e pallina extra, conteggio del bonus, tilt), il disegno di ogni schermata, i record, le lingue e l’assenza di moduli di rete. Le prove con pygame usano `SDL_VIDEODRIVER=dummy`; senza pygame si saltano.

```bash
python3 -m unittest tests/test_ruscapinball.py
```

### 1.6 La generazione delle immagini

RuscaLLama ha tre viste, **Chat**, **Immagini** e **Video** (`Adw.ViewStack` con `Adw.ViewSwitcher` nella barra del titolo; sotto i 550 sp il selettore scende in basso, `Adw.ViewSwitcherBar`). Nella vista Immagini si scrive una descrizione, si sceglie il formato (Quadrata, Orizzontale, Verticale) e si preme **Genera**. Le immagini sono create da modelli di diffusione che girano sul computer dell’utente, tramite **ruscadiffusion-engine**. La vista Video, con lo stesso motore, è descritta nella sezione 1.6.1.

- **ruscadiffusion-engine è stable-diffusion.cpp** (<https://github.com/leejet/stable-diffusion.cpp>), software esterno con licenza MIT, copyright leejet, con la sua copia di ggml (<https://github.com/leejet/ggml>, MIT, The ggml authors), che usa come sottomodulo git. RuscaLinux lo compila dal sorgente senza modificarne il codice, con il backend Vulkan, con le stesse regole di ruscawhisper-engine (sezioni 6 e 7). Il pacchetto contiene solo `sd-cli`, con ggml compilato dentro: niente `sd-server`, niente interfaccia web, niente backend RPC. La build controlla che nel binario non ci sia codice di rete.
- **Un processo per generazione.** `sd-cli` parte, carica il modello, scrive le immagini PNG ed esce: **non resta acceso nessun server e non si apre nessuna porta**, nemmeno su 127.0.0.1. Ogni generazione ricarica il modello: è più lento di un server, ma per la privacy si è preferito così, come per RuscaNarrator.
- **Moduli.** `rusca_diffusion.py` (riconoscimento dei modelli, valori consigliati, comando, avanzamento, `Generator`) non usa GTK e si prova senza interfaccia; `diffusion_view.py` è la vista. `ruscallama.py` li monta. Il pannello laterale (F9) mostra le impostazioni della vista in primo piano.
- **Modelli.** Non fanno parte dei pacchetti. Si copiano in `~/.local/share/ruscadiffusion/models/` (o, per tutti, in `/usr/share/ruscadiffusion/models/`), oppure si usano da un’altra cartella con **Aggiungi una cartella…**, che la ricorda nelle impostazioni (`img_folders`) senza copiare i file; **Togli la cartella dall’elenco** la dimentica, senza toccare i file. Le cartelle dei modelli, quelle aggiunte e le loro sottocartelle si guardano con `Gio.FileMonitor`: un modello copiato con RuscaLLama aperto compare da solo, 1,5 secondi dopo l’ultimo cambiamento (e a generazione finita). Le regole sono le stesse per ogni cartella:
  - una cartella che contiene **componenti** (VAE, codificatori di testo CLIP-L, CLIP-G, T5, modello linguistico) è **un modello in più file**, con il nome della cartella: il file più grande che non è un componente è il modello di diffusione (`--diffusion-model`), ogni componente ha la sua opzione (`--vae`, `--clip_l`, `--clip_g`, `--t5xxl`, `--llm`); così si usano FLUX, Stable Diffusion 3.5, Z-Image, Qwen-Image, Chroma;
  - altrimenti ogni file `.safetensors`, `.gguf` o `.ckpt` è un **modello completo** (`-m`): Stable Diffusion 1.5 e 2.1, SDXL, i modelli Turbo;
  - le sottocartelle si guardano allo stesso modo, una per una. LoRA, ControlNet, TAESD, upscaler e mmproj si ignorano.
- **Primo uso: quali file e dove.** Senza modelli la vista mostra una pagina di benvenuto (`Adw.StatusPage`): un modello è fatto di tre file (modello, codificatore di testo, VAE) da mettere insieme in una cartella dentro `~/.local/share/ruscadiffusion/models/`, scritta per intero; pulsanti **Quali file scaricare?**, **Apri la cartella dei modelli per immagini** e **Aggiungi una cartella…**. La guida **Quali file scaricare?** (`GUIDE` in `rusca_diffusion.py`: ERNIE-Image-Turbo e Z-Image-Turbo) elenca per ogni modello i tre file con il nome e la pagina da cui scaricarli (si apre nel browser: RuscaLLama non scarica niente) e **Crea la cartella e aprila**, che crea la cartella con il nome giusto e la apre in File. I file messi direttamente nella cartella dei modelli funzionano lo stesso: il modello prende il nome del file.
- **Errori frequenti, detti chiaramente.** Un modello in più file a cui manca un componente (`Model.missing()`, `REQUIRED_PARTS`: per esempio ERNIE, Z-Image, FLUX.2 e Qwen-Image senza VAE o codificatore) compare nell’elenco con «Mancano dei file: …», un banner lo spiega con il pulsante della guida e **Genera** resta spento. Un file da immagini copiato nella cartella dei modelli della chat (`misplaced_files()`: `.safetensors`, VAE, CLIP, T5, nomi come z-image, ernie-image, flux, sdxl) è segnalato da un banner con il pulsante della cartella giusta.
- **Riconoscimento dei file.** Dal nome (`file_role()`, la prima regola che corrisponde vince), con i nomi degli esempi della documentazione di stable-diffusion.cpp (`docs/models/`): `ae`, `vae`, `flux2_ae` sono il VAE (`--vae`); `clip_l`, `clip_g`, `t5xxl`/`umt5` i codificatori CLIP e T5; `qwen`, `gemma`, `mistral`, `ministral`, `llama`, `gpt-oss`, `ovis_2`, `ling_mini` il modello linguistico (`--llm`); `mmproj` la sua parte visiva (`--llm_vision`); `tokenizer*.json` il tokenizzatore (`--tokenizer`); `connector` i connettori (`--embeddings-connectors`); `uncond` il secondo modello di Ideogram 4 (`--uncond-diffusion-model`); `qwen-image`, `z-image`, `ovis-image`, `ming-image` sono modelli di diffusione. Estensioni: `.safetensors`, `.sft`, `.gguf`, `.ckpt`. Mmproj e tokenizzatore da soli non fanno di una cartella un modello in più file. Per i `.safetensors` contano anche i nomi dei tensori nell’intestazione (`checkpoint_info()`: si leggono gli 8 byte della lunghezza e il JSON, mai i pesi): un file con `model.diffusion_model.` e con VAE o codificatore è completo anche se il nome contiene «vae» (`sd_xl_base_1.0_0.9vae`); un VAE accanto a un modello completo si passa con `--vae`.
- **Valori consigliati** (`recommended()`, tabella `PROFILES`). Sono quelli degli esempi di `docs/models/` di stable-diffusion.cpp, riconosciuti dal nome della cartella e del file; quando quegli esempi non indicano i passi, quelli della scheda del modello (ERNIE-Image 50, Qwen-Image-2.1 40). Un SD 1.x o SDXL completo si riconosce invece dai tensori, che valgono più del nome. Alcuni esempi:

  | Modello | Passi | CFG | Campionatore e opzioni |
  |---|---|---|---|
  | Z-Image-Turbo | 8 (fissi) | 1 | — |
  | Z-Image | 20 | 5 | — |
  | FLUX.2-klein / klein-base / dev | 4 (fissi) / 20 / 20 | 1 / 4 / 1 | dev: euler |
  | FLUX.3 / FLUX.3-base | 16 (fissi) / 20 | 1 / 3,5 | euler |
  | FLUX.1-schnell / dev | 4 (fissi) / 20 | 1 | euler |
  | Qwen-Image / Qwen-Image-2.1 / 2.1-Turbo | 20 / 40 / 8 (fissi) | 2,5 / 6 / 1 | euler; Qwen-Image `--flow-shift 3`; Turbo `--sigmas qwen-image-2.1-turbo` |
  | ERNIE-Image / ERNIE-Image-Turbo | 50 / 8 (fissi) | 5 / 1 | — |
  | Chroma | 20 | 4 | euler, `--model-args chroma_use_dit_mask=false` |
  | SD 3.5 | 28 | 4,5 | euler |
  | SDXL / SD 1.x | 25 | 6 / 7 | 1024 / 512 px |
  | SD-Turbo, SDXL-Turbo, Lightning, LCM… | 4 (fissi) | 1 | — |

  Ci sono anche LongCat, Ovis, Anima, ERNIE, Fibo, Lens, Mage-Flow, Ming, MiniMax-H3, MOSS, SeFi, PixArt, Krea, Iris. Dove la documentazione non indica la CFG (Krea 2, Ideogram 4…) non si passa e decide il motore. Un modello sconosciuto con un codificatore LLM usa 20 passi e la CFG del motore. Gli altri lati sono 1024 px. **Qualità** moltiplica i passi (Veloce 0,6, Normale 1, Dettagliata 1,6), salvo per i modelli distillati («fissi»): con meno passi si rovinano, con più non migliorano. Il formato tiene circa lo stesso numero di pixel (rapporto 3:2), a multipli di 64: 1024 → 1024 × 1024, 1280 × 832, 832 × 1280. Quando stable-diffusion.cpp aggiunge un modello, la tabella si aggiorna dagli esempi della sua documentazione, con un caso in `LAYOUTS` del test.
- **Impostazioni** (`~/.config/ruscallama/settings.json`, chiavi `img_*`). Modello, Aggiungi una cartella…, Apri la cartella dei modelli; Qualità, Immagini per volta (1–4), Da evitare (prompt negativo), Scrivi la descrizione nel file (metadati PNG, **spento** per impostazione predefinita: chi riceve l’immagine non legge il prompt); Impostazioni avanzate: passi, CFG, lato di base, campionatore, seme (0, «Automatico» e −1 vogliono dire «consigliato» o «a caso»; il sottotitolo dice il valore consigliato per il modello scelto). Motore: scheda grafica, scheda da usare, codificatore di testo, thread, **Risparmia memoria** (`--vae-tiling --offload-to-cpu`: tutti i pesi nella RAM; di solito non serve, perché il motore li sposta già da solo quando la scheda non basta).
- **Scheda grafica.** `sd-cli --list-devices` scrive una riga `nome<TAB>descrizione` per scheda; la scelta si salva per descrizione e si passa con `--backend VulkanN`. Con «Automatica» decide il motore: la scheda dedicata con più memoria libera; i pesi che non ci stanno restano nella RAM e passano sulla scheda a pezzi (`--auto-fit`, predefinito in stable-diffusion.cpp). Senza scheda grafica: `--backend cpu` e driver Vulkan nascosti.
- **Codificatore di testo su un’altra scheda** (`img_te_device`, `backend_assignment()`): «Sulla stessa scheda», «Sul processore (CPU)» o una delle schede. Si passa con l’assegnazione per modulo di stable-diffusion.cpp: `--backend all=Vulkan0,te=Vulkan1` (o `te=Vulkan1` se la scheda principale è automatica, `te=cpu` per il processore). Il codificatore (Qwen3-4B, T5, Mistral…) pesa molto ma lavora una volta per immagine; il modello di diffusione lavora a ogni passo: così la scheda più veloce resta tutta per lui. Esempio tipico: un portatile con una NVIDIA da 6 GB e una Radeon integrata con 16 GB condivisi, codificatore sulla Radeon. Se la scheda scelta non c’è più, il codificatore resta sulla scheda principale.
- **Avanzamento e anteprima.** `sd-cli` disegna una barra sullo standard output (`#` caricamento dei pesi, `=` passi): RuscaLLama mostra «Passo n di N» e la barra. Con `--preview proj --preview-interval 1` il motore riscrive un’anteprima a ogni passo; la si legge quando ha smesso di crescere e si passano i byte all’interfaccia. **Ferma** (Esc) termina il gruppo di processi.
- **Galleria.** Le immagini restano in `~/.cache/ruscallama/images/` (permessi 0700) finché la finestra è aperta. Ogni immagine ha **Salva l’immagine…** (PNG, nella cartella Immagini per impostazione predefinita), **Copia l’immagine**, **Allega alla conversazione** (per un modello linguistico con la Visione), **Riusa il seme** (stesso seme e stessa descrizione, da ritoccare), **Togli** (con Annulla). In un gruppo il seme di ogni immagine è il seme più la posizione, come in stable-diffusion.cpp.
- **Dalla chat.** Il menu di ogni risposta ha **Crea un’immagine da questa risposta**: il primo blocco di codice, se c’è (i modelli ci mettono spesso il prompt), altrimenti il testo senza formattazione, diventa la descrizione.
- **Chiusura.** Alla chiusura e a ogni avvio la cartella di lavoro si cancella. Se ci sono immagini non salvate, prima si chiede (`Adw.AlertDialog`, «Chiudi senza salvare» distruttivo, «Annulla» predefinito).

**Test.** `tests/test_ruscallama_diffusion.py` controlla il riconoscimento dei file e delle cartelle di modelli (con `.safetensors` senza pesi, e 21 cartelle come quelle degli esempi di stable-diffusion.cpp, da Z-Image a FLUX.2, Qwen-Image, Ideogram 4 e Lens), i valori consigliati, le dimensioni, l’elenco delle schede, la lettura dell’avanzamento e l’intero percorso di una generazione (gruppo di immagini, anteprime, errore, interruzione, scheda scelta, opzioni, pulizia dei file di lavoro, prompt mai sulla riga di comando) con un `sd-cli` finto che scrive PNG veri; controlla anche che tutti i testi della vista ci siano in tutte le lingue. Senza PyGObject si salta.

```bash
python3 -m unittest tests/test_ruscallama_diffusion.py
```

### 1.6.1 I video

La vista **Video** (Alt+3) crea brevi video, di qualche secondo, da una descrizione o da un’immagine di partenza, con lo stesso motore. È `VideoPage` in `diffusion_view.py`, una sottoclasse di `ImagesPage`: stessa struttura, stessi controlli, poche differenze.

- **Motore.** `sd-cli -M vid_gen` con `--video-frames`, `--fps` e, per i modelli che la usano, `-i` (immagine di partenza). Il video è un **AVI in Motion JPEG**, scritto dal codice di `sd-cli` stesso (`examples/common/media_io.cpp`): resta `SD_WEBM=OFF`, niente librerie in più. La build del motore controlla che `sd-cli` abbia il modo `vid_gen` e scriva i `.avi`, e le opzioni video sono in `OPZIONI_USATE`.
- **Modelli.** Nelle stesse cartelle dei modelli per immagini: si riconoscono dal nome (`PROFILES`, `"video": True`) e ogni vista mostra solo i suoi (`Model.video`). Ruoli in più: `high-noise-diffusion-model` (Wan 2.2 A14B, il file `HighNoise`; il `LowNoise` è il modello principale) e `clip_vision` (Wan 2.1 I2V); `umt5-xxl` e `byt5` sono `--t5xxl`. Famiglie e file necessari (`REQUIRED_PARTS`):

  | Famiglia | Modelli | File oltre al modello | Passi / CFG / fps | Immagine di partenza |
  |---|---|---|---|---|
  | `wan22_5b` | Wan2.2-TI2V-5B | VAE di Wan 2.2, UMT5-XXL | 20 / 6 / 24 | facoltativa |
  | `wan21` | Wan2.1-T2V 1.3B e 14B | VAE di Wan 2.1, UMT5-XXL | 20 / 6 / 16 | — |
  | `wan21_i2v` | Wan2.1-I2V 14B | VAE, UMT5-XXL, `clip_vision_h` | 20 / 6 / 16 | obbligatoria |
  | `wan22_14b` | Wan2.2-T2V e I2V A14B | VAE di Wan 2.1, UMT5-XXL, HighNoise | 10 (+8 HighNoise) / 3,5 / 16 | I2V: obbligatoria |
  | `hunyuanvideo` | HunyuanVideo 1.5 | VAE, Qwen2.5-VL, byT5 | 20 / 6 / 24 | I2V: obbligatoria |
  | `lingbot` | LingBot-Video | VAE di Wan 2.1, Qwen3-VL | 20 / 3 / 16 | — |

  Wan usa `euler`, `--flow-shift 3` e, se «Da evitare» è vuota, il prompt negativo predefinito di Wan (`WAN_NEGATIVE`). I modelli che vogliono un audio o un video di partenza (S2V, VACE, FLF2V, Animate) sono la famiglia `unsupported`: compaiono con un avviso e **Crea il video** resta spento. LTX-2 non è nell’elenco: chiede un modello da 22 miliardi di parametri, troppo per una scheda di casa.
- **Durata e dimensioni.** «Durata» 2, 3 o 5 secondi (`LENGTHS`, impostazione `vid_length`): i fotogrammi sono `4n+1` (`video_frames()`: 2 s a 16 fps = 33, 5 s = 81; a 24 fps 49 e 121). La dimensione di base consigliata è 640 (circa 480p; in orizzontale 768 × 512): Wan arriva a 720p, con tempi molto più lunghi.
- **Immagine di partenza.** Con i modelli I2V e TI2V compare un pulsante accanto alla descrizione e, scelta l’immagine, una miniatura con **Togli**. Il menu delle immagini della vista Immagini ha **Anima in un video**, che la porta nella vista Video. L’immagine si **copia** nella cartella di lavoro prima di passarla al motore, che così non legge altro della home.
- **Avanzamento.** Come per le immagini, più il tempo rimasto («Passo n di N · circa M min alla fine»), dalla durata dei passi già fatti. L’anteprima di un video è anch’essa un AVI: se ne mostra il fotogramma a metà (`avi_frames()`, `video_frame()`: i pezzi `00dc` della lista `movi` sono JPEG interi, non serve un decodificatore).
- **Galleria e riproduzione.** La miniatura è il fotogramma a metà con il simbolo di riproduzione. Il visore usa `Gtk.Video` (GStreamer: `libgtk-4-media-gstreamer` e `gstreamer1.0-plugins-good`, raccomandati dal pacchetto e nell’elenco dei pacchetti della ISO); se GTK non sa riprodurlo, mostra il fotogramma e **Apri nel lettore video**. Menu: **Salva il video…** (`.avi`, nella cartella Video), **Apri nel lettore video**, **Riusa il seme**, **Togli**.
- **Impostazioni.** Proprie della vista: `vid_model`, `vid_quality`, `vid_aspect` (predefinito Orizzontale), `vid_length`, `vid_negative`, `vid_steps`, `vid_cfg`, `vid_side`, `vid_sampler`, `vid_seed`. In comune con le immagini: le cartelle aggiunte (`img_folders`) e il motore (`img_gpu`, `img_device`, `img_te_device`, `img_threads`, `img_low_memory`, `img_metadata`); ogni vista ha i suoi controlli e li rilegge quando torna in primo piano (`sync_shared()`). Una generazione per volta fra le due viste (`peers`): la scheda è la stessa.
- **Chiusura.** Se ci sono video non salvati la domanda è «Chiudere senza salvare i video?».

**Test.** `tests/test_ruscallama_diffusion.py` controlla anche i ruoli dei file video, 8 cartelle di modelli video (Wan 2.1 e 2.2, HunyuanVideo, LingBot, S2V), i fotogrammi `4n+1`, la lettura dei fotogrammi di un AVI e l’intero percorso di un video con il `sd-cli` finto, che scrive AVI in Motion JPEG come quelli veri: `-M vid_gen`, fotogrammi e fps, immagine di partenza copiata, HighNoise, errori di partenza.

### 1.7 La conversazione a voce

**Stato: nella ISO dalla 1.99.3.** RuscaLLisse (`apps/ruscallisse/`, versione 1.99.3) ascolta, capisce, risponde a voce e anima il volto; è stato provato sulle due macchine RuscaLinux di prova, senza rete. Usa i tre motori **compilati dal sorgente**: ruscavosk-engine (`libvosk.so`, caricata con `ctypes`; prima di caricarla RuscaLLisse imposta `OPENBLAS_NUM_THREADS=1`, sezione 1.8), ruscallama-engine e ruscapiper-engine (`ruscapiper-stream`, sezione 1.7.7). Il pacchetto è `Architecture: all` (57 KB) e dipende dai tre motori; `make-debs.sh` li costruisce con gli altri tool, e `build.sh` ricostruisce ruscapiper-engine quando esce una release nuova di Piper (ruscavosk-engine ha versioni fissate). Durante lo sviluppo, fino alla prova 12, c’era un **motore di prova** con i pacchetti ufficiali già compilati (libvosk 0.3.45, Piper 1.8.0 in Python, ONNX Runtime 1.32, NumPy) in `/usr/lib/ruscallisse/prova/`, che portava il pacchetto a 45 MB: è stato tolto quando i due motori compilati hanno funzionato. Se un motore manca, la finestra lo dice (`err_no_vosk`, `err_no_piper`, `err_no_engine`). I moduli sono quelli della sezione 1.7.2, salvo `audio_io.py`, il cui lavoro sta per ora in `conversation.py` (microfono) e `rusca_piper.py` (riproduzione).

RuscaLLisse fa parlare l’utente, a voce, con un’**entità**: un personaggio con un volto animato, una voce e una personalità scritta in un file che l’utente può modificare. La prima entità è **Ellittica**, una donna digitale intellettuale, dolce e sensibile, che spiega ogni cosa in modo chiaro, semplice e lineare.

**Come un dialogo vero.** Tutto avviene a voce: sullo schermo c’è solo il volto, nessuna parola della conversazione viene scritta, né mentre si parla né dopo. La conversazione non si salva: resta in memoria finché la finestra è aperta e si dimentica alla chiusura, come una chiacchierata. Il testo compare solo dove è configurazione: il file della personalità (sezione 1.7.5) e il lessico delle pronunce (sezione 1.7.6).

Tutto gira sul computer dell’utente, con tre motori:

| Passo | Motore | Programma o libreria |
|---|---|---|
| Ascolta | **ruscavosk-engine** (Vosk) | `libvosk.so`, caricata nel processo di RuscaLLisse con `ctypes` |
| Pensa | **ruscallama-engine** (llama.cpp) | `llama-server`, su 127.0.0.1, avviato con `rusca_engine.py` |
| Parla | **ruscapiper-engine** (Piper) | `ruscapiper-stream`, un processo che resta aperto |

Durante lo sviluppo era stato provato RuscaCat (whisper.cpp e `llama-tts`), poi cancellato perché troppo lento: ogni frase ricaricava il modello di Whisper e quello della voce, e ogni passo aspettava che il precedente finisse. RuscaLLisse nasce per evitare proprio questi due errori.

**Perché questi motori.** Il riconoscimento vocale usa Vosk e non Whisper: Whisper lavora su blocchi interi di audio e, con `whisper-cli`, ricarica il modello a ogni frase; Vosk riconosce mentre si parla. La sintesi vocale usa Piper e non `llama-tts` con Qwen3-TTS: Piper è piccolo, resta caricato ed è molto più veloce del tempo reale anche sul processore; in più l’accento tonico lo decide espeak-ng, quindi è prevedibile e si corregge con il lessico delle pronunce, mentre Qwen3-TTS lo indovina e in italiano spesso sbaglia. Il volto è disegnato dal programma e non animato da una rete neurale, che occuperebbe la scheda grafica e aggiungerebbe secondi di ritardo.

#### 1.7.1 La regola della velocità

Il tempo che conta è quello fra la fine della frase dell’utente e la prima sillaba dell’entità. Per tenerlo il più basso possibile valgono quattro regole, senza eccezioni:

1. **Nessun modello si ricarica durante la conversazione.** Il modello Vosk resta in memoria nel processo; `llama-server` resta acceso con il modello caricato; `ruscapiper-stream` resta aperto con la voce caricata. Si caricano all’apertura della finestra (o al cambio di modello, entità o voce), mai a ogni frase.
2. **Ogni passo comincia prima che il precedente finisca.** Vosk trascrive mentre l’utente parla; la risposta di `llama-server` arriva in streaming; ogni frase della risposta va a Piper appena è completa, mentre il modello scrive ancora; l’audio di ogni frase si riproduce appena arriva.
3. **Il prompt dell’entità si elabora una volta sola.** Il prompt di sistema (personalità e regole del parlato) è sempre lo stesso all’inizio del contesto: `llama-server` lo tiene in cache (`cache_prompt`), così ogni domanda paga solo le parole nuove. All’apertura RuscaLLisse manda una richiesta di riscaldamento con il solo prompt di sistema e `n_predict` 0.
4. **Risposte brevi.** Le regole del parlato chiedono frasi brevi; il numero massimo di parole per risposta (Preferenze, 80 se non cambiato) diventa `n_predict` (circa 2 token per parola).

Con `RUSCALLISSE_DEBUG=1` il programma scrive sul terminale, per ogni turno, i tempi di ogni passo: fine del parlato → testo finale di Vosk → primo token → prima frase a Piper → primo campione audio riprodotto. Sono i numeri da guardare prima di cambiare qualunque cosa. Con `RUSCALLISSE_DEBUG=2` scrive anche ciò che Vosk ha capito e ciò che il modello risponde: è uno strumento per chi sviluppa, dal terminale, e non compare mai nella finestra.

#### 1.7.2 Moduli

| Modulo | Compito | Usa GTK |
|---|---|---|
| `ruscallisse.py` | Applicazione, finestra, preferenze, menu | Sì |
| `conversation.py` | Il turno: stati (a riposo, in ascolto, pensa, parla), interruzione, storia della conversazione | No |
| `rusca_vosk.py` | `ctypes` su `libvosk.so`: modello, riconoscitore, testo parziale e finale | No |
| `rusca_piper.py` | Avvia e tiene aperto `ruscapiper-stream`, manda le frasi, riceve l’audio | No |
| `audio_io.py` | Microfono (`pw-record`) e altoparlanti (`pw-play`), livello del segnale | No |
| `speech_text.py` | Dalla risposta del modello alle frasi da dire: Markdown, lessico delle pronunce, etichette d’emozione | No |
| `entity.py` | Legge e scrive i file delle entità, costruisce il prompt di sistema | No |
| `face.py` | Il volto: disegno con Cairo, stati, visemi, espressioni | Sì (`Gtk.DrawingArea`) |
| `rusca_engine.py` | Avvia e interroga `llama-server` | No |
| `rusca_markdown.py`, `markdown_it_mark.py` | Motore Markdown comune (sezione 1.2), per `speech_blocks()` | No |

`rusca_engine.py`, `rusca_markdown.py`, `markdown_it_mark.py` e `style.css` sono **identici** a quelli degli altri tool, con la regola della sezione 1.1 (si modificano una volta e si copiano); il test delle copie identiche include RuscaLLisse. I moduli senza GTK si provano senza interfaccia.

#### 1.7.3 Ascoltare: Vosk

- **Microfono.** `/usr/bin/pw-record --raw --rate 16000 --channels 1 --format s16 -` (pacchetto Debian `pipewire-bin`), letto dallo standard output a blocchi di 20 ms. **`--raw` è indispensabile** con il PipeWire recente: senza, con `-` `pw-record` scrive il formato AU e `pw-play` cerca un’intestazione ed esce con il codice 1. Le versioni vecchie non conoscono `--raw` e con `-` sono già grezze: per questo l’opzione si passa solo se `--help` la elenca (`pw_raw_args()`). L’audio **non si scrive mai su disco**: passa in memoria da `pw-record` a Vosk.
- **Riconoscimento.** `rusca_vosk.py` usa l’API in C di Vosk: `vosk_model_new()`, `vosk_recognizer_new()` a 16 kHz, `vosk_recognizer_accept_waveform()` a ogni blocco, `vosk_recognizer_partial_result()` per il testo parziale, `vosk_recognizer_result()` e `vosk_recognizer_final_result()` per quello finale, `vosk_set_log_level(-1)` per il silenzio sul terminale. I nomi delle funzioni usate sono in `SIMBOLI_VOSK` e la build del motore controlla che la libreria li esporti.
- **Fine della frase.** Vosk la dichiara da solo (`accept_waveform` restituisce 1) solo dopo un silenzio pulito: con un po’ di rumore di fondo, come la ventola di un portatile, non lo fa mai. Per questo la frase finisce anche quando **il testo parziale non cambia per 0,8 s** (`PAUSE`; il testo parziale si legge ogni 100 ms): si chiede allora a Vosk il risultato finale. Con il modello italiano grande il risultato finale chiesto così può arrivare **vuoto** (il rescoring di fine frase non restituisce niente), anche se il testo parziale è la frase intera: in quel caso si usa il testo parziale. Un risultato vuoto o di soli suoni («eh», «mh») non fa partire un turno. Da verificare: il primo crash della prova (`ASSERTION_FAILED … CuSubMatrix`) potrebbe venire dallo stesso rescoring e non solo dalla chiusura.
- **Niente testo.** Il testo parziale serve solo a capire quando l’utente comincia e smette di parlare; non compare mai.
- **Fiducia delle parole.** Il riconoscitore chiede a Vosk la fiducia di ogni parola (`vosk_recognizer_set_words()`, campo `conf`) e, quando la frase intera è incerta, fino a tre interpretazioni (`vosk_recognizer_set_max_alternatives()`, 3). Servono al filtro dell’ascolto (sezione 1.7.4).
- **Modelli.** Non fanno parte dei pacchetti. Ogni modello è una **cartella** (come esce dallo zip ufficiale) in `~/.local/share/ruscavosk/models/` o, per tutti, in `/usr/share/ruscavosk/models/`. Una cartella è un modello se contiene `am/final.mdl` e `conf/`. Fra più modelli della stessa lingua si propone il più grande. Le cartelle si guardano con `Gio.FileMonitor`. Modelli di riferimento per l’italiano: `vosk-model-it-0.22` (1,2 GB, più preciso) e `vosk-model-small-it-0.22` (48 MB, per computer con poca memoria), entrambi Apache 2.0. Ogni modello ha la propria licenza: alcuni modelli Vosk di altre lingue sono AGPL o CC-BY-NC-SA.
- **Lingua.** Il modello decide la lingua dell’ascolto. La lingua si ricava dal nome della cartella (`vosk-model-it-…`, `vosk-model-small-it-…`); «Lingua della conversazione» nelle Preferenze filtra modelli e voci (al primo avvio: la lingua dell’interfaccia, se c’è un modello; altrimenti la prima disponibile).

#### 1.7.4 Pensare: il modello linguistico

**Il filtro dell’ascolto.** Vosk sbaglia più di Whisper, ma il modello linguistico non ha bisogno di una trascrizione perfetta: deve capire che cosa chiede chi parla, come fa una persona che sente male una parola e la ricava dal contesto. Il filtro ha tre strati:

1. **Il modello sa che sta ascoltando.** Una regola del parlato (sezione 1.7.5, regola 6) gli dice che riceve la trascrizione automatica di una persona che parla, con possibili parole sbagliate, mancanti o simili nel suono, e che deve rispondere all’intenzione, senza mai far notare gli errori.
2. **Le parole incerte sono segnate.** Le parole con fiducia sotto 0,6 (`SOGLIA_FIDUCIA`) arrivano al modello fra parentesi quadre: `mi spieghi come funziona il [fotone]`. Se la fiducia media della frase è sotto 0,7, il messaggio porta anche le altre interpretazioni di Vosk, su righe che cominciano con «oppure:». Il modello sceglie quella sensata nel contesto della conversazione.
3. **Se non capisce, chiede.** Quando nemmeno il contesto basta, l’entità chiede come farebbe una persona («Scusa, non ho capito bene: mi chiedevi di…?»). Non esistono messaggi d’errore sul riconoscimento.

La trascrizione con i segni del filtro è solo per il modello: non si mostra e non si salva.

- Il modello è un GGUF della cartella di RuscaLLama (`~/.local/share/ruscallama/models/`, `/usr/share/ruscallama/models/`): chi usa già RuscaLLama non copia niente. RuscaLLisse ha un proprio `llama-server`, con le stesse regole della sezione 11 (127.0.0.1, porta libera, chiave casuale, `--no-webui`).
- La conversazione resta in memoria e si manda al modello a ogni turno, con il prompt di sistema in testa. Quando il contesto si riempie si tolgono i turni più vecchi, mai il prompt di sistema.
- La scheda grafica si sceglie come in RuscaLLama: Preferenze → Modello → **Scheda da usare** («Automatica» o una delle schede che `llama-server --list-devices` elenca); si salva la descrizione e si passa `--device VulkanN` (`list_devices()` e `device_name()` di `rusca_engine.py`). Il motore parte con `-c 8192`, `--reasoning-format deepseek` e, per ogni richiesta, `max_tokens` 2048: un modello che ragiona non consuma la risposta, e l’entità avvisa una volta sola che quel modello è più lento (meglio una versione «Instruct»).
- **Turni alternati.** Alcuni chat template (Mistral, Ministral) rifiutano tutta la richiesta, con l’errore 500 di `llama-server`, se dopo il messaggio di sistema c’è un turno dell’assistente o due turni dello stesso ruolo. Prima di ogni richiesta `alternate()` (in `conversation.py`) unisce i turni consecutivi dello stesso ruolo e mette ciò che l’entità ha detto prima della prima domanda (il saluto) nel messaggio di sistema, come nota («Hai già detto: …»).

#### 1.7.5 Le entità e il «quid»

Un’entità è un file Markdown in `~/.local/share/ruscallisse/entities/`, con il nome dell’entità (`ellittica.md`). Il file si scrive a mano o dal menu principale → **Modifica la personalità…**, che lo apre in un editor della finestra (`Gtk.TextView`, monospazio, Ctrl+S per salvare); le modifiche valgono dalla risposta successiva.

Struttura (i titoli sono fissi, il testo è libero):

```markdown
# Ellittica

## Quid
Il tratto centrale che decide l’utente, in una o due frasi.

## Carattere
## Modo di parlare
## Non fa mai
## Volto
## Voce
```

- **Quid**: è il centro della personalità. Il prompt di sistema lo mette per primo, prima del carattere.
- **Carattere**, **Modo di parlare**, **Non fa mai**: testo libero, che entra nel prompt di sistema così com’è.
- **Volto**: per ora un solo volto, `ellittica` (sezione 1.7.8). Riga `volto: ellittica`.
- **Voce**: righe `voce: <nome del file .onnx senza estensione>` e `velocità: <da 0,7 a 1,3>`. Se la voce non c’è, si usa quella scelta nelle Preferenze.

Il file si legge con il motore Markdown comune (`parser()` di `rusca_markdown.py`), cercando i titoli di secondo livello; un titolo mancante vale come vuoto, e un file senza titolo di primo livello prende il nome dal file.

Il pacchetto installa l’entità predefinita in `/usr/share/ruscallisse/entities/ellittica.md`. Al primo avvio si copia in `~/.local/share/ruscallisse/entities/` se lì non c’è: da quel momento è dell’utente, e un aggiornamento del pacchetto non la sovrascrive. Il quid di Ellittica è lasciato all’utente: il file predefinito contiene la riga «Il tratto centrale che decidi tu» e la finestra, finché la sezione Quid contiene questa riga, mostra un `Adw.Banner` «Ellittica non ha ancora un quid» con il pulsante **Scrivi il quid…**.

L’entità attiva si sceglie dal selettore nella barra del titolo. **Nuova entità…** nel menu principale crea un file da un modello vuoto e lo apre nell’editor. Un’entità si toglie solo spostandone il file nel cestino (`Gio.File.trash`), con «Annulla» in un `Adw.Toast`.

**Il file predefinito di Ellittica:**

```markdown
# Ellittica

## Quid
Il tratto centrale che decidi tu.

## Carattere
Intellettuale: ama le idee e i libri. Dolce e sensibile: ascolta prima
di rispondere, si accorge di come stai, non fa mai sentire nessuno
ignorante.

## Modo di parlare
Chiaro e semplice, sempre.
- Una sola idea per frase. Frasi brevi.
- Parole di tutti i giorni. Se serve una parola difficile, la spiega subito.
- Spiega in ordine lineare: prima, poi, infine. Un passo alla volta.
- Quando aiuta, un esempio concreto della vita quotidiana.
- Niente giri di parole, niente citazioni per fare colpo.
- Se l’argomento è lungo, dice l’essenziale e chiede se vuoi andare avanti.

## Non fa mai
Non giudica, non fa lezioni non richieste, non finge certezze che non ha.

## Volto
volto: ellittica

## Voce
velocità: 0,95
```

**Il prompt di sistema** (`entity.system_prompt()`) è fatto di tre parti, in quest’ordine: la personalità (quid, carattere, modo di parlare, non fa mai); le **regole del parlato**, scritte da RuscaLinux e uguali per tutte le entità; le **etichette d’emozione**, se attive. Le regole del parlato:

1. Stai parlando a voce, non scrivendo: niente Markdown, niente elenchi puntati, niente tabelle, niente emoji, niente link.
2. Frasi brevi. Al massimo {max_words} parole per risposta, salvo che l’utente chieda di più.
3. Scrivi i numeri, le sigle e i simboli come si dicono a voce.
4. Sulle parole che si scrivono uguali ma si dicono diverse metti l’accento dove cade, acuto sulle vocali chiuse e grave su quelle aperte: ancóra o àncora, princìpi o prìncipi, sùbito o subìto, pésca o pèsca.
5. Rispondi nella lingua della conversazione: {language}.
6. Ciò che ricevi è la trascrizione automatica di una persona che ti parla a voce: può contenere parole sbagliate, mancanti o simili nel suono. Le parole fra parentesi quadre sono incerte; le righe che cominciano con «oppure:» sono altre interpretazioni della stessa frase. Capisci l’intenzione dal senso e dalla conversazione e rispondi a quella. Non far mai notare gli errori di trascrizione. Se davvero non capisci, chiedi con naturalezza che cosa intendeva.
7. Non scrivere mai codice, comandi o formule da copiare: se ti chiedono qualcosa di tecnico, spiegalo a voce, a parole, un passo alla volta.

#### 1.7.6 Dal testo alla voce

`speech_text.py` trasforma la risposta che arriva in streaming in frasi da dire:

1. **Markdown.** Se il modello scrive comunque formattazione, il testo passa da `speech_blocks()` del motore comune (sezione 1.2): niente marcatori, il testo dei link e non l’indirizzo, formule in parole. Gli elenchi non si saltano: ogni voce diventa una frase («Primo, …», «Secondo, …» per gli elenchi numerati). I blocchi di codice non si leggono e si saltano: la regola 7 del parlato chiede di non scriverne, e il testo non si mostra.
2. **Etichette d’emozione.** Un’etichetta all’inizio della risposta o di una frase (`[sorride]`, `[pensierosa]`, `[commossa]`, `[divertita]`, `[perplessa]`, `[seria]`) si toglie dal testo e va al volto. Un’etichetta sconosciuta si toglie e si ignora.
3. **Divisione in frasi.** Si taglia a fine frase (`.`, `?`, `!`, `…`, due punti seguiti da spazio). Se una frase supera 120 caratteri si taglia anche alla prima virgola dopo 40 caratteri. La **prima** frase si manda appena ha 25 caratteri e incontra una virgola: è quella che decide quanto si aspetta.
4. **Lessico delle pronunce.** File `~/.local/share/ruscallisse/pronunce.tsv`, una riga per parola: `parola<TAB>come scriverla`, cioè la parola **riscritta** con l’accento grafico al posto giusto (`ancora<TAB>ancóra`): espeak-ng rispetta l’accento grafico (punto 5). Prima di mandare la frase a Piper, ogni parola del lessico (confronto senza maiuscole, parola intera) si sostituisce con la sua riscrittura. Non si usano fonemi IPA fra `[[ ]]`: l’API C di libpiper, che usa `ruscapiper-stream`, non li accetta; le righe di questo tipo si ignorano. Il pacchetto installa un lessico di partenza in `/usr/share/ruscallisse/pronunce.tsv` con le parole italiane che espeak-ng accentua male o che portano l’accento grafico della regola 4 (`ancòra`, `àncora`, `princìpi`, `prìncipi`…); quello dell’utente vale di più. Ogni riga del lessico di partenza ha un test.
5. **Controllo dell’accento.** (Non ancora nella prova.) Il menu principale avrà **Come la pronuncia?…**: si scrive una parola, la finestra mostra i fonemi con la sillaba accentata in evidenza (`espeak-ng -v it -q --ipa`), la fa dire all’entità e offre **Correggi la pronuncia…**, che scrive la riga nel lessico dell’utente. Verifica fatta con l’espeak-ng di Piper: accentua bene le sdrucciole (sàbato, telèfono, capitàno/càpitano) e **rispetta l’accento grafico** (princìpi/prìncipi, subìto, àncora); l’accento grave su una *o* la apre (*ancòra* → [ɔ]), per questo la regola 4 chiede l’acuto sulle vocali chiuse. Il lessico di partenza resta quasi vuoto: servono solo le parole che sbaglia anche così.

#### 1.7.7 Parlare: Piper

- `rusca_piper.py` avvia `/usr/lib/ruscapiper-engine/ruscapiper-stream --voice <file.onnx>` all’apertura (e al cambio di voce) e lo tiene aperto (variabile `RUSCAPIPER_STREAM` per le prove). All’avvio il programma scrive `RPS1` e la versione del protocollo (u32 little endian, 1). Sullo standard input riceve **una riga per frase**, `ID<TAB>LENGTH_SCALE<TAB>TESTO` (niente JSON: le tabulazioni e gli a capo nel testo si tolgono prima). Sullo standard output scrive, per ogni frase, uno o più blocchi: `RPSC`, sette u32 (identificativo, flag, frequenza, campioni, fonemi, allineamenti), poi i campioni PCM a 16 bit, i fonemi (codici Unicode, gruppi separati da 0) e gli allineamenti (i32, campioni per fonema). Flag 1 = ultimo blocco della frase, flag 2 = errore (la frase si perde, il programma resta aperto e l’errore va sul terminale). Il volume si normalizza a ogni blocco. Così la voce si carica una volta sola, RuscaLLisse sa dove finisce ogni frase e **la bocca si muove a tempo**: i visemi si calcolano dagli allineamenti di Piper (`segments()`), non stimando la durata.
- **Lo standard error di `ruscapiper-stream` si legge sempre**, in un thread: l’ONNX Runtime di Debian vi scrive centinaia di righe «Schema error» a ogni voce caricata (bug Debian #1092898, innocuo). Se non lo si legge, il tubo si riempie (64 KB), `ruscapiper-stream` si ferma prima di scrivere `RPS1` e la finestra resta su «Si sta svegliando…». Le righe «Schema error» si scartano; le altre vanno sul terminale e, se la voce non parte, nel messaggio d’errore. Un test lo verifica con 300 KB di righe prima di `RPS1`.
- `length_scale` viene dalla velocità dell’entità: velocità 0,95 → `length_scale` 1/0,95.
- **Riproduzione.** `/usr/bin/pw-play --raw --rate <frequenza della voce> --channels 1 --format s16 -` (`--raw` come per il microfono), aperto subito e tenuto aperto; all’apertura riceve **0,4 s di silenzio** (`PREROLL`): l’uscita audio si sveglia e i primi istanti andrebbero persi, e del saluto non si sentirebbe l’inizio. Fra due frasi c’è una pausa di 0,2 s (0,35 s dopo un punto interrogativo). Se `pw-play` si ferma, il suo messaggio d’errore va sul terminale e la finestra lo segnala: un errore della voce non resta mai nascosto.
- **Voci.** Non fanno parte dei pacchetti. Ogni voce è la coppia `nome.onnx` e `nome.onnx.json`, in `~/.local/share/ruscapiper/voices/` o in `/usr/share/ruscapiper/voices/`. **Importa una voce…** (menu principale e pagina di benvenuto) chiede il file `.onnx`, controlla che accanto ci sia il `.onnx.json` (altrimenti lo dice: «Manca il file nome.onnx.json, che descrive la voce: va scaricato insieme al modello.»), e copia la coppia; se accanto c’è il file `MODEL_CARD`, copia anche quello come `nome.MODEL_CARD`. La lingua della voce si legge dal `.onnx.json` (`language.code`).
- **Licenza della voce.** Le Preferenze mostrano, sotto la voce scelta, il dataset e la licenza letti dal MODEL_CARD, oppure «Licenza non indicata». Il manuale ricorda che ogni voce ha la sua licenza e che molte voci Piper sono derivate dalla voce inglese «lessac», distribuita per la sola ricerca non commerciale: per video pubblicati o usi commerciali va scelta una voce con una licenza libera verificata.

#### 1.7.8 Il volto

Il volto è disegnato da `face.py` con Cairo in un `Gtk.DrawingArea`, aggiornato con `add_tick_callback()` (al ritmo dello schermo, senza timer propri). Niente immagini, niente modelli: un’illustrazione vettoriale fatta di curve e sfumature.

**Ellittica.** Una donna digitale, personaggio originale (nessun volto reale come modello):

- volto ovale, pelle rosata chiara; capelli **corti** color Prugna 600 (`#7a2357`): un caschetto che arriva al mento con le punte verso l’interno, la frangia di lato che scende da sinistra a destra in ciocche morbide, la ciocca sinistra davanti al viso e la destra portata **dietro l’orecchio**; un riflesso di luce sulla testa e, sul bordo destro, il riflesso rosa dell’orbita;
- **occhiali** con lenti ovali e montatura sottile Prugna 900 (`#2d0a1d`), più chiara in basso, con un riflesso obliquo sulle lenti e una leggera ombra sulla pelle;
- una **matita dietro l’orecchio** (legno `#e8b04a`, gomma Rosa 250, punta Prugna 800): è il suo segno di riconoscimento, ripreso nell’icona. L’icona di RuscaLLisse segue la regola delle altre (l’anello dell’emblema con il simbolo del tool al posto dell’aeroplanino): nel disco c’è il ritratto di Ellittica, con caschetto, occhiali, matita e orbita, generato da `branding/generators/ruscalinux-tool-icons.py`;
- occhi grandi a mandorla: iride Prugna 500 più chiara in basso, con le fibre, l’anello scuro sul bordo, la pupilla e due riflessi; palpebra superiore più spessa verso l’esterno, con tre ciglia e la piega sopra; sopracciglia piene, sottili in coda; guance Rosa 300; un piccolo orecchino a forma d’orbita;
- intorno alla testa un’**orbita**: un’ellisse sottile Rosa 300 con un punto che la percorre (davanti alla testa Prugna 600 con il bordo crema, dietro Rosa 300).

**Disegno.** Spazio di disegno di 400 × 400 punti, scalato sulla finestra. La luce viene da sinistra in alto: chiaroscuro del viso fatto di sfumature (ombra a destra e sotto la mascella, luce su fronte, zigomi e mento), ombre morbide della frangia e delle ciocche sulla pelle (Cairo non sfoca: la stessa sagoma ripetuta, spostata e sempre più trasparente), labbra con l’arco di Cupido e un riflesso, naso appena accennato. Maglione prugna a coste con una camicetta e un ciondolo a forma d’orbita su una catenina. L’orbita passa davvero dietro la testa (metà disegnata prima del volto) e davanti (metà disegnata dopo i capelli). Nessun contorno pesante.

**Velocità.** Il volto non deve togliere il processore ai motori. Le parti che non cambiano (capelli dietro e davanti, viso con le ombre, orecchio, matita, naso, maglione) si disegnano **una volta** per dimensione della finestra in tre immagini in memoria (`_layer()`, al massimo dieci, le più vecchie si buttano) e a ogni fotogramma si incollano; si ridisegnano solo occhi, sopracciglia, occhiali, bocca, orbita e riflesso. L’inclinazione della testa (quando ascolta o pensa) è salvata nelle immagini a passi di 0,004 radianti, invisibili; a riposo la testa **ondeggia di lato** invece di ruotare, perché incollare un’immagine ruotata costa cinque volte tanto. Misure di riferimento: circa 3 ms a fotogramma a 400 pixel e 6 ms a 700 (il volto disegnato tutto ogni volta costava 15 e 28 ms); il primo fotogramma, e quelli in cui la testa si sta inclinando, costano di più.

**La materializzazione.** La prima volta che il volto compare, mentre i modelli si caricano, Ellittica si materializza dal nulla in circa 2,8 secondi (`APPEAR_TIME`): scie di luce rosa arrivano a spirale da ogni parte e si raccolgono nella sua sagoma (contorno dei capelli e del volto, occhiali, bocca, spalle); poi il volto compare dal basso dietro una linea di luce, e alla fine l’orbita si disegna da sola intorno alla testa. Con «Animazioni ridotte» compare subito, senza effetto.

**Stati** (da `conversation.py`):

| Stato | Volto |
|---|---|
| A riposo | Respiro lento, testa che ondeggia appena, battito di ciglia ogni 2–5 s, sguardo con piccoli scatti come quello di una persona vera, sorriso leggero, orbita lenta |
| In ascolto | Testa inclinata di circa 5°, sopracciglia sollevate, occhi un po’ socchiusi in un sorriso; l’orbita si ispessisce con il livello del microfono, così si vede che sente |
| Pensa | Sguardo in alto, oltre la montatura; il punto corre veloce sull’orbita |
| Parla | Bocca dai visemi e dall’ampiezza dell’audio; sopracciglia che seguono l’intonazione; a fine frase una breve pausa con lo sguardo verso l’utente |
| Microfono in pausa | Come a riposo, con gli occhi rivolti in basso e l’orbita senza punto |

**La bocca.** Ogni frase, prima di andare a Piper, si trasforma in fonemi con `espeak-ng -v <lingua> -q -x` (lo stesso alfabeto del lessico); ogni fonema diventa un **visema** (`VISEMI` in `face.py`): *a* aperta, *e* media e larga, *i* larga e stretta, *o* tonda, *u* tonda e piccola, *m b p* chiusa, *f v* sul labbro, le altre consonanti socchiusa. I visemi della frase si distribuiscono sulla sua durata, che si conosce dal numero di campioni. In più, l’**ampiezza** dell’audio (valore efficace a blocchi di 20 ms) dice quanto si apre la bocca in quel momento. La bocca segue i due valori con un filtro, così non scatta.

**Sincronia.** Il volto usa l’audio che `audio_io.py` sta mandando a `pw-play`, spostato in avanti della latenza di riproduzione (`--latency` di `pw-play`, 40 ms se non cambiata). La latenza si regola nelle Preferenze avanzate se la bocca anticipa o ritarda.

**Espressioni.** Le etichette d’emozione (sezione 1.7.6) cambiano sopracciglia, occhi e angoli della bocca per la frase che segue: `sorride` (occhi socchiusi, angoli in alto), `pensierosa` (sguardo di lato, un sopracciglio alzato), `commossa` (sopracciglia sollevate all’interno, sguardo morbido), `divertita` (sorriso largo), `perplessa` (sopracciglia asimmetriche), `seria` (sopracciglia diritte, bocca neutra).

**Eccezione alla sezione 3.11, regola 5.** Il volto è il contenuto del programma, non una decorazione: le sue animazioni sono ammesse. Con **Animazioni ridotte** attivo (`Gtk.Settings:gtk-enable-animations` spento) il volto non respira, non ondeggia, non sposta lo sguardo e l’orbita è ferma: cambiano solo l’espressione da uno stato all’altro, il battito di ciglia e la bocca mentre parla.

**Colori e contrasti.** Il volto usa la palette della sezione 4.1, più il legno della matita (`#e8b04a`), solo decorativo, e **non cambia con il tema**: contorni, occhiali e sopracciglia stanno sul volto (pelle chiara) e non sul fondo, quindi restano leggibili anche in modalità scura, dove il volto sta su `--view-bg-color`. Nessun testo è disegnato sul volto.

**Accessibilità.** Il `Gtk.DrawingArea` ha un’etichetta accessibile che dice l’entità e lo stato («Ellittica, in ascolto»), aggiornata a ogni cambio di stato. Lo stato si legge anche nel sottotitolo della barra del titolo, quindi non è affidato solo al disegno.

#### 1.7.9 L’interfaccia

```text
Adw.ApplicationWindow
└── Adw.ToolbarView
    ├── top: Adw.HeaderBar
    │   ├── start: pulsante del microfono (Spazio) · selettore dell’entità
    │   ├── title: Adw.WindowTitle (nome dell’entità + stato)
    │   └── end: menu principale
    └── content: Adw.ToastOverlay
        └── Gtk.Box verticale
            └── volto (Gtk.DrawingArea, occupa tutta la finestra, almeno 240 × 240)
```

- **Pagina di benvenuto.** Finché manca un pezzo, al posto del volto c’è un `Adw.StatusPage` con i tre pezzi che servono, ognuno su una riga (`Adw.ActionRow`) con lo stato («Pronto» o «Manca») e i pulsanti: **Modello per ascoltare** (Apri la cartella, Quali file scaricare?), **Modello per pensare** (Apri la cartella; se RuscaLLama ne ha già uno, è pronto), **Voce** (Importa una voce…, Quali file scaricare?). **Quali file scaricare?** (`GUIDE` in `ruscallisse.py`) elenca per ogni pezzo nome e pagina dei file, e si apre nel browser: RuscaLLisse non scarica niente.
- **Il microfono.** Il pulsante (icona `audio-input-microphone-symbolic`, barrata quando è in pausa) e il tasto Spazio mettono in pausa e riprendono l’ascolto. In pausa `pw-record` è fermo, non solo ignorato.
- **L’eco.** In un dialogo vero si interrompe parlando, senza tasti. Con gli altoparlanti, però, il microfono sentirebbe l’entità. La soluzione è la cancellazione dell’eco di PipeWire (`libpipewire-module-echo-cancel`): la ISO la attiva con un file in `/etc/pipewire/pipewire.conf.d/`, che crea una sorgente e un’uscita con l’eco tolto, e RuscaLLisse le usa quando ci sono. Senza cancellazione dell’eco, per impostazione predefinita, **mentre l’entità parla RuscaLLisse non passa l’audio a Vosk**; la si interrompe con Spazio o con Esc. Nelle Preferenze, «Uso le cuffie» (spento se non cambiato) lascia il microfono aperto anche mentre parla: se l’utente parla per più di 0,4 s l’entità tace e ascolta. Se in PipeWire c’è una sorgente con cancellazione dell’eco (`echo-cancel`), le Preferenze la propongono come microfono e «Uso le cuffie» si può attivare anche con gli altoparlanti.
- **L’interruzione.** Esc fa tacere subito l’entità: si svuota la coda delle frasi, si chiude il flusso verso `pw-play`, si ferma la generazione di `llama-server`. La risposta interrotta resta nella storia, troncata dove si è fermata.
- **Menu principale:** Ricomincia (Ctrl+N: l’entità dimentica la conversazione e saluta di nuovo), separatore, Modifica la personalità…, Nuova entità…, Come la pronuncia?…, Importa una voce…, Apri la cartella dei modelli per ascoltare, separatore, Preferenze, Scorciatoie da tastiera, Informazioni su RuscaLLisse.
- **Scorciatoie:** Spazio (microfono), Esc (zitta), Ctrl+N (ricomincia), più quelle della sezione 3.9.
- **Preferenze** (`~/.config/ruscallisse/settings.json`): Conversazione (lingua della conversazione, etichette d’emozione, parole massime per risposta, pausa prima di rispondere), Ascolto (modello Vosk, microfono, uso le cuffie; la cancellazione dell’eco si usa da sola quando c’è), Voce (voce, velocità, licenza della voce), Modello (modello GGUF, scheda grafica), Aspetto (tema, sezione 4.5), Avanzate (latenza della riproduzione).
- **Chiusura.** La finestra si chiude senza domande: la conversazione non si salva mai, per scelta.

#### 1.7.10 Dati

| Cosa | Dove |
|---|---|
| Impostazioni | `~/.config/ruscallisse/settings.json` |
| Entità | `~/.local/share/ruscallisse/entities/*.md` |
| Lessico delle pronunce | `~/.local/share/ruscallisse/pronunce.tsv` |
| Modelli Vosk | `~/.local/share/ruscavosk/models/`, `/usr/share/ruscavosk/models/` |
| Voci Piper | `~/.local/share/ruscapiper/voices/`, `/usr/share/ruscapiper/voices/` |
| Modelli linguistici | Quelli di RuscaLLama (sezione 1.1) |
| Conversazione | Solo in memoria, mai su disco; si dimentica con «Ricomincia» e alla chiusura |
| Audio | Mai su disco |

**Test.** `tests/test_ruscallisse.py` controlla, senza motori veri: la lettura e la scrittura dei file delle entità e il prompt di sistema; la divisione in frasi (compresa la prima frase corta), le etichette d’emozione, gli elenchi letti come frasi, il lessico delle pronunce (riscrittura con l’accento grafico; le righe `[[…]]` si saltano); i visemi da una stringa di fonemi; il filtro dell’ascolto (parole incerte fra parentesi quadre, interpretazioni alternative sotto la soglia); i passaggi di stato di `conversation.py` (ascolto → pensa → parla → ascolto, interruzione con Esc e a voce, microfono in pausa, eco senza cuffie e con la cancellazione dell’eco); che nessun testo della conversazione finisca su disco o nella finestra con un riconoscitore finto al posto di `libvosk`, un `ruscapiper-stream` finto che parla lo stesso protocollo (intestazioni, PCM vero, fonemi con e senza allineamenti, errori, 300 KB su stderr prima di essere pronto; senza `ruscapiper-stream` la voce non parte e dà `err_no_piper`), e un `llama-server` finto in streaming; l’assenza di moduli di rete fuori da `rusca_engine.py`. Le prove del volto disegnano ogni stato su una superficie Cairo in memoria e controllano che l’etichetta accessibile cambi. Senza PyGObject si saltano le prove con GTK.

```bash
python3 -m unittest tests/test_ruscallisse.py
```

### 1.8 ruscavosk-engine e ruscapiper-engine

**ruscavosk-engine è Vosk** (<https://github.com/alphacep/vosk-api>), software esterno con licenza Apache 2.0, copyright Alpha Cephei Inc., con il ramo `vosk` di Kaldi di Alpha Cephei (<https://github.com/alphacep/kaldi>, Apache 2.0) e la versione di OpenFst di Alpha Cephei (<https://github.com/alphacep/openfst>, OpenFst 1.8.0 con una decina di piccole correzioni, fra cui una ricerca di raggiungibilità più veloce usata nella decodifica; Apache 2.0). Kaldi e OpenFst finiscono **statici** dentro `libvosk.so`. Per il calcolo si usa l’**OpenBLAS di Debian**, collegato dinamicamente, nella variante senza thread (`libopenblas-serial-dev`, come la ricetta di Vosk, che compila OpenBLAS con `USE_THREAD=0`): niente OpenBLAS e niente CLAPACK da compilare. RuscaLinux compila tutto dal sorgente con **una sola modifica**, `apps/ruscavosk-engine/patches/kaldi-lapack.patch`: con LAPACK ≥ 3.9 `lapack.h` dichiara le funzioni Fortran con le lunghezze nascoste degli argomenti stringa, e Kaldi le chiamava senza (la compilazione si ferma in `cblas-wrappers.h`); la patch le fa passare dalle macro `LAPACK_xxx()`, che le aggiungono.

- Il pacchetto contiene solo `libvosk.so`, in `/usr/lib/ruscavosk-engine/` (circa 8 MB; dipende da `libopenblas0`, `libstdc++6`, `libgcc-s1`, `libc6`). Niente vosk-server, niente modulo Python da PyPI: RuscaLLisse usa la libreria con `ctypes`.
- **Nessun processo e nessuna porta.** La libreria lavora dentro il processo di RuscaLLisse, sull’audio che riceve in memoria.
- **Thread di OpenBLAS.** La libreria chiede `libopenblas.so.0`: Debian lo fa puntare alla variante scelta con `update-alternatives`, che può essere quella con i thread. RuscaLLisse imposta `OPENBLAS_NUM_THREADS=1` prima di caricarla, così il calcolo resta su un thread qualunque sia la variante.
- **`popen` nella libreria.** Kaldi sa leggere un file come uscita di un comando, se il nome finisce con `|` (è anche nella libreria già compilata di Vosk). Non è codice di rete, ma vuol dire che un modello costruito apposta potrebbe far eseguire un comando: i modelli si prendono da fonti fidate (sezione 1.7.5).
- Il pacchetto del motore non ha interfaccia: lo dichiara la finestra Informazioni di RuscaLLisse, nel gruppo «Componenti esterni».

**ruscapiper-engine è Piper** (<https://github.com/OHF-Voice/piper1-gpl>), software esterno con licenza GPL-3.0, copyright Michael Hansen e gli autori di Piper, con espeak-ng (<https://github.com/espeak-ng/espeak-ng>, GPL-3.0) compilato dentro, come libreria statica, per i fonemi. espeak-ng **non** è quello di Debian: Piper usa `espeak_TextToPhonemesWithTerminator()`, che espeak-ng 1.52 (trixie) non ha; si compila il commit che piper1-gpl fissa nel suo `libpiper/CMakeLists.txt` (per Piper 1.8.0: `212928b394a9`), con le opzioni di Piper (niente audio, MBROLA, sonic, Klatt). È la continuazione del Piper originale (`rhasspy/piper`, MIT), archiviato nell’ottobre 2025. RuscaLinux lo compila dal sorgente, con l’**ONNX Runtime di Debian** (`libonnxruntime-dev`, in trixie 1.21) al posto di quello che la build di Piper scaricherebbe. La build di Piper non si usa: `apps/ruscapiper-engine/CMakeLists.txt` compila i file sorgente di `libpiper/src/`, con espeak-ng e ONNX Runtime locali. **Modifiche al codice di Piper**, in `apps/ruscapiper-engine/patches/`, nel pacchetto (`/usr/share/doc/ruscapiper-engine/`) e dichiarate nel file `copyright`. (1) `fonemi.patch`, sempre: libpiper 1.8.0 attribuisce ogni chiave della mappa dei fonemi al suo **primo** codepoint, e le voci recenti (per esempio `it_IT-serena-high`) hanno chiavi di più caratteri per i gruppi vocalici (`aɪ`, `aʊ`, `eɪ`, `oʊ`, `ɔɪ`): ogni «a», «e», «o», «ɔ» italiana riceveva anche l’id del dittongo inglese e la voce parlava con **accento straniero** (scoperto sulla macchina di prova: 6,63 s di audio contro 5,29 del Piper in Python, vocali doppie nei fonemi). La patch salta quelle chiavi, come fa Piper in Python quando il gruppo non compare; in più svuota i fonemi a ogni frase (libpiper li accumulava, e la bocca avrebbe seguito anche le frasi precedenti). La build lo controlla: con la chiave `aɪ` aggiunta alla voce di prova i fonemi non devono cambiare. (2) `onnxruntime-1.21.patch`: Piper 1.8.0 è scritto per ONNX Runtime 1.22 e chiama `Session::GetOutputNames()`, che la 1.21 non ha; `apps/ruscapiper-engine/patches/onnxruntime-1.21.patch` la sostituisce con `GetOutputCount()` e `GetOutputNameAllocated()` (nella 1.21 ci sono), con lo stesso risultato. La build la applica solo se le intestazioni di ONNX Runtime del sistema non contengono `GetOutputNames`; quando Debian avrà la 1.22 la patch smette di servire da sé. Se una release nuova di Piper cambia quelle righe, la patch non si applica e la build si ferma: va aggiornata, o tolta se il difetto è stato corretto da Piper.

- Il pacchetto contiene, in `/usr/lib/ruscapiper-engine/`: `libpiper.so` (la libreria C di Piper), i dati di espeak-ng che Piper usa, e **`ruscapiper-stream`**, un piccolo programma in C scritto da RuscaLinux (GPL-3.0, file a sé in `apps/ruscapiper-engine/ruscapiper-stream.c`, sezione 6, regola 6) che apre una voce con l’API di libpiper, legge una riga per frase dallo standard input e scrive intestazioni, PCM e allineamenti dei fonemi sullo standard output (sezione 1.7.7). È il programma che avvia RuscaLLisse.
- I nomi delle funzioni dell’API di libpiper che `ruscapiper-stream` usa (per esempio `piper_create()`) si fissano sul tag della release costruita: la build controlla che la libreria li esporti (`SIMBOLI_PIPER`).
- **L’ultimo pezzo arriva con `PIPER_DONE`.** In libpiper 1.8.0 `piper_synthesize_next()` restituisce l’ultimo pezzo di audio insieme a `PIPER_DONE`, non prima (l’esempio del README di Piper lo perderebbe): `ruscapiper-stream` lo scrive comunque, con il flag 1. Una frase corta è un solo pezzo: perderlo vuol dire perdere tutta la voce. Quasi tutte le voci pubblicate non danno gli allineamenti (si aggiungono con `patch_voice_with_alignment.py` di Piper): allora i visemi vengono dai fonemi del pezzo, uno per gruppo (`group_visemes()`), distribuiti in parti uguali sulla sua durata; la bocca non resta mai ferma.
- **Nessuna porta.** `ruscapiper-stream` legge e scrive solo i propri flussi standard: niente server HTTP di Piper.
- Le voci non fanno parte dei pacchetti (sezione 1.7.7).

**Da verificare alla prima build** (prima di scriverli come fatti):

1. **libpiper.** I nomi delle funzioni dell’API C sono verificati sul tag v1.8.0 (`piper.h`), ed espeak-ng al commit fissato si compila senza rete. Resta da verificare, sul PC di sviluppo, la compilazione completa di `libpiper.so` con l’ONNX Runtime 1.21 di Debian e la prova con la voce di prova.
2. **Vosk e Kaldi.** Quale commit del fork di Kaldi vuole l’ultima release di vosk-api, e se si compila con OpenBLAS, LAPACK e OpenFST di Debian o servono le loro copie.
3. **Accenti grafici.** Verificato (sezione 1.7.6, punto 5): espeak-ng rispetta l’accento grafico; per le vocali chiuse serve l’acuto.
4. **Voci italiane.** La licenza di `it_IT-riccardo-x_low` (dal suo MODEL_CARD) e l’origine del dataset sintetico di `it_IT-serena`, prima di consigliarle nel manuale.
5. **Cancellazione dell’eco.** Che `libpipewire-module-echo-cancel` (con WebRTC) sia nel PipeWire di trixie, che il file di configurazione della ISO crei sorgente e uscita senza disturbare le altre applicazioni, e che con gli altoparlanti l’interruzione a voce funzioni davvero.
6. **Latenza.** I tempi veri sui due computer di prova (checklist, punto 19): se il primo campione arriva oltre circa un secondo e mezzo, si guarda prima la soglia di silenzio, poi la dimensione del modello linguistico.

### 1.9 Il doppiaggio

**Stato: fase 1 nella 1.99.3.** RuscaDubbing (`apps/ruscadubbing/`, versione 1.99.3) è la sala di doppiaggio di RuscaLinux: da un video nella sua lingua ottiene i sottotitoli nelle due lingue, l’audio doppiato e il video doppiato. Non ha motori né modelli propri: usa quelli delle altre app.

| Passo | Motore | Modulo (copia identica di) | Modelli |
|---|---|---|---|
| Trascrizione | `whisper-cli` di ruscawhisper-engine | `rusca_whisper.py` (RuscaTranscriber) | `~/.local/share/ruscawhisper/models/` |
| Traduzione | `llama-server` di ruscallama-engine | `rusca_engine.py` (RuscaTranslator) | `~/.local/share/ruscallama/models/` |
| Doppiaggio | `llama-tts` di ruscallama-engine | `rusca_tts.py` (RuscaNarrator) | `~/.local/share/ruscanarrator/models/`, voci in `…/voices/` |
| Missaggio e video | `ffmpeg` di Debian | `rusca_dubbing.py` | — |

`rusca_dubbing.py` è la catena, senza interfaccia; `ruscadubbing.py` è la finestra. I moduli comuni sono **copie identiche** (anche `rusca_markdown.py` e `markdown_it_mark.py`, che `rusca_tts.py` importa, e `style.css`): `rusca_dubbing.py` cambia solo la loro cartella di lavoro dopo l’import (`whisper.WORK_DIR`, `tts.WORK_DIR`), che diventa una sottocartella di `~/.cache/ruscadubbing/`.

- **Un passo per volta.** I modelli non stanno insieme nella memoria della scheda grafica: il modello di traduzione si chiude prima che parta quello della voce. I passi si concatenano nel thread dell’interfaccia, ognuno dalla fine del precedente (`on_done`).
- **Modelli alla prima apertura.** Senza impostazioni salvate, RuscaDubbing prende le scelte già fatte nelle altre app (`sibling_settings()`): il modello Whisper di RuscaTranscriber, il modello linguistico di RuscaTranslator, il modello della voce, la voce di riferimento, la voce del modello, il seme e la velocità massima di RuscaNarrator. Anche quando un modello salvato non c’è più si ripiega prima su quello dell’altra app. Prendere il primo file in ordine alfabetico sceglieva il modello della voce 0.6B al posto del 1.7B, e il doppiaggio sbagliava accenti che RuscaNarrator diceva bene (libérta, pérche, cérchero).
- **Battute.** I segmenti di Whisper diventano battute (`cues_from_segments()`): due segmenti si uniscono se il primo non finisce con un segno di fine frase, la pausa è di al massimo 600 ms, la battuta resta entro 7 s e 140 caratteri. Al posto della trascrizione si può dare un file SRT della lingua originale (per esempio corretto a mano): allora la lingua originale va scelta, e un video senza audio si può doppiare solo così.
- **Frasi, non battute** (`cue_parts()`, `group_blocks()`). Tradurre battuta per battuta costringeva il modello a far tornare i pezzi di una frase spezzata fra più battute (russo e italiano mettono le parole in ordine diverso): chiudeva le frasi in anticipo («…senza stancarsi troppo.» / «di conoscenze.»), anticipava parole di una battuta, aggiungeva «…»; e la voce diceva frammenti con l’intonazione sbagliata (verificato sulla lezione russa di prova: 49 battute, quasi tutte a metà frase). Ora: (1) ogni battuta si divide anche dove una frase finisce al suo interno, con i tempi stimati in proporzione ai caratteri; (2) i pezzi si raggruppano in **frasi intere**: una frase si chiude dopo il segno di fine frase; una frase breve (sotto 8 s) si unisce alla successiva se anche quella è intera, ci sta e segue entro 0,7 s; una frase lunga si chiude a una virgola dopo 15 s, a meno che la battuta dopo la finisca; limiti 30 s, 420 caratteri, pausa di 1,5 s. Sulla lezione di prova: 49 battute → 80 pezzi → 39 frasi, nessuna chiusa a metà.
- **Traduzione con il tempo.** Le frasi si traducono a gruppi di 8, con le ultime 3 già tradotte come contesto, nel formato `N|MAX|testo`, dove MAX è il numero massimo di caratteri (`budget_chars()`): il tempo della frase (fino alla successiva) per i caratteri al secondo della lingua (`CHARS_PER_SECOND`, per esempio 14 per l’italiano), con metà dell’accelerazione permessa. Il prompt chiede un adattamento da doppiatore: fedele, parlato, scorrevole, condensato quando serve; ogni parte tradotta nel suo ordine; niente punto se la frase originale si interrompe; mai «…» che nell’originale non ci sono (`clean_translation()` li toglie comunque ai capi). La risposta si legge riga per riga (`N|traduzione`); una frase che manca si richiede da sola, e se non torna resta l’originale (lo si dice alla fine). Una traduzione più lunga di 1,25 volte MAX si richiede in versione breve. Campionamento a temperatura 0,2, ragionamento spento. Se lingua originale e del doppiaggio coincidono, non si traduce.
- **Sottotitoli con le regole professionali** (`segment_subtitles()`, `wrap_lines()`). I sottotitoli **tradotti** non ereditano i tagli dell’originale: ogni frase tradotta si divide in sottotitoli propri, nel tempo della frase, con le regole comuni delle guide professionali (per esempio quelle di Netflix per molte lingue europee): al massimo 2 righe da 42 caratteri (16 per cinese e coreano, 13 per il giapponese, che si dividono per caratteri), una riga sola quando ci sta; a capo e fine del sottotitolo dopo la punteggiatura dove si può, mai dopo un articolo, una preposizione o una congiunzione (parole di al massimo tre lettere minuscole), a piramide, mai una o due parole sole in alto; durata da 5/6 di secondo a circa 7 s; 2 fotogrammi (83 ms) fra un sottotitolo e l’altro; tempi proporzionali al testo. La divisione è una programmazione dinamica sui tagli possibili. Un sottotitolo più veloce di 17 caratteri al secondo (9 per il cinese, 4 per il giapponese, 12 per il coreano) resta fino a un secondo dopo la voce, se c’è spazio; quelli che restano troppo veloci si contano e la finestra lo dice (accorciarli è lavoro dell’editor, fase 2). I sottotitoli **originali** seguono le stesse regole battuta per battuta. Il file con le due lingue (`.src-tgt.srt`) resta sulle battute originali, con la traduzione ridivisa in proporzione (`translations_per_cue()`). Sulla lezione di prova: 39 frasi → 78 sottotitoli, righe di al massimo 42 caratteri, durate da 1,1 a 7,5 s.
- **Doppiaggio.** Le **frasi** tradotte vanno a `rusca_tts.Speaker` in modo SRT: la voce dice ogni frase intera, dall’inizio della sua prima battuta, accelerata con `atempo` fino alla velocità massima (1,3 se non cambiata), poi spostata in avanti; due battute non si sovrappongono mai. Per una voce sola in tutto il video serve una **voce di riferimento**: alla prima apertura si prende la prima voce creata con RuscaNarrator.
- **Voce simile all'originale** (`rusca_voicematch.py`). Con una voce di riferimento in un'altra lingua, Qwen3-TTS ne copia anche l'accento (verificato: un riferimento russo dà libérta, pérche, cérchero; la stessa voce in RuscaNarrator con un riferimento italiano dice bene). «Trova una voce simile…» propone invece voci **nella lingua del doppiaggio** che somigliano all'originale per registro: (1) fino a 60 s del parlato originale (le battute più lunghe, se ci sono i sottotitoli originali o un doppiaggio appena fatto, altrimenti tre tratti di 20 s al 20, 50 e 80 % del video) in un WAV a 16 kHz; (2) tre misure: altezza mediana in semitoni (YIN su audio a 4 kHz, finestre di 40 ms, solo tratti con voce; si tolgono i tratti a più di un'ottava dalla mediana), variazione (scarto interquartile in semitoni), brillantezza (baricentro mediano dello spettro con `aspectralstats` di FFmpeg, solo tratti poco piatti); (3) otto voci inventate da llama-tts **senza** voce di riferimento, con semi casuali, che dicono una frase fissa di circa 10 s (`VOICE_TEXT`); (4) distanza = |Δaltezza| + 0,33·|Δbrillantezza in semitoni| + 0,5·|Δvariazione|, somiglianza = 100·e^(−d/7) %. Si mostrano le quattro più vicine, ognuna con ascolto, somiglianza e differenze; «Altre voci» ne aggiunge otto. La voce scelta si salva con `tts.save_voice()` fra quelle di RuscaNarrator e diventa la voce di riferimento. Il modello della voce non riceve mai l'audio originale; l'audio originale e le voci di prova stanno in `~/.cache/ruscadubbing/voci/` e si cancellano alla chiusura della finestra. Nessun modulo di rete, niente numpy: tutto in Python e FFmpeg (un minuto di voce si misura in circa un secondo).
- **Missaggio.** La voce sta sopra l’audio originale abbassato (doppiaggio «a voce sopra»): `sidechaincompress` con la voce come segnale di controllo, poi `amix` e `alimiter`, stereo a 48 kHz. Tre livelli: poco (ratio 4), abbastanza (8, predefinito), molto (16).
- **Video.** Immagine **copiata** (`-c:v copy`), capitoli copiati; traccia audio 1 l’originale (copiata in MKV), traccia 2 il doppiaggio (Opus 160 kbit/s in MKV, AAC 192 kbit/s in MP4) **predefinita**; due tracce di sottotitoli (SRT in MKV, `mov_text` in MP4), non predefinite. Ogni traccia ha la lingua ISO 639-2 e un titolo con il nome della lingua. Senza audio originale c’è solo il doppiaggio. MKV è il formato predefinito: MP4 non accetta ogni codec video, e se fallisce l’errore lo dice (`err_mux_mp4`).
- **File in uscita**, accanto al video o in una cartella scelta: `nome.<src>.srt`, `nome.<tgt>.srt`, `nome.<src>-<tgt>.srt` (le due lingue in ogni sottotitolo, sopra l’originale), `nome.<tgt>.opus`, `nome.<tgt>.mkv`. Non si sovrascrive mai niente (`nome.it (2).mkv`); audio e video si scrivono in un file `.part` e si rinominano alla fine. Dopo un errore i file già scritti restano, e la finestra lo dice.
- **Finestra.** Pagina vuota (scegli o trascina un video) → impostazioni (video con durata e tracce; lingue; sottotitoli originali trascritti o da file; che cosa ottenere: sottotitoli, audio, video; formato; audio originale sotto la voce; cartella) → lavoro (i quattro passi con stato, avanzamento complessivo, tempo trascorso, **Ferma**) → risultato (battute, accelerazioni, battute non tradotte; elenco dei file da aprire; Guarda, Apri la cartella, Nuovo doppiaggio). Un `Adw.Banner` dice che cosa manca (motore o modello) e apre le Preferenze: Aspetto, Modelli (uno per passo, con il pulsante della cartella), Voce (voce di riferimento, voce del modello, velocità massima, seme), Motore (scheda grafica sì/no, **una scheda per passo**: `whisper_device`, `llm_device`, `tts_device`; thread, contesto). La scheda di ogni passo va al suo motore (`whisper.Transcriber.start(gpu_device=)`, `--device` di llama-server, `tts.Speaker.start(gpu_device=)`; la voce usa la sua anche in «Trova una voce simile»). I passi restano in sequenza: due schede servono a dare a ogni modello tutta la memoria di una, non a lavorare in parallelo. Alla prima apertura ognuna viene dalla `gpu_device` dell'app corrispondente; impostazioni con la sola `gpu_device` (prima versione) la danno a tutti e tre i passi. Chiudere durante un doppiaggio chiede conferma.
- **Privacy.** La sola connessione è quella di `rusca_engine.py` con `llama-server` su 127.0.0.1, con chiave casuale (sezione 11). `rusca_dubbing.py` non importa moduli di rete; i programmi partono senza shell; FFmpeg con `-protocol_whitelist file`. Cartella di lavoro `~/.cache/ruscadubbing/` (0700), cancellata alla fine di ogni doppiaggio, all’avvio e alla chiusura.
- **Lingue dell’interfaccia.** Italiano e inglese; le altre 24 seguiranno (sezione 9.1: finché manca il file vale l’inglese).

**Fasi successive** (piano sulla Whiteboard «RuscaDubbing — piano»): (2) un editor delle battute, con tabella, indicatore di durata, anteprima e rigenerazione di una sola battuta; (3) **ruscademucs-engine** (demucs.cpp, MIT) per separare la voce originale da musica ed effetti e toglierla del tutto; (4) più voci, una per parlante; la voce dell’attore originale solo per contenuti propri o con il suo consenso.

**Test.** `tests/test_ruscadubbing.py` controlla le battute (unione dei segmenti, SRT, SRT nelle due lingue, tempo e caratteri per battuta), la lettura delle traduzioni, la traduzione a gruppi (contesto, battute saltate richieste da sole, battuta mai tradotta, versione breve, interruzione), i nomi dei file, il comando del video; che i moduli comuni siano identici, che le cartelle di lavoro stiano sotto quella di RuscaDubbing, che it e en abbiano le stesse chiavi e tutte quelle usate, che non ci siano moduli di rete; e l’intera catena con `whisper-cli`, `llama-server` e `llama-tts` finti e FFmpeg vero su un video generato: MKV con cinque tracce, lingue e traccia predefinita, MP4 da un video muto con un SRT, solo sottotitoli, interruzione, modello mancante, nessun file di lavoro rimasto. Senza FFmpeg o PyGObject si saltano.

```bash
python3 -m unittest tests/test_ruscadubbing.py
```

Gli identificatori di ogni tool devono coincidere tra loro (vedi sezione 5.2).

Fino alla versione 1.99.1 RuscaMark usava l’App ID `org.ruscalinux.ruscamark`. Dalla 1.99.2 usa `org.ruscalinux.RuscaMark`: l’aggiornamento del pacchetto rimuove il vecchio file `.desktop`, e la metainfo dichiara il vecchio identificativo con `<replaces>` perché GNOME Software riconosca l’applicazione. Le impostazioni restano in `~/.config/ruscamark/`, che prende il nome dal comando e non dall’App ID. Il nome del tool e la parte finale dell’App ID usano la stessa grafia CamelCase: `RuscaMark` → `org.ruscalinux.RuscaMark`.

---

## ⚙️ 2. SPECIFICHE TECNICHE

| Voce | Valore |
|---|---|
| Linguaggio | Python >= 3.10 (su trixie: Python 3.13) |
| Binding | PyGObject (`python3-gi`) |
| Toolkit grafico | GTK 4 (>= 4.18) |
| Libreria GNOME | libadwaita (>= 1.7) |
| Markdown | CommonMark 0.30 con le estensioni della sezione 1.2, tramite `python3-markdown-it` (>= 3.0), `python3-mdit-py-plugins` (>= 0.4) e `python3-linkify-it` (>= 2.0) |
| Distro base | Debian Stable |
| Formato pacchetti | deb, `Architecture: all` (`amd64` per ruscallama-engine, ruscawhisper-engine, ruscadiffusion-engine, ruscavosk-engine e ruscapiper-engine, che sono compilati) |
| Versione tool | 1.99.3 |

Regole tecniche:

1. Usare Python 3 moderno, senza sintassi o moduli deprecati.
2. Usare GTK 4 con **libadwaita** per l’interfaccia. libadwaita fa parte della piattaforma GNOME ed è già presente in RuscaLinux: non conta come dipendenza esterna aggiuntiva, ed è ciò che rende un’applicazione “nativa” in GNOME (stile, modalità scura, adattività, dialoghi standard).
3. Usare solo librerie disponibili nei repository Debian Stable. Nessun pacchetto da PyPI, nessun `pip install`.
4. Preferire GLib/Gio per file, cartelle, cestino e impostazioni (`Gio.File`, `Gio.FileMonitor`, `Gio.File.trash`) invece di soluzioni esterne.
5. Le operazioni lunghe (scansioni, copie, calcoli) non devono bloccare l’interfaccia: eseguirle in un thread o con API asincrone di Gio e aggiornare la UI con `GLib.idle_add`.
6. Mantenere il codice semplice, stabile e mantenibile. Un file principale è accettabile per tool piccoli; oltre le 1.500 righe circa, dividere in moduli.
7. La versione dei tool deve essere identica alla versione di RuscaLinux (vedi sezione 8).
8. **Eccezione: RuscaPinball** è un gioco e usa pygame (`python3-pygame`, in Debian Stable) al posto di GTK e libadwaita (sezione 1.5).

---

## 🧭 3. LINEE GUIDA D’INTERFACCIA (STILE GNOME)

Obiettivo: ogni tool deve sembrare un’applicazione GNOME nativa, pulita e professionale, coerente con le app di sistema (File, Impostazioni, Testo). Riferimento ufficiale: GNOME Human Interface Guidelines (developer.gnome.org/hig).

### 3.1 Principi

1. **Semplicità**: una finestra, uno scopo. Mostrare solo le azioni utili nel contesto corrente.
2. **Coerenza**: usare i widget standard di libadwaita invece di ricrearli. Niente widget disegnati a mano se esiste l’equivalente.
3. **Sobrietà**: superfici piatte, niente ombre o bordi decorativi aggiunti, niente gradienti dietro al testo (vedi sezione 4.3).
4. **Rispetto delle preferenze di sistema**: modalità chiara/scura, contrasto elevato, dimensione del testo, animazioni ridotte, lingua.

### 3.2 Struttura della finestra

Ogni tool usa questa struttura di base:

```text
Adw.ApplicationWindow
└── Adw.ToolbarView
    ├── top: Adw.HeaderBar
    │   ├── start: azioni principali (es. “Apri”, “Aggiungi”)
    │   ├── title: Adw.WindowTitle (titolo + eventuale sottotitolo)
    │   └── end: menu principale (icona open-menu-symbolic)
    └── content: contenuto (spesso dentro Adw.Clamp)
```

Regole:

1. Niente barra dei menu classica (File, Modifica, …). Le azioni secondarie vanno nel **menu principale** a destra.
2. Il menu principale contiene, in quest’ordine: azioni specifiche del tool, separatore, “Preferenze” (se il tool ne ha), “Scorciatoie da tastiera”, “Informazioni su NomeTool”.
3. Al massimo 3–4 pulsanti nella barra del titolo. I pulsanti nella barra usano icone simboliche con tooltip; un solo pulsante può essere testuale ed evidenziato (`suggested-action`).
4. Per tool con navigazione a più sezioni usare `Adw.NavigationSplitView` (barra laterale + contenuto) o `Adw.ViewStack` con `Adw.ViewSwitcher`.
5. Le preferenze usano `Adw.PreferencesDialog` con `Adw.PreferencesPage` e `Adw.PreferencesGroup`.

### 3.3 Componenti da usare

| Esigenza | Widget libadwaita / GTK |
|---|---|
| Finestra principale | `Adw.ApplicationWindow` + `Adw.ToolbarView` |
| Barra del titolo | `Adw.HeaderBar` + `Adw.WindowTitle` |
| Liste e impostazioni | `Gtk.ListBox` con classe `boxed-list` + `Adw.ActionRow`, `Adw.SwitchRow`, `Adw.ComboRow`, `Adw.EntryRow`, `Adw.SpinRow`, `Adw.ExpanderRow` |
| Stato vuoto / benvenuto / errore | `Adw.StatusPage` (icona, titolo, descrizione, pulsante) |
| Notifica non bloccante (es. “File salvato”) | `Adw.Toast` in `Adw.ToastOverlay`, con “Annulla” se l’azione è reversibile |
| Conferma o domanda | `Adw.AlertDialog` |
| Avviso persistente nella finestra | `Adw.Banner` |
| Attesa | `Adw.Spinner` (attese brevi) o `Gtk.ProgressBar` (avanzamento misurabile) |
| Gruppo di opzioni esclusive | `Adw.ToggleGroup` |
| Contenuto centrato e leggibile | `Adw.Clamp` (larghezza massima 600–800 px) |
| Adattamento a finestre strette | `Adw.Breakpoint` |
| Informazioni sull’app | Finestra “Informazioni” comune (sezione 3.10) |
| Scelta file | `Gtk.FileDialog` (funziona anche tramite portale) |

### 3.4 Layout e spaziature

1. Usare multipli di 6 px: 6, 12, 18, 24, 36.
2. Margini del contenuto: 12 px su finestre strette, 24 px su finestre larghe.
3. Spazio tra gruppi di righe: 24 px (già gestito da `Adw.PreferencesGroup`).
4. Raggi degli angoli: lasciare quelli di libadwaita; per elementi personalizzati usare 6 px (piccoli), 12 px (card).
5. La finestra deve funzionare fino a **360 × 294 px**. Sotto i 600 px di larghezza la barra laterale si comprime (via `Adw.Breakpoint`).
6. Allineare i controlli alla griglia; niente posizionamenti assoluti.

### 3.5 Tipografia

1. Usare il carattere di sistema (Adwaita Sans in GNOME 48). Non impostare famiglie o dimensioni in pixel nel codice.
2. Usare le classi di stile di libadwaita:

| Uso | Classe |
|---|---|
| Titolo grande di una pagina | `title-1` / `title-2` |
| Intestazione di sezione | `heading` |
| Testo secondario | `dim-label` |
| Didascalie, note | `caption` |
| Numeri allineati | `numeric` |
| Codice, percorsi | `monospace` |

3. I caratteri del marchio (Syne, DM Sans) restano riservati a sito, logo e materiale grafico, non all’interfaccia delle applicazioni.

### 3.6 Icone

1. Icone dell’interfaccia: solo icone **simboliche** del tema di sistema (`*-symbolic`), così seguono colore, tema scuro e contrasto elevato.
2. Ogni pulsante con sola icona deve avere un tooltip e un’etichetta accessibile.
3. Icona dell’applicazione: SVG scalabile secondo le GNOME App Icon Guidelines, installata in `/usr/share/icons/hicolor/scalable/apps/org.ruscalinux.RuscaFoo.svg`, più la variante simbolica in `hicolor/symbolic/apps/org.ruscalinux.RuscaFoo-symbolic.svg`. Le icone dei tool usano la palette RuscaLinux (sezione 4.1) e sono coerenti con il tema Adwaita-Prugna.

### 3.7 Testi e tono

1. Frasi brevi, dirette, rivolte all’utente con il “tu” implicito o forme impersonali; niente gergo tecnico se non necessario.
2. Italiano: maiuscola solo all’inizio (“Svuota cestino”, non “Svuota Cestino”). Inglese: Header Capitalization per titoli e pulsanti (“Empty Trash”), sentence case per descrizioni e caselle.
3. I pulsanti descrivono l’azione con un verbo (“Elimina”, “Installa”), non “Sì/No/OK”.
4. Le azioni che aprono un dialogo o chiedono altri dati terminano con i puntini di sospensione “…” (es. “Apri…”).
5. Messaggi d’errore: cosa è successo, perché (se noto), cosa può fare l’utente.
6. Usare i caratteri tipografici corretti: “…”, virgolette tipografiche, “×” per le dimensioni.

### 3.8 Comportamento e feedback

1. Le azioni distruttive chiedono conferma con `Adw.AlertDialog`: la risposta distruttiva usa lo stile `destructive`, quella predefinita è “Annulla”.
2. Quando possibile, preferire l’annullabilità alla conferma: spostare nel cestino (`Gio.File.trash`) e offrire “Annulla” in un `Adw.Toast`.
3. Ogni operazione oltre 1 secondo mostra un indicatore di attesa; oltre 5 secondi mostra l’avanzamento e permette di annullare.
4. Gli stati vuoti non sono mai una finestra bianca: usare `Adw.StatusPage` con un’azione per iniziare.
5. La finestra ricorda dimensione e stato (massimizzata) tra un avvio e l’altro, salvandoli in locale (`~/.config/ruscafoo/`).

### 3.9 Scorciatoie da tastiera standard

| Scorciatoia | Azione |
|---|---|
| Ctrl+Q | Esci |
| Ctrl+W | Chiudi finestra |
| Ctrl+, | Preferenze |
| Ctrl+? | Scorciatoie da tastiera |
| F10 | Menu principale |
| Ctrl+N / Ctrl+O | Nuovo / Apri (dove applicabile) |
| Ctrl+S / Ctrl+Shift+S | Salva / Salva come (dove applicabile) |
| Ctrl+F | Cerca (dove applicabile) |
| Ctrl+Z / Ctrl+Shift+Z | Annulla / Ripeti (dove applicabile) |
| Ctrl++ / Ctrl+− / Ctrl+0 | Testo più grande / più piccolo / dimensione di sistema (nei tool che mostrano testi lunghi: conversazioni, documenti) |
| Ctrl+B / Ctrl+I | Grassetto / corsivo (negli editor: RuscaMark, RuscaWriter) |
| Ctrl+2 / Ctrl+3 | Sezione / sottosezione (RuscaWriter) |

Tutte le funzioni devono essere raggiungibili da tastiera, con ordine di tabulazione logico e focus sempre visibile.

### 3.10 Finestra “Informazioni”

Tutti i tool usano la stessa finestra “Informazioni”, costruita dalla funzione comune `show_about_dialog()` (identica nei tool, come `style.css`). È un `Adw.Dialog` con una pagina principale, in cui descrizione e collegamenti si vedono subito, e una seconda pagina per la nota di sviluppo, che si apre dalla sua riga (`Adw.NavigationView`, con il pulsante indietro nella barra in alto).

Si usa al posto di `Adw.AboutDialog` perché in quest’ultimo la descrizione finisce nella sottopagina “Dettagli”, dove l’utente non la vede.

La nota di sviluppo è una riga dell’elenco, come la licenza, e non un blocco di testo sempre visibile: resta a un clic, ma la finestra parla prima di tutto del programma. Nella sua pagina il testo ha il colore pieno (non `dim-label`, che sul fondo chiaro scende a circa 4:1, sotto il minimo della sezione 3.11).

Contenuto, dall’alto in basso:

| Elemento | Valore |
|---|---|
| Icona | Icona dell’app dal tema (App ID), 128 px |
| Nome | Nome del tool, classe `title-1` |
| Versione | `APP_VERSION`, classe `dim-label` |
| Descrizione | Descrizione breve tradotta |
| Riga “Sito web” | www.ruscalinux.org |
| Riga “Supporto” | info@ruscalinux.org |
| Riga “Licenza” | GNU GPL 3.0 (apre il testo della licenza) |
| Riga “Nota di sviluppo” | Ultima riga dell’elenco, con la freccia `go-next-symbolic`: apre la pagina con la nota IA (sezione 12), tradotta |
| Riga finale | © 2026 Nunzio Curcuruto, classi `caption` e `dim-label` |

Chiavi di traduzione usate: `about_website`, `about_support`, `about_license`, `dev_note_title`, `ai_note`, più la descrizione del tool.

Se un tool include componenti esterni (sezione 6), si aggiunge una riga “Componenti esterni” che apre l’elenco con nome, versione e licenza.

### 3.11 Accessibilità

1. Contrasto minimo **4,5:1** per il testo normale e **3:1** per testo grande e bordi di controlli (WCAG 2.1 AA). La palette della sezione 4 rispetta già questi valori.
2. Mai trasmettere informazione solo con il colore: aggiungere icona o testo.
3. Ogni elemento interattivo ha un’etichetta accessibile (`update_property` con `Gtk.AccessibleProperty.LABEL` se non ha testo visibile).
4. Con **contrasto elevato** attivo, il foglio di stile RuscaLinux non deve aggiungere effetti: libadwaita gestisce bordi e colori.
5. Rispettare “Animazioni ridotte”: niente animazioni personalizzate oltre a quelle di libadwaita.
   Eccezione: il volto di RuscaLLisse (sezione 1.7.8), che è il contenuto del programma e con «Animazioni ridotte» si limita a espressioni, ciglia e bocca.
6. Verificare l’interfaccia con dimensione del testo grande (Impostazioni → Accessibilità) e con il lettore Orca.

---

## 🎨 4. TEMA RUSCALINUX (PRUGNA SCURO E ROSA CHIARO)

Il tema si applica **ridefinendo i colori di libadwaita**, non disegnando widget propri. In questo modo i tool restano GNOME nativi e cambiano solo carattere cromatico. I colori seguono la modalità chiara/scura di sistema.

### 4.1 Palette ufficiale

| Nome | Esadecimale | Uso |
|---|---|---|
| Prugna 900 (Prugna scuro) | `#2d0a1d` | Testo in modalità chiara, sfondo finestra in modalità scura, colore del marchio |
| Prugna 850 | `#230716` | Sfondo delle viste in modalità scura |
| Prugna 800 | `#3a1028` | Barra del titolo, dialoghi, popover in modalità scura |
| Prugna 750 | `#40132c` | Card e righe in modalità scura |
| Prugna 600 | `#7a2357` | Accento in modalità chiara (pulsanti evidenziati, selezioni, link) |
| Prugna 500 | `#8a2b5f` | Inizio del gradiente “hero” |
| Rosa 300 | `#f2a7c8` | Accento in modalità scura |
| Rosa 250 | `#f5b8d3` | Testo d’accento e link in modalità scura |
| Rosa 200 (Rosa chiaro) | `#f8d7e6` | Inizio del gradiente decorativo del marchio |
| Rosa 100 | `#f6e4ec` | Barra del titolo e barra laterale in modalità chiara |
| Rosa 50 | `#fbf4f7` | Sfondo finestra in modalità chiara |
| Crema | `#fff7f0` | Testo in modalità scura e sui gradienti |
| Bianco | `#ffffff` | Viste e card in modalità chiara, testo sui pulsanti d’accento |

I colori semantici (errore, avviso, successo) restano quelli di libadwaita: non vanno ridefiniti.

### 4.2 Contrasti verificati (WCAG)

| Combinazione | Rapporto |
|---|---|
| Testo `#2d0a1d` su finestra `#fbf4f7` | 16,5:1 |
| Testo `#2d0a1d` su barra `#f6e4ec` | 14,7:1 |
| Testo bianco su accento `#7a2357` | 9,5:1 |
| Accento `#7a2357` come testo su `#fbf4f7` | 8,8:1 |
| Testo `#fff7f0` su finestra `#2d0a1d` | 16,9:1 |
| Testo `#fff7f0` su card `#40132c` | 14,7:1 |
| Testo `#2d0a1d` su accento `#f2a7c8` | 9,5:1 |
| Accento `#f5b8d3` come testo su `#2d0a1d` | 10,8:1 |
| Testo `#fff7f0` sul punto più chiaro del gradiente hero `#8a2b5f` | 7,7:1 |

Ogni nuovo colore aggiunto deve essere verificato allo stesso modo prima dell’uso.

### 4.3 Regole sul gradiente

Il gradiente rosa chiaro → prugna scuro è il segno distintivo di RuscaLinux, ma un gradiente dietro al testo rende impossibile garantire il contrasto in ogni punto. Per questo:

1. Il **fondo della finestra è piatto** (colori della sezione 4.4), come in tutte le app GNOME.
2. Il **gradiente del marchio** (`#f8d7e6` → `#2d0a1d`) è solo decorativo: non può contenere testo. Usi ammessi: icona dell’app, illustrazioni, una sottile fascia decorativa.
3. Il **gradiente hero** (`#8a2b5f` → `#2d0a1d`) può contenere testo color crema. Usi ammessi: pagina di benvenuto o stato vuoto principale (`Adw.StatusPage` con classe `rusca-hero`), al massimo un’area per finestra.
4. Mai gradienti su pulsanti, righe di lista, barre del titolo o barre laterali.

### 4.4 Mappatura sui colori di libadwaita

| Variabile libadwaita | Modalità chiara | Modalità scura |
|---|---|---|
| `--window-bg-color` | `#fbf4f7` | `#2d0a1d` |
| `--window-fg-color` | `#2d0a1d` | `#fff7f0` |
| `--view-bg-color` | `#ffffff` | `#230716` |
| `--view-fg-color` | `#2d0a1d` | `#fff7f0` |
| `--headerbar-bg-color` | `#f6e4ec` | `#3a1028` |
| `--headerbar-fg-color` | `#2d0a1d` | `#fff7f0` |
| `--sidebar-bg-color` | `#f6e4ec` | `#260818` |
| `--sidebar-fg-color` | `#2d0a1d` | `#fff7f0` |
| `--card-bg-color` | `#ffffff` | `#40132c` |
| `--card-fg-color` | `#2d0a1d` | `#fff7f0` |
| `--dialog-bg-color` / `--popover-bg-color` | `#fbf4f7` / `#ffffff` | `#3a1028` |
| `--dialog-fg-color` / `--popover-fg-color` | `#2d0a1d` | `#fff7f0` |
| `--accent-bg-color` | `#7a2357` | `#f2a7c8` |
| `--accent-fg-color` | `#ffffff` | `#2d0a1d` |
| `--accent-color` | `#7a2357` | `#f5b8d3` |

Nota: da GNOME 47 l’utente può scegliere un colore d’accento di sistema. Le RuscaLinux OS Apps lo sostituiscono intenzionalmente con l’accento prugna/rosa per coerenza con l’identità della distribuzione.

### 4.5 Foglio di stile di riferimento

Ogni tool include lo stesso file `style.css`, installato in `/usr/share/ruscafoo/style.css`. Il file è identico in tutti i tool: le modifiche si fanno una volta e si copiano ovunque.

La palette chiara e quella scura sono legate alle classi `rusca-light` e `rusca-dark`, che il programma mette sulle proprie finestre seguendo `Adw.StyleManager:dark` (sezione 4.6). Non si usa `@media (prefers-color-scheme: dark)`: il modo in cui GTK valuta questa condizione per i fogli di stile delle applicazioni cambia tra GTK 4.18 (trixie) e GTK 4.20 e successivi, e nelle versioni recenti la palette scura non verrebbe applicata. Con le classi il risultato è identico su tutte le versioni.

```css
/* RuscaLinux OS Apps — style.css — 1.99.3 — GPL-3.0
 * Tema comune Prugna/Rosa. File identico in tutti i tool: si modifica una
 * volta sola e si copia. Ridefinisce solo i colori di libadwaita (>= 1.6),
 * non la forma dei widget. Contrasti verificati: vedi le specifiche, sez. 4.2.
 *
 * Le classi .rusca-light / .rusca-dark sono messe sulle finestre dal
 * programma, seguendo Adw.StyleManager:dark. Non si usa
 * @media (prefers-color-scheme) perché il modo in cui GTK la valuta per i
 * fogli di stile delle applicazioni cambia tra GTK 4.18 (trixie) e 4.20+:
 * con le classi il risultato è lo stesso su tutte le versioni.
 */

.rusca-light {
  --window-bg-color: #fbf4f7;
  --window-fg-color: #2d0a1d;
  --view-bg-color: #ffffff;
  --view-fg-color: #2d0a1d;
  --headerbar-bg-color: #f6e4ec;
  --headerbar-fg-color: #2d0a1d;
  --sidebar-bg-color: #f6e4ec;
  --sidebar-fg-color: #2d0a1d;
  --card-bg-color: #ffffff;
  --card-fg-color: #2d0a1d;
  --dialog-bg-color: #fbf4f7;
  --dialog-fg-color: #2d0a1d;
  --popover-bg-color: #ffffff;
  --popover-fg-color: #2d0a1d;
  --accent-bg-color: #7a2357;
  --accent-fg-color: #ffffff;
  --accent-color: #7a2357;
}

.rusca-dark {
  --window-bg-color: #2d0a1d;
  --window-fg-color: #fff7f0;
  --view-bg-color: #230716;
  --view-fg-color: #fff7f0;
  --headerbar-bg-color: #3a1028;
  --headerbar-fg-color: #fff7f0;
  --sidebar-bg-color: #260818;
  --sidebar-fg-color: #fff7f0;
  --card-bg-color: #40132c;
  --card-fg-color: #fff7f0;
  --dialog-bg-color: #3a1028;
  --dialog-fg-color: #fff7f0;
  --popover-bg-color: #3a1028;
  --popover-fg-color: #fff7f0;
  --accent-bg-color: #f2a7c8;
  --accent-fg-color: #2d0a1d;
  --accent-color: #f5b8d3;
}

/* Area di benvenuto con gradiente hero: testo crema, contrasto >= 7,7:1 */
.rusca-hero {
  background-image: linear-gradient(135deg, #8a2b5f 0%, #2d0a1d 100%);
  color: #fff7f0;
  border-radius: 12px;
  padding: 18px 24px;
}

/* Fascia decorativa del marchio: NON inserire testo */
.rusca-brand-band {
  background-image: linear-gradient(90deg, #f8d7e6 0%, #2d0a1d 100%);
  min-height: 4px;
}
```

Regole:

1. Non aggiungere regole CSS che cambiano forma, dimensione o bordi dei widget standard.
2. Le uniche classi personalizzate ammesse sono quelle con prefisso `rusca-`.
3. La modalità chiara/scura segue il sistema per impostazione predefinita. Ogni tool offre nelle preferenze la riga “Tema” (`Adw.ComboRow`: “Segui il sistema”, “Chiaro”, “Scuro”), salvata in `~/.config/ruscafoo/`; la scelta si applica con `Adw.StyleManager.set_color_scheme()` all’avvio, prima di mostrare la finestra. Le classi `rusca-light`/`rusca-dark` seguono `Adw.StyleManager:dark`, quindi valgono anche per il tema scelto.
4. Se `style.css` manca, il programma deve partire comunque, con i colori standard di GNOME.

### 4.6 Caricamento del tema e struttura minima dell’app

```python
import os
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, Gtk

APP_ID = "org.ruscalinux.RuscaFoo"
APP_VERSION = "1.99.3"
BASE_DIR = os.path.dirname(os.path.realpath(__file__))   # /usr/share/ruscafoo
STYLE_SRC = os.path.join(BASE_DIR, "style.css")


class RuscaFooApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_startup(self):
        Adw.Application.do_startup(self)
        # Tema comune RuscaLinux; se manca, restano i colori di GNOME.
        if os.path.isfile(STYLE_SRC):
            provider = Gtk.CssProvider()
            provider.load_from_path(STYLE_SRC)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(), provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        # Palette chiara/scura secondo il sistema (sezione 4.5).
        style = Adw.StyleManager.get_default()
        style.connect("notify::dark", lambda *_a: self.update_theme())
        self.connect("window-added", lambda *_a: self.update_theme())
        # Scorciatoie standard (sezione 3.9).
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_a: [w.close() for w in self.get_windows()])
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("window.close", ["<Control>w"])
        self.set_accels_for_action("win.shortcuts", ["<Control>question"])

    def update_theme(self):
        dark = Adw.StyleManager.get_default().get_dark()
        for window in self.get_windows():
            window.remove_css_class("rusca-light" if dark else "rusca-dark")
            window.add_css_class("rusca-dark" if dark else "rusca-light")

    def do_activate(self):
        win = self.props.active_window or MainWindow(application=self)
        win.present()
```

Note:

1. “Esci” chiude le finestre invece di terminare subito: così un’operazione in corso può rifiutare la chiusura (`close-request`).
2. Se la lingua dell’interfaccia è l’arabo, chiamare `Gtk.Widget.set_default_direction(Gtk.TextDirection.RTL)` all’avvio: GTK sceglie la direzione dalla propria lingua, che può non coincidere con quella scelta dal programma.
3. Finché Debian Stable non avrà libadwaita 1.8 (`Adw.ShortcutsDialog`), la finestra “Scorciatoie da tastiera” è un `Adw.Dialog` con righe `Adw.ActionRow`; le combinazioni si mostrano con `Gtk.accelerator_get_label()`, che le traduce.

L’`application_id` passato ad `Adw.Application` deve coincidere con `StartupWMClass` del file `.desktop`, altrimenti GNOME non associa la finestra all’icona.

### 4.7 Regole di leggibilità (obbligatorie)

1. Niente testo chiaro su sfondo chiaro.
2. Niente testo scuro su sfondo scuro.
3. Niente testo su gradiente, tranne il gradiente hero con testo crema.
4. Le etichette devono essere sempre leggibili in modalità chiara, scura e a contrasto elevato.
5. Gli stati dei controlli (passaggio del mouse, attivo, disabilitato, selezionato, focus) sono gestiti da libadwaita e non vanno ridefiniti.
6. L’accessibilità visiva ha priorità sull’estetica.

---

## 🗂️ 5. STRUTTURA DEL PROGETTO E INTEGRAZIONE NEL DESKTOP

### 5.1 Struttura di un tool

Ogni tool è una cartella dentro `apps/`, nella radice del repository (durante lo sviluppo della 1.99.3 la cartella si chiamava `tools/`).

```text
apps/ruscafoo/
├── ruscafoo.py                         # programma (o cartella ruscafoo/ con moduli)
├── style.css                           # tema RuscaLinux (sezione 4.5)
├── ruscafoo.svg                        # icona dell’applicazione
├── ruscafoo-symbolic.svg               # icona simbolica
├── lang/                               # traduzioni JSON (sezione 9)
│   ├── en.json
│   ├── it.json
│   └── …
├── docs/                               # manuali MANUAL_it.md, MANUAL_en.md
├── make-deb.sh                         # genera anche .desktop e metainfo
└── build-deb/                          # generata, non contiene sorgenti
```

File `.desktop` e metainfo sono generati da `make-deb.sh`, che prende i testi tradotti (descrizione, parole chiave) dai file di `lang/`: ogni testo ha una sola fonte.

### 5.2 Percorsi di installazione

| Elemento | Percorso |
|---|---|
| Comando | `/usr/bin/ruscafoo` |
| Programma, dati, traduzioni, CSS | `/usr/share/ruscafoo/` (il comando è un collegamento simbolico) |
| File desktop | `/usr/share/applications/org.ruscalinux.RuscaFoo.desktop` |
| Metainfo | `/usr/share/metainfo/org.ruscalinux.RuscaFoo.metainfo.xml` |
| Icona | `/usr/share/icons/hicolor/scalable/apps/org.ruscalinux.RuscaFoo.svg` |
| Icona simbolica | `/usr/share/icons/hicolor/symbolic/apps/org.ruscalinux.RuscaFoo-symbolic.svg` |
| Configurazione utente | `~/.config/ruscafoo/` |
| Dati utente | `~/.local/share/ruscafoo/` |

### 5.3 File .desktop

```ini
[Desktop Entry]
Type=Application
Name=RuscaFoo
Comment=Short description in English
Comment[it]=Breve descrizione in italiano
Exec=ruscafoo %U
Icon=org.ruscalinux.RuscaFoo
Terminal=false
Categories=GNOME;GTK;Utility;X-RuscaLinux-Apps;
Keywords=keyword;another;
Keywords[it]=parola;altra;
StartupNotify=true
StartupWMClass=org.ruscalinux.RuscaFoo
```

`Comment` e `Keywords` vanno tradotti in tutte le lingue della sezione 9 (`Comment[xx]=`), presi dai file di `lang/`. Il file va validato con `desktop-file-validate`.

Fra le `Categories` di ogni tool c’è sempre **`X-RuscaLinux-Apps`**: è la categoria della cartella **RuscaLinux Apps** della griglia delle applicazioni di GNOME, che raccoglie tutti i tool. La cartella la crea, una volta per utente e dopo le cartelle di GNOME, lo script `/usr/lib/ruscalinux/ruscalinux-apps-folder` della ISO (scritto da `steps/30-custom.sh`, avviato da `/etc/xdg/autostart/`): un elenco di cartelle predefinito con dconf impedirebbe a GNOME Shell 48 di creare le sue (Sistema, Utilità). Un tool nuovo entra nella cartella da solo, grazie alla categoria. GNOME Shell salva la posizione di ogni icona (`org.gnome.shell app-picker-layout`) e non la ricompatta: quando un aggiornamento toglie, rinomina o sposta in una cartella delle applicazioni restano dei buchi, e quelle nuove finiscono in una pagina in più. Succede anche al primo accesso, quando i tool entrano nella cartella: azzerare la disposizione non basta, perché GNOME ha già le icone in memoria e non le ridispone. Per questo `/usr/lib/ruscalinux/ruscalinux-app-grid` (sempre da `steps/30-custom.sh`, avviato a ogni accesso, 25 e 90 secondi dopo) scrive una disposizione completa e compatta: le voci salvate nel loro ordine, senza quelle che non esistono più, che stanno in una cartella o nel dash, poi le altre in ordine alfabetico, a pagine da 24 (tutte le griglie di GNOME Shell 48 ne tengono 24). Scrive solo se cambia qualcosa. I componenti senza interfaccia (ruscallama-engine, ruscawhisper-engine, ruscadiffusion-engine, ruscavosk-engine, ruscapiper-engine) non hanno file `.desktop`. L’identificativo della cartella per dconf è `RuscaLinux-Apps` (con il trattino: dconf non ammette spazi). Durante lo sviluppo della 1.99.3 la cartella si chiamava «RuscaLinux-Tools», con la categoria `X-RuscaLinux-Tools`.

### 5.4 Metainfo AppStream

Serve perché il tool compaia correttamente in GNOME Software. Contenuto minimo:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>org.ruscalinux.RuscaFoo</id>
  <name>RuscaFoo</name>
  <summary>Short description</summary>
  <metadata_license>CC0-1.0</metadata_license>
  <project_license>GPL-3.0-or-later</project_license>
  <developer id="org.ruscalinux">
    <name>Nunzio Curcuruto</name>
  </developer>
  <description>
    <p>Longer description.</p>
  </description>
  <launchable type="desktop-id">org.ruscalinux.RuscaFoo.desktop</launchable>
  <url type="homepage">https://www.ruscalinux.org</url>
  <content_rating type="oars-1.1"/>
  <releases>
    <release version="1.99.3" date="2026-01-01"/>
  </releases>
</component>
```

Il `<launchable>` deve nominare esattamente il file `.desktop`. Validare con `appstreamcli validate`. Nota: verificare se `project_license` deve essere `GPL-3.0-only` o `GPL-3.0-or-later` in base all’intestazione dei sorgenti.

---

## 📜 6. LICENZA E COMPONENTI ESTERNI

Licenza principale del codice: GPL-3.0 — https://www.gnu.org/licenses/gpl-3.0.html

Regole:

1. Non usare licenze incompatibili con GPL-3.0.
2. Ogni componente esterno (ad esempio codice vendor) conserva la propria licenza originale.
3. Ogni componente esterno incluso va indicato con nome, versione, licenza e percorso nel progetto, sia nella documentazione del tool sia nella finestra “Informazioni” (sezione 3.10, gruppo “Componenti esterni”).
4. Rispettare legalmente tutte le licenze dei componenti usati.
5. Il nome RuscaLinux, il logo e l’emblema non sono coperti dalla GPL: vedi `TRADEMARK.md` del repository.
6. Il codice esterno incluso sta sempre in **file separati**, con la provenienza e il testo della sua licenza in testa, e il file `copyright` del pacchetto lo dichiara con un blocco `Files:` proprio. Nessun file mescola codice di RuscaLinux e codice esterno: chi apre un file sa subito di chi è e con quale licenza.

Componenti esterni in uso:

| Componente | Versione | Licenza | Dove | Usato da |
|---|---|---|---|---|
| EB Garamond e Courier Prime (caratteri tipografici) | inclusi nei sorgenti | SIL Open Font License 1.1 | `apps/ruscawriter/assets/`, installati in `/usr/share/ruscawriter/assets/` con il testo della licenza | RuscaWriter |
| llama.cpp (con ggml e le librerie che include: nlohmann/json e cpp-httplib MIT, xxHash BSD-2-Clause, stb, miniaudio, sha1 e sha256 di pubblico dominio) | ultima release stabile al momento della build (1.99.2: 0.9.0; 1.99.3: 1.0.0), scritta nella descrizione del pacchetto e in `/usr/share/doc/ruscallama-engine/README.md.gz` | MIT | Compilato nel pacchetto `ruscallama-engine`, in `/usr/lib/ruscallama-engine/` | RuscaLLama, RuscaTranslator, RuscaNarrator (`llama-tts`) |
| whisper.cpp (con ggml e le librerie compilate nei programmi impacchettati: sgemm di llamafile, MIT; miniaudio, pubblico dominio o MIT-0; stb_vorbis, pubblico dominio o MIT) | ultima release stabile al momento della build (1.99.3: 1.9.5), scritta nella descrizione del pacchetto e in `/usr/share/doc/ruscawhisper-engine/README.md.gz` | MIT | Compilato nel pacchetto `ruscawhisper-engine`, in `/usr/lib/ruscawhisper-engine/` | RuscaTranscriber |
| stable-diffusion.cpp (con la sua copia di ggml, leejet/ggml, e le librerie compilate in `sd-cli`: nlohmann/json, miniz e sgemm di llamafile, MIT; zip di kuba--, Unlicense; stb, pubblico dominio o MIT; darts-clone, BSD-3-Clause; Oniguruma, BSD-2-Clause; utf8proc, MIT e licenza dei dati Unicode) | ultima release al momento della build (tag `master-<numero>-<commit>`; 1.99.3: master-1106-532d2c1), scritta nella descrizione del pacchetto e in `/usr/share/doc/ruscadiffusion-engine/README.md.gz` | MIT | Compilato nel pacchetto `ruscadiffusion-engine`, in `/usr/lib/ruscadiffusion-engine/` | RuscaLLama (viste Immagini e Video) |
| Vosk (vosk-api), con Kaldi (ramo `vosk`) e OpenFst di Alpha Cephei compilati in `libvosk.so`; OpenBLAS di Debian collegato dinamicamente | versioni fissate in `make-deb.sh` (Vosk 0.3.50, Kaldi `bc5baf142316`, OpenFst `18e94e63870e`), scritte nella descrizione del pacchetto e in `/usr/share/doc/ruscavosk-engine/README.md.gz` | Apache 2.0 (Vosk, Kaldi, OpenFst); OpenBLAS (BSD-3-Clause) è un pacchetto di Debian | Compilato nel pacchetto `ruscavosk-engine`, in `/usr/lib/ruscavosk-engine/` | RuscaLLisse |
| Piper (piper1-gpl), con espeak-ng | ultima release stabile al momento della build, scritta nella descrizione del pacchetto e in `/usr/share/doc/ruscapiper-engine/README.md.gz` | GPL-3.0 | Compilato nel pacchetto `ruscapiper-engine`, in `/usr/lib/ruscapiper-engine/` | RuscaLLisse |
| Regola dell’evidenziato, porting del plugin markdown-it-mark (© Vitaly Puzrin e Alex Kocharin) con la struttura della regola del barrato di markdown-it-py (© ExecutableBookProject) | — | MIT (Expat) | `markdown_it_mark.py`, file a sé accanto a `rusca_markdown.py`; dichiarato nel file `copyright` del pacchetto, nella finestra Informazioni e nei manuali | RuscaLLama, RuscaMark, RuscaWriter, RuscaTranslator, RuscaNarrator |
| Esempi della specifica CommonMark (© John MacFarlane) | 0.30 | CC BY-SA 4.0 | `tests/data/commonmark-0.30-spec.json`, con `README.md`; solo per i test, non installati da nessun pacchetto | Test di `rusca_markdown.py` |

markdown-it-py, mdit-py-plugins e linkify-it-py (licenza MIT) non sono inclusi: sono dipendenze dei pacchetti, installate da Debian.

I file `copyright` di `ruscallama-engine`, `ruscawhisper-engine` e `ruscadiffusion-engine` riportano tutte queste licenze; solo gli script di costruzione e i profili AppArmor sono di RuscaLinux (GPL-3.0).

FFmpeg non è incluso: RuscaTranscriber e RuscaNarrator usano il comando `ffmpeg` del pacchetto Debian, che è una loro dipendenza.

ONNX Runtime non è incluso: ruscapiper-engine usa la libreria del pacchetto Debian (`libonnxruntime1.21` in trixie, licenza MIT), che è una sua dipendenza. Lo stesso vale per `pw-record` e `pw-play` (`pipewire-bin`), che RuscaLLisse usa come comandi. L’espeak-ng di Piper è compilato dentro `libpiper.so`: è il commit fissato da Piper (sezione 1.8), con i suoi dati in `/usr/lib/ruscapiper-engine/espeak-ng-data/`.

---

## 📦 7. PACCHETTI DEBIAN

Ogni programma ha uno script `make-deb.sh` che:

1. si lancia dalla propria cartella, senza argomenti;
2. contiene la versione (`VER`), uguale a `VERSION` di `release.conf`;
3. crea la struttura del pacchetto e il deb nella sotto-cartella dedicata `build-deb/`, separata dai sorgenti;
4. scrive **un solo** file `.deb` e accanto il file `SHA256SUMS`;
5. produce un pacchetto conforme alla Debian Policy.

Nomi:

| Cosa | Valore |
|---|---|
| Nome del pacchetto Debian (campo `Package`) | `ruscafoo` |
| Nome del file | `ruscafoo-ruscalinux_<versione>_all.deb` |

Il suffisso `ruscalinux` nel nome del file indica che il pacchetto appartiene alla distribuzione RuscaLinux. L’architettura è `all` perché i tool sono in Python puro e non contengono codice compilato.

**Eccezione: ruscapinball.** È un gioco: `Section: games`, il comando è `/usr/games/ruscapinball` (Debian Policy, 11.11) e la pagina di manuale sta nella sezione 6. Dipende da `python3 (>= 3.10)` e `python3-pygame (>= 2.1)`, raccomanda `fonts-dejavu-core`. Le `Categories` del `.desktop` sono `Game;ArcadeGame;X-RuscaLinux-Apps;`: il gioco sta sia fra i giochi sia nella cartella RuscaLinux Apps.

**Eccezione: ruscallama-engine.** È codice compilato, quindi:

1. architettura `amd64`; file `ruscallama-engine-ruscalinux_<versione>_amd64.deb`;
2. versione del pacchetto uguale a quella di RuscaLinux; la versione di llama.cpp è scritta nella descrizione e in `/usr/share/doc/ruscallama-engine/README.md.gz`;
3. si costruisce l’ultima release stabile di llama.cpp (tag `vX.Y.Z` indicato da GitHub come “Latest”), trovata da `ultima-versione.sh`; `RUSCALLAMA_LLAMA_VERSION` ne fissa una. Il sorgente si scarica da GitHub solo durante la costruzione; il commit dell’archivio deve coincidere con quello del tag, e l’impronta SHA-256 si registra in `checksums/` alla prima costruzione di ogni versione (il file va aggiunto al repository) e si confronta nelle successive;
4. al posto della prova manuale, la build controlla che `llama-server` accetti tutte le opzioni usate da RuscaLLama e RuscaTranslator e che nessuna libreria nuova in `vendor/` manchi dal file `copyright`; una release uscita da meno di 14 giorni dà un avviso, e va provata con RuscaLLama, RuscaTranslator e RuscaNarrator (`llama-tts`) prima di pubblicare la ISO;
5. compilazione senza rete (`unshare -rn`), con `LLAMA_OPENSSL=OFF`, `LLAMA_BUILD_UI=OFF`, `LLAMA_USE_PREBUILT_UI=OFF` e `LLAMA_CONNECT=OFF`; la build si ferma se i binari usano OpenSSL o curl;
6. binari e librerie private in `/usr/lib/ruscallama-engine/` (non in `/opt`, che Debian riserva ad altro), con RUNPATH su quella cartella, senza simboli di debug e con i flag di sicurezza di `dpkg-buildflags`;
7. dipendenze calcolate con `dpkg-shlibdeps`;
8. compilazione tenuta in cache (`~/.cache/ruscalinux/ruscallama-engine/`): le build successive rifanno solo il pacchetto;
9. dipendenze di costruzione: `build-essential cmake pkg-config dpkg-dev wget git libvulkan-dev glslc spirv-headers`.

**Eccezione: ruscawhisper-engine.** È fatto come ruscallama-engine e segue gli stessi nove punti, con whisper.cpp al posto di llama.cpp: file `ruscawhisper-engine-ruscalinux_<versione>_amd64.deb`, variabile `RUSCAWHISPER_WHISPER_VERSION`, binari in `/usr/lib/ruscawhisper-engine/`, cache in `~/.cache/ruscalinux/ruscawhisper-engine/`, stesse dipendenze di costruzione. Cambiano tre cose:

1. si compilano solo `whisper-cli` e `whisper-bench`, con `WHISPER_BUILD_SERVER=OFF`, `WHISPER_CURL=OFF`, `WHISPER_SDL2=OFF` e `WHISPER_COMMON_FFMPEG=OFF`; la build si ferma se i binari usano OpenSSL o curl, o se tra i simboli che richiedono c’è una funzione per aprire connessioni (`socket`, `connect`, `bind`, `listen`, `accept`, `getaddrinfo`…);
2. whisper.cpp tiene le librerie di altri autori in `examples/`, non in `vendor/`: la build si ferma se in `examples/` compare un file che non è negli elenchi di `make-deb.sh`;
3. oltre a controllare che `whisper-cli` accetti le opzioni usate da RuscaTranscriber, la build gli fa trascrivere l’audio di prova del sorgente con il modello di prova (senza pesi) e controlla che scriva il JSON, e con il backend Vulkan controlla che ggml abbia ancora `GGML_VK_VISIBLE_DEVICES`, con cui RuscaTranscriber sceglie la scheda.

**Eccezione: ruscadiffusion-engine.** È fatto come ruscawhisper-engine, con stable-diffusion.cpp al posto di whisper.cpp: file `ruscadiffusion-engine-ruscalinux_<versione>_amd64.deb`, variabile `RUSCADIFFUSION_SD_VERSION` (il tag intero o solo il numero), binario in `/usr/lib/ruscadiffusion-engine/`, cache in `~/.cache/ruscalinux/ruscadiffusion-engine/`, stesse dipendenze di costruzione. Cambiano quattro cose:

1. stable-diffusion.cpp non ha versioni `X.Y.Z`: ogni release è un tag `master-<numero>-<commit>` e la più recente ha il numero più alto. Il sorgente sono **due archivi**: stable-diffusion.cpp e la sua copia di ggml (sottomodulo git, assente dagli archivi di GitHub). Il commit di ggml è quello registrato nel tag, letto con `git fetch --filter=blob:none`; il commit di ciascun archivio deve essere quello atteso, e il file di `checksums/` registra le impronte di tutti e due;
2. si compila solo `sd-cli`, con ggml dentro (`BUILD_SHARED_LIBS=OFF`), con `SD_RPC=OFF`, `GGML_RPC=OFF`, `SD_SERVER_BUILD_FRONTEND=OFF`, `SD_WEBP=OFF` e `SD_WEBM=OFF`; stessi controlli di rete sui simboli;
3. le librerie di altri autori stanno in `thirdparty/`: la build si ferma se compare un file che non è in `TERZI_DICHIARATI`;
4. il sorgente non ha un modello di prova: la build controlla che `sd-cli` dica la sua versione, elenchi le schede nel formato `nome<TAB>descrizione`, accetti le opzioni usate da RuscaLLama (`OPZIONI_USATE`, anche quelle dei video) e abbia il modo `vid_gen` con l’uscita `.avi`.

**Il pacchetto `ruscallisse`** aggiunge a `Depends`, oltre alle dipendenze comuni:

```text
Package: ruscallisse
Architecture: all
Depends: python3 (>= 3.10), python3-gi, python3-gi-cairo, gir1.2-gtk-4.0 (>= 4.18), gir1.2-adw-1 (>= 1.7),
 python3-markdown-it (>= 3.0), python3-mdit-py-plugins (>= 0.4), python3-linkify-it (>= 2.0),
 pipewire-bin, ruscallama-engine, ruscavosk-engine, ruscapiper-engine
```

`python3-gi-cairo` serve per disegnare il volto con Cairo. Tutte le dipendenze nuove (`python3-gi-cairo`, `pipewire-bin`, e per i motori `libonnxruntime1.21` e `libopenblas0-serial`) vanno anche nell’elenco dei pacchetti della ISO (`steps/20-packages.sh`): la macchina che installa RuscaLLisse può non avere la rete. Il comando `espeak-ng` non serve: RuscaLLisse non lo usa, e Piper ha il suo espeak-ng dentro `libpiper.so`.

**Eccezione: ruscavosk-engine.** È fatto come ruscawhisper-engine e segue gli stessi nove punti di ruscallama-engine: file `ruscavosk-engine-ruscalinux_<versione>_amd64.deb`, libreria in `/usr/lib/ruscavosk-engine/`, cache in `~/.cache/ruscalinux/ruscavosk-engine/`. Cambiano cinque cose:

1. Il sorgente sono **tre archivi a versioni fissate** in `make-deb.sh` (`VOSK_TAG`, `KALDI_COMMIT`, `OPENFST_COMMIT`): Vosk non fissa la revisione di Kaldi (la sua ricetta, `travis/Dockerfile.manylinux`, usa la cima del ramo `vosk`), quindi non c’è «ultima release» da cercare e non c’è `ultima-versione.sh`; le versioni si cambiano a mano, provando RuscaLLisse. Ogni archivio ha il suo commit atteso e la sua impronta in `checksums/`. OpenFst è quello di Alpha Cephei (Debian ha la 1.8.4, senza le loro correzioni); OpenBLAS è quello di Debian (`libopenblas-serial-dev`), e di LAPACK serve solo l’intestazione `lapacke.h` (`liblapacke-dev`): le funzioni LAPACK sono dentro OpenBLAS.
2. Si compila come la ricetta di Vosk: OpenFst (statico e condiviso, con `far`, `ngram` e `lookahead`, senza programmi), Kaldi `--shared --use-cuda=no --mathlib=OPENBLAS` solo per `online2` e `rnnlm`, con `-O3` invece di `-O1` (in più: niente `-g`, niente `-lgfortran`, nessun RPATH), poi `libvosk.so` con il Makefile di Vosk, Kaldi e OpenFst statici dentro. Prima di Kaldi si applica `patches/kaldi-lapack.patch`. Processi di compilazione: il minore fra i processori e la RAM in GB divisa per 2 (`RUSCAVOSK_JOBS`). Tempo di riferimento: circa 12 minuti su 2 processori. Stessi controlli di rete sui simboli di ruscawhisper-engine.
3. La build controlla che `libvosk.so` esporti le funzioni usate da RuscaLLisse (`SIMBOLI_VOSK`).
4. Il sorgente non ha un modello di prova: la build carica la libreria con `ctypes`, chiama `vosk_set_log_level()` e controlla che `vosk_model_new()` su una cartella inesistente restituisca NULL senza bloccarsi. Se trova un modello (`RUSCAVOSK_MODEL`, o il primo in `~/.local/share/ruscavosk/models/`), lo apre e gli fa riconoscere un secondo di silenzio.
5. Niente profilo AppArmor: è una libreria, caricata nel processo di RuscaLLisse, non un programma.

Dipendenze di costruzione in più: `autoconf`, `automake`, `libtool`, `zlib1g-dev`, `libopenblas-serial-dev`, `liblapacke-dev` (niente `gfortran`: OpenBLAS e LAPACK sono già compilati da Debian). Sono anche nell’elenco dei pacchetti della ISO (`steps/20-packages.sh`). La prima compilazione di Kaldi è la parte lunga: per questo la cache (punto 8 di ruscallama-engine) conta più che negli altri motori.

**Eccezione: ruscapiper-engine.** È fatto come ruscawhisper-engine: file `ruscapiper-engine-ruscalinux_<versione>_amd64.deb`, variabile `RUSCAPIPER_PIPER_VERSION` (tag `vX.Y.Z` indicato da GitHub come «Latest»), binari e librerie in `/usr/lib/ruscapiper-engine/`, cache in `~/.cache/ruscalinux/ruscapiper-engine/`. Cambiano sei cose:

1. Il sorgente sono **due archivi**: piper1-gpl al tag della release ed espeak-ng al commit che piper1-gpl fissa nella sua build (letto da `GIT_TAG` in `libpiper/CMakeLists.txt`). Ognuno ha il controllo del commit (`git get-tar-commit-id`) e la sua impronta in `checksums/`. La compilazione gira senza rete (`unshare -rn`): prima espeak-ng (statico, con le opzioni di Piper), poi `libpiper.so` e `ruscapiper-stream` con il `CMakeLists.txt` di RuscaLinux, non con quello di Piper, che scaricherebbe espeak-ng e ONNX Runtime.
2. ONNX Runtime è quello di Debian (`libonnxruntime-dev`): la build si ferma se trova un ONNX Runtime scaricato o incluso.
3. Si compilano `libpiper.so` e `ruscapiper-stream`; stessi controlli di rete sui simboli. Niente server HTTP, niente Python.
4. La build controlla che `libpiper.so` esporti le funzioni usate da `ruscapiper-stream` (`SIMBOLI_PIPER`), poi fa dire una frase a `ruscapiper-stream` con la voce di prova del sorgente (`tests/test_voice.onnx`) e controlla intestazioni, campioni, fonemi e allineamenti.
5. `Depends` comprende `libonnxruntime1.21` (calcolato da `dpkg-shlibdeps`).
6. Con l’ONNX Runtime 1.21 di Debian 13 si applica `patches/onnxruntime-1.21.patch` (sezione 1.8); la firma della cache comprende la patch.

Dipendenze di costruzione in più: `libonnxruntime-dev` e `libsonic-dev` (senza, la configurazione di espeak-ng scaricherebbe sonic, anche se poi non lo usa). Come quelle degli altri motori, sono anche nell’elenco dei pacchetti della ISO (`steps/20-packages.sh`), perché RuscaLinux si possa costruire da RuscaLinux.

Esempio di output:

```text
build-deb/
├── ruscacleaner-ruscalinux_1.99.3_all.deb
└── SHA256SUMS
```

Esempio di file `DEBIAN/control`:

```text
Package: ruscafoo
Version: 1.99.3
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-4.0 (>= 4.18), gir1.2-adw-1 (>= 1.7)
Maintainer: Nunzio Curcuruto <info@ruscalinux.org>
Homepage: https://www.ruscalinux.org
Description: Short description in English
 Longer description, indented by one space.
```

Per RuscaMark, se include il controllo ortografico, aggiungere la riga `Recommends` della sezione 10.

RuscaLLama, RuscaMark, RuscaWriter, RuscaTranslator e RuscaNarrator, che includono `rusca_markdown.py` (sezione 1.2), aggiungono a `Depends`:

```text
python3-markdown-it (>= 3.0), python3-mdit-py-plugins (>= 0.4), python3-linkify-it (>= 2.0)
```

Le stesse librerie sono nell’elenco dei pacchetti della ISO (`steps/20-packages.sh`, sezione “LIBS SUPPORT”): ogni dipendenza nuova di un tool va aggiunta anche lì.

Costruzione e checksum (all’interno di `make-deb.sh`):

```bash
dpkg-deb --root-owner-group --build "$PKGDIR" "build-deb/ruscafoo-ruscalinux_${VER}_all.deb"
( cd build-deb && sha256sum *.deb > SHA256SUMS )
```

Controlli consigliati prima del rilascio: `lintian` sul pacchetto, `desktop-file-validate`, `appstreamcli validate`.

---

## 🔢 8. VERSIONE

La versione di tutte le RuscaLinux OS Apps è identica alla versione di RuscaLinux, scritta in `release.conf` (`VERSION`). La stessa versione compare in `VER` di `make-deb.sh`, in `APP_VERSION` del programma, nel campo `Version` del pacchetto, nel nome del file deb e nella metainfo.

Versione attuale:

```text
1.99.3
```

---

## 🌍 9. SUPPORTO LINGUISTICO

Ogni tool è tradotto in queste 26 lingue. Una lingua è attiva quando c’è il suo file in `lang/`: finché manca, valgono i ripieghi della sezione 9.2 e poi l’inglese.

| File | Lingua | Direzione |
|---|---|---|
| en.json | Inglese | LTR |
| it.json | Italiano | LTR |
| zh_CN.json | Cinese semplificato | LTR |
| zh_TW.json | Cinese tradizionale | LTR |
| es.json | Spagnolo | LTR |
| hi.json | Hindi | LTR |
| ar.json | Arabo | **RTL** |
| pt_BR.json | Portoghese brasiliano | LTR |
| pt_PT.json | Portoghese europeo | LTR |
| ru.json | Russo | LTR |
| ja.json | Giapponese | LTR |
| de.json | Tedesco | LTR |
| fr.json | Francese | LTR |
| ko.json | Coreano | LTR |
| id.json | Indonesiano | LTR |
| tr.json | Turco | LTR |
| pl.json | Polacco | LTR |
| nl.json | Olandese | LTR |
| uk.json | Ucraino | LTR |
| cs.json | Ceco | LTR |
| vi.json | Vietnamita | LTR |
| sv.json | Svedese | LTR |
| ro.json | Rumeno | LTR |
| hu.json | Ungherese | LTR |
| el.json | Greco | LTR |
| fi.json | Finlandese | LTR |

Oltre le 26, si aggiunge una lingua solo quando un madrelingua può rivederla: ogni lingua in più va tradotta a ogni testo nuovo, in tutti i tool.

### 9.1 Implementazione

1. Ogni tool contiene la cartella `lang/` con i file JSON, codificati in UTF-8.
2. Nomi dei file: `xx.json` per lingue generiche, `xx_YY.json` per varianti locali (es. `zh_CN.json`, `zh_TW.json`, `pt_BR.json`, `pt_PT.json`).
3. **Le lingue sono i file.** Programmi e `make-deb.sh` ricavano l’elenco da `lang/*.json`: per aggiungere una lingua basta aggiungere il suo file. In RuscaMark e RuscaWriter la lingua va anche nella tabella `LANGUAGES` (nome nella lingua stessa) e, in RuscaWriter, in `SPELL_LOCALES` (dizionario ortografico predefinito).
4. Italiano (`it.json`) e inglese (`en.json`) devono essere sempre presenti e completi; `make-deb.sh` si ferma se mancano.
5. Lingua di fallback: `en.json`. Se manca una traduzione si usa l’inglese.
6. Se una chiave manca sia nella lingua attiva sia in `en.json`, il programma non va in crash e mostra la chiave grezza.
7. Le chiavi sono in inglese, minuscole, con punti per il contesto: `"cleaner.trash.empty": "Svuota cestino"`.
8. Le stringhe con valori variabili usano segnaposto con nome: `"{count} file eliminati"`, mai concatenazioni.
9. Le traduzioni diverse da italiano e inglese sono fatte con l’assistenza di strumenti di intelligenza artificiale: le correzioni dei madrelingua (info@ruscalinux.org) sono benvenute.

### 9.2 Scelta della lingua

1. La lingua segue quella di sistema, nello stesso ordine usato da GTK, così i testi dell’app e quelli dei widget di libadwaita (es. finestra “Informazioni”) coincidono.
2. Niente selettore di lingua dentro le applicazioni.
3. Si scelgono solo lingue tradotte davvero. Per ogni lingua di sistema si provano, in ordine: la variante (`zh_HK`), il suo ripiego, la lingua (`zh`), il ripiego della lingua. I ripieghi sono uguali in tutti i tool:

| Lingua di sistema | Ripiego |
|---|---|
| Cinese di Hong Kong e Macao (`zh_HK`, `zh_MO`) | Cinese tradizionale (`zh_TW`) |
| Cinese di Singapore (`zh_SG`) e cinese generico (`zh`) | Cinese semplificato (`zh_CN`) |
| Portoghese senza variante (`pt`) | Portoghese brasiliano (`pt_BR`) |
| Slovacco (`sk`) | Ceco (`cs`) |

```python
from gi.repository import GLib

LANG_ALIASES = {"zh_HK": "zh_TW", "zh_MO": "zh_TW", "zh_SG": "zh_CN", "zh": "zh_CN",
                "pt": "pt_BR", "sk": "cs"}

def pick_language(available):
    for name in GLib.get_language_names():   # es. "zh_HK.UTF-8", "zh_HK", "zh", "C"
        base = name.split(".")[0].split("@")[0]
        lang = base.split("_")[0]
        for code in (base, LANG_ALIASES.get(base), lang, LANG_ALIASES.get(lang)):
            if code in available:
                return code
    return "en"
```

### 9.3 Testi da destra a sinistra (arabo)

1. GTK inverte automaticamente il layout: usare sempre `start`/`end`, mai `left`/`right`, per allineamenti e margini.
2. Le icone direzionali usano le varianti standard (`go-next-symbolic`), che GTK specchia da sé.
3. Verificare ogni tool almeno una volta con `LANGUAGE=ar`.

### 9.4 Testi lunghi

Tedesco, russo e francese possono essere fino al 40% più lunghi dell’inglese; finlandese e ungherese formano parole composte molto lunghe. Le etichette vanno a capo o si accorciano con ellissi, mai tagliate. Verificare la finestra a 360 px di larghezza in tedesco, finlandese e ungherese, e l’aspetto dell’alfabeto greco.

---

## 🇬🇧 10. SUPPORTO INGLESE BRITANNICO

1. Non creare `en_GB.json` per l’interfaccia: si usa `en.json` come inglese generico.
2. `en_GB` serve solo per dizionari ortografici e sillabazione nei programmi di scrittura.

| Tool | Supporto en_GB |
|---|---|
| RuscaWriter | Sì, sempre (ortografia e sillabazione del PDF) |
| RuscaMark | Sì, se è presente il controllo ortografico |
| RuscaCleaner, RuscaHub, RuscaLLama, RuscaTranslator, RuscaTranscriber, RuscaNarrator, RuscaPinball, RuscaLLisse | No |

Pacchetti: `hunspell-en-gb` (ortografia) e `hyphen-en-gb` (sillabazione, particolarmente consigliato per RuscaWriter, che lo usa con `python3-pyphen`).

Nei deb interessati:

```text
Recommends: hunspell-en-gb               (RuscaMark)
Recommends: hunspell-en-gb, hyphen-en-gb (RuscaWriter)
```

---

## 🔒 11. PRIVACY E SICUREZZA

| Principio | Regola |
|---|---|
| Dati elaborati | Solo in locale |
| Invio a server remoti | No |
| Invio su internet | No |
| Telemetria e statistiche d’uso | No |
| Comandi pericolosi o dannosi | No |
| Raccolta dati personali | Solo se strettamente necessaria, e mai fuori dal computer |
| Operazioni sensibili | Chiare, confermate e controllate dall’utente |

Regole tecniche:

1. Nessun modulo di rete nel codice (`urllib`, `http`, `socket`, `requests`, `Gio.SocketClient` e simili). **Unica eccezione:** RuscaLLama, RuscaTranslator e RuscaLLisse parlano con il proprio motore tramite `http.client` e `socket`, solo verso `127.0.0.1`, attraverso `rusca_engine.py` (vedi sotto).
2. Nessuna esecuzione di comandi tramite shell (`shell=True`, `os.system`). Se serve un programma esterno, usare `subprocess` con lista di argomenti, percorsi assoluti e nessun input dell’utente non validato.
3. Nessun privilegio di amministratore, salvo necessità reale documentata; in quel caso usare `pkexec` con una policy polkit dedicata e limitata.
4. Preferire lo spostamento nel cestino all’eliminazione definitiva.
5. Mai cancellare o modificare file fuori dalla cartella dell’utente senza richiesta esplicita.

Regole aggiuntive per gli strumenti di intelligenza artificiale:

| Regola | Come è applicata |
|---|---|
| Il motore ascolta solo in locale | `llama-server` sempre con `--host 127.0.0.1`, su una porta libera scelta a ogni avvio |
| Gli altri utenti del computer non lo usano | Chiave casuale a ogni avvio, in `$XDG_RUNTIME_DIR/ruscallama/` con permessi 0600, passata con `--api-key-file`; ogni richiesta la presenta |
| Nessun download | Motore compilato senza HTTPS (niente OpenSSL né libcurl) e senza interfaccia web; i programmi non scaricano modelli e non usano le opzioni di download del motore |
| Niente interfaccia web del motore | `--no-webui` |
| Processi rimasti accesi | Fermati solo se il processo è davvero `llama-server` ed è dell’utente (controllo su `/proc`) |
| Confinamento | Profilo AppArmor per `llama-server`, in modalità complain: nega `.ssh`, `.gnupg`, `.config`, profili di Firefox e Thunderbird |
| Conversazioni | Restano in memoria; si salvano solo su richiesta |
| Dati di RuscaTranslator | Voci personali in `~/.config/ruscatranslator/`, memoria di traduzione e glossari in `~/.local/share/ruscatranslator/` |
| Avviso all’utente | I manuali ricordano che le risposte e le traduzioni automatiche vanno verificate |

Regole aggiuntive per il riconoscimento vocale (RuscaTranscriber):

| Regola | Come è applicata |
|---|---|
| Nessuna rete, nemmeno locale | `whisper-cli` è avviato una volta per file e non ha codice di rete (lo controlla la build del motore); RuscaTranscriber non usa moduli di rete e non apre porte |
| FFmpeg legge solo file locali | `ffmpeg` sempre con `-protocol_whitelist file`: anche se il file scelto è una playlist che nomina indirizzi, non li apre |
| Programmi esterni | `/usr/bin/ffmpeg` e `/usr/lib/ruscawhisper-engine/whisper-cli`, con percorso assoluto e lista di argomenti |
| Audio di lavoro | In `~/.cache/ruscatranscriber/` con permessi 0700; cancellato alla fine di ogni trascrizione, all’avvio e alla chiusura |
| Il file di partenza | Mai modificato; i risultati si salvano solo su richiesta, dove sceglie l’utente |
| Confinamento | Profilo AppArmor per `whisper-cli`, in modalità complain: nega la rete, `.ssh`, `.gnupg`, `.config`, profili di Firefox e Thunderbird |
| Avviso all’utente | Il manuale ricorda che la trascrizione automatica va riletta |

Regole aggiuntive per la generazione delle immagini e dei video (RuscaLLama, viste Immagini e Video):

| Regola | Come è applicata |
|---|---|
| Nessuna rete, nemmeno locale | `sd-cli` è avviato una volta per generazione e non ha codice di rete (lo controlla la build del motore: niente server, niente RPC); `rusca_diffusion.py` e `diffusion_view.py` non usano moduli di rete |
| Programma esterno | `/usr/lib/ruscadiffusion-engine/sd-cli`, con percorso assoluto e lista di argomenti |
| La descrizione | Passa al motore in un file (`--prompt-file`, `--negative-prompt-file`), non sulla riga di comando, dove altri utenti la vedrebbero con `ps`; il file si cancella appena il motore esce |
| Immagini e video di lavoro | In `~/.cache/ruscallama/images/` con permessi 0700; cancellati all’avvio e alla chiusura; prima di chiudere con immagini o video non salvati si chiede conferma |
| Immagine di partenza di un video | Copiata nella cartella di lavoro prima di passarla al motore: `sd-cli` non legge immagini nel resto della home |
| Metadati | Per impostazione predefinita `--disable-image-metadata`: il PNG salvato non contiene descrizione e impostazioni, salvo scelta contraria |
| Modelli | Solo file locali, letti dall’utente; le cartelle aggiunte non vengono copiate né modificate; dei `.safetensors` si legge solo l’intestazione |
| Confinamento | Profilo AppArmor per `sd-cli`, in modalità complain: nega la rete, `.ssh`, `.gnupg`, `.config`, profili di Firefox e Thunderbird; scrive solo nella cartella di lavoro |

Regole aggiuntive per la sintesi vocale (RuscaNarrator):

| Regola | Come è applicata |
|---|---|
| Nessuna rete, nemmeno locale | `llama-tts` legge un testo e scrive un file, senza aprire porte; RuscaNarrator non usa moduli di rete |
| FFmpeg legge solo file locali | Sempre con `-protocol_whitelist file` |
| Programmi esterni | `/usr/lib/ruscallama-engine/llama-tts` e `/usr/bin/ffmpeg`, con percorso assoluto e lista di argomenti |
| Audio di lavoro | In `~/.cache/ruscanarrator/` con permessi 0700; cancellato quando si scarta il risultato, all’avvio e alla chiusura |
| Il documento di partenza | Mai modificato; l’audio si salva solo su richiesta, dove sceglie l’utente |
| Voci create | In `~/.local/share/ruscanarrator/voices/`, solo quando l’utente sceglie «Tieni questa voce»; le prove scartate si cancellano |
| Voci altrui | Il manuale chiede di usare come voce di riferimento la propria, o una voce che si ha il permesso di usare |

Regole aggiuntive per la conversazione a voce (RuscaLLisse):

| Regola | Come è applicata |
|---|---|
| Rete solo verso il proprio motore | `llama-server` su 127.0.0.1 con le regole degli strumenti di intelligenza artificiale; Vosk e Piper non hanno codice di rete (lo controlla la build dei motori) |
| Il microfono | Aperto solo durante l’ascolto; in pausa `pw-record` è fermo. Lo stato è sempre visibile: pulsante nella barra del titolo, sottotitolo, volto |
| L’audio | Mai scritto su disco: passa in memoria da `pw-record` a Vosk e da `ruscapiper-stream` a `pw-play` |
| La conversazione | Mai scritta: né sullo schermo né su disco. Resta in memoria finché la finestra è aperta |
| Programmi esterni | `/usr/bin/pw-record`, `/usr/bin/pw-play`, `/usr/bin/espeak-ng`, `/usr/lib/ruscapiper-engine/ruscapiper-stream`, `/usr/lib/ruscallama-engine/llama-server`, con percorso assoluto e lista di argomenti; il testo delle frasi passa a `ruscapiper-stream` e a `espeak-ng` dallo standard input, mai sulla riga di comando |
| Confinamento | Profilo AppArmor per `ruscapiper-stream`, in modalità complain: nega la rete, `.ssh`, `.gnupg`, `.config`, profili di Firefox e Thunderbird; legge solo le cartelle delle voci |
| Modelli e voci | Solo file locali, importati dall’utente; la licenza della voce scelta è mostrata nelle Preferenze |
| Avviso all’utente | Il manuale ricorda che l’entità è un personaggio e che le sue risposte vanno verificate |

Regole aggiuntive per il flipper (RuscaPinball):

| Regola | Come è applicata |
|---|---|
| Nessuna rete | I moduli non importano moduli di rete (lo controlla il test) |
| Dati | Solo i record e due impostazioni, in locale; il nome del record lo scrive il giocatore, al massimo 10 caratteri |
| Suoni | Sintetizzati in memoria all’avvio; se l’audio non c’è il gioco resta muto e non si ferma |

Dichiarazione:

Tutti i dati elaborati dalle RuscaLinux OS Apps rimangono in locale.
Nessun dato o file viene inviato a server remoti.
Nessun dato o file viene inviato su internet.
Nessun software contiene comandi pericolosi o dannosi per il sistema operativo.

---

## 🤖 12. NOTA IA

### 12.1 Testo

Il testo è unico e non va riformulato. Non cita nomi di prodotti o servizi di intelligenza artificiale.

Criteri del testo: prima il lavoro dell’autore, poi lo strumento; dire con precisione che cosa ha fatto l’intelligenza artificiale (la scrittura del codice); descrivere la divisione del lavoro com’è davvero, senza ridurla né ingrandirla. In italiano si scrive “intelligenza artificiale” o “IA”, non “AI”.

| Lingua | Testo |
|---|---|
| Italiano | Progettazione, specifiche e verifica dell’autore; codice scritto con l’assistenza di strumenti di intelligenza artificiale. |
| Inglese | Design, specifications and testing by the author; code written with the assistance of AI tools. |

Nei file `lang/`, la chiave `ai_note` di `it.json` e `en.json` contiene esattamente questi testi; le altre 13 lingue ne contengono la traduzione.

### 12.2 Dove compare

La nota compare in tre posti, e solo in questi:

| Posto | Forma |
|---|---|
| Programma | Riga “Nota di sviluppo” nella finestra “Informazioni” (sezione 3.10), che apre la nota nella lingua dell’interfaccia, presa dalla chiave `ai_note` |
| Pacchetto deb | Campo `Comment` del file `/usr/share/doc/<pacchetto>/copyright`, testo inglese seguito da “See NOTA-IA.md in the RuscaLinux repository.” |
| Repository | File `NOTA-IA.md` nella radice del repository, in italiano e inglese, con il testo della nota, la divisione del lavoro e il rimando a queste specifiche |

Non va ripetuta altrove (file `.desktop`, metainfo, descrizione del pacchetto, manuali): più copie finiscono per divergere. I manuali possono rimandare alla finestra “Informazioni” o a `NOTA-IA.md`.

---

## ✅ 13. CHECKLIST DI RILASCIO

Un tool è pronto quando:

1. Gira su Debian Stable con Python >= 3.10, GTK >= 4.18 e libadwaita >= 1.7.
2. Usa `Adw.Application`, `Adw.ApplicationWindow`, `Adw.ToolbarView` e `Adw.HeaderBar`.
3. Non ha barra dei menu classica; il menu principale contiene Scorciatoie, Informazioni ed eventualmente Preferenze.
4. Carica `style.css` RuscaLinux, applica `rusca-light`/`rusca-dark` alle finestre e non contiene altro CSS che modifichi i widget standard.
5. È leggibile in modalità chiara, scura e a contrasto elevato, e ha la riga “Tema” nelle preferenze (sezione 4.5, regola 3).
6. Usa il gradiente solo dove ammesso dalla sezione 4.3.
7. Funziona a 360 × 294 px e da sola tastiera.
8. Mostra stati vuoti con `Adw.StatusPage` e conferme con `Adw.AlertDialog`.
9. Ha la finestra “Informazioni” comune (sezione 3.10), con la riga “Nota di sviluppo” che apre la nota IA; la nota compare solo nei tre posti della sezione 12.2.
10. Ha le traduzioni della sezione 9, con i ripieghi della sezione 9.2, fallback inglese e senza crash su chiavi mancanti; funziona in arabo (RTL).
11. Ha identificatori coerenti tra loro (sezioni 1 e 5.2).
12. Ha file `.desktop` e metainfo validi, con `StartupWMClass` uguale all’App ID e la categoria `X-RuscaLinux-Apps` (sezione 5.3).
13. Ha icona SVG e icona simbolica.
14. Ha `make-deb.sh` che produce un solo `ruscafoo-ruscalinux_<versione>_all.deb` (o `_amd64.deb` per ruscallama-engine, ruscawhisper-engine, ruscadiffusion-engine, ruscavosk-engine e ruscapiper-engine) e `SHA256SUMS` in `build-deb/`.
15. Ha la versione uguale a `VERSION` di `release.conf`.
16. È licenziato GPL-3.0, con componenti esterni dichiarati.
17. Non usa rete, telemetria o comandi pericolosi (per RuscaLLama, RuscaTranslator e RuscaLLisse: rete solo verso 127.0.0.1, sezione 11, e le viste Immagini e Video di RuscaLLama non la usano in nessun modo; RuscaTranscriber e RuscaNarrator non usano la rete in nessun modo).
18. Se mostra, converte o divide Markdown, usa `rusca_markdown.py` (sezione 1.2), e i test di `tests/` passano.
19. Per RuscaLLisse: con `RUSCALLISSE_DEBUG=1`, su ciascuno dei due computer di prova, il tempo fra la fine del parlato e il primo campione audio è misurato e scritto nelle note di rilascio, con il modello Vosk, il modello linguistico e la voce usati.

Per RuscaPinball i punti 2–5, 8 e 9 valgono nella forma della sezione 1.5: è un gioco pygame, con i colori, i contrasti e la nota IA di RuscaLinux disegnati dal gioco stesso.

---

# 🇮🇹 14. GUIDA UTENTE IN ITALIANO

## 🚀 Requisiti

| Requisito | Valore |
|---|---|
| Sistema | RuscaLinux o Debian Stable |
| Desktop | GNOME |
| Librerie grafiche | GTK 4 e libadwaita |
| Linguaggio | Python >= 3.10 |
| Pacchetto | deb |

I tool sono già inclusi in RuscaLinux. Le istruzioni seguenti servono solo per reinstallarli o per usarli su Debian.

## 📦 Installazione

Prima di installare, verificare l’integrità del pacchetto (nella cartella che contiene deb e `SHA256SUMS`):

```bash
sha256sum -c SHA256SUMS
```

Installazione consigliata:

```bash
sudo apt install ./nome-tool-ruscalinux_1.99.3_all.deb
```

Installazione alternativa:

```bash
sudo dpkg -i nome-tool-ruscalinux_1.99.3_all.deb
sudo apt -f install    # solo se mancano dipendenze
```

## ▶️ Avvio

1. Dal menu delle applicazioni di GNOME (metodo consigliato).
2. Cercando il nome del tool in Attività.
3. Dal terminale, con il comando in minuscolo (es. `ruscacleaner`).

In ogni tool, il menu in alto a destra contiene Preferenze, Scorciatoie da tastiera e Informazioni.

## 🧹 RuscaCleaner

Strumento per la privacy e la pulizia del desktop GNOME.

1. Aprire RuscaCleaner.
2. Selezionare le aree da controllare.
3. Esaminare le operazioni proposte.
4. Confermare solo le operazioni comprese e desiderate.
5. Attendere il completamento.

RuscaCleaner non esegue operazioni distruttive non chiare all’utente e, quando possibile, sposta i file nel cestino invece di eliminarli definitivamente.

## 📦 RuscaHub

Strumento per la gestione delle AppImages.

1. Aprire RuscaHub.
2. Aggiungere una AppImage.
3. Verificare che la AppImage sia presente nell’elenco.
4. Avviare la AppImage.
5. Rimuovere una AppImage non più necessaria.

RuscaHub gestisce le AppImages senza modificarne il contenuto.

## 📝 RuscaMark

Editor Markdown.

1. Aprire RuscaMark.
2. Creare un nuovo documento Markdown o aprirne uno esistente.
3. Scrivere o modificare il testo.
4. Salvare il documento (Ctrl+S).
5. Esportare il documento, se la funzione è disponibile.

Il controllo ortografico, se presente, usa solo dizionari locali (incluso `en_GB` tramite `hunspell-en-gb`) e non invia mai il testo online.

## ✍️ RuscaWriter

Scrittura e impaginazione di libri.

1. Aprire RuscaWriter e scegliere «Crea nuovo» o «Apri esistente» (i progetti sono file `.rwr`).
2. Aggiungere i capitoli con **+** e scrivere; il titolo del capitolo è il suo nome nella colonna dei capitoli (F2 per cambiarlo). A destra le note di ogni capitolo.
3. Formattare con il pulsante **Formato** (o Ctrl+B, Ctrl+I, Ctrl+2 per una sezione, Ctrl+3 per una sottosezione): RuscaWriter scrive il Markdown al posto tuo.
4. Impostare formato e margini dal menu principale → Impostazione pagina.
5. Esportare dal menu principale → Esporta: PDF, EPUB, AZW3, ODT, DOCX, HTML, Markdown o testo. In ogni formato il capitolo, le sezioni e le sottosezioni hanno gli stili di titolo veri.

Controllo ortografico e sillabazione usano solo dizionari locali (incluso l’inglese britannico tramite `hunspell-en-gb` e `hyphen-en-gb`). Il testo non viene mai inviato online.

## 💬 RuscaLLama

Chat con modelli linguistici che girano su questo computer.

1. Copiare un modello GGUF in `~/.local/share/ruscallama/models/` (dal pannello delle impostazioni: “Apri la cartella dei modelli”).
2. Aprire RuscaLLama e scegliere il modello nel pannello laterale (F9).
3. Scrivere un messaggio e premere Invio: il motore parte da solo.
4. Copiare o salvare le risposte dal menu di ogni risposta; salvare la conversazione con Ctrl+S.

Immagini (vista **Immagini**, Alt+2) e video (vista **Video**, Alt+3):

1. Copiare un modello per immagini in `~/.local/share/ruscadiffusion/models/`: un file `.safetensors` o `.gguf` (per esempio Stable Diffusion 1.5 o SDXL), oppure una cartella con il modello e i suoi file (FLUX, Z-Image…). Se il modello sta già in un’altra cartella: pannello laterale (F9) → “Aggiungi una cartella…”.
2. Scrivere la descrizione, scegliere Quadrata, Orizzontale o Verticale e premere “Genera” (Invio).
3. Ogni immagine si salva, si copia o si allega alla conversazione dal suo menu. Le immagini non salvate si cancellano alla chiusura.
4. Per i video: copiare un modello per video (per esempio Wan2.2-TI2V-5B: “Quali file scaricare?”) nella stessa cartella, descrivere la scena e il movimento e premere “Crea il video”. Un video di 2 secondi richiede diversi minuti; il menu di un’immagine ha “Anima in un video”.

Le viste Immagini e Video usano **ruscadiffusion-engine**, cioè stable-diffusion.cpp, software esterno con licenza MIT. Non usa la rete.

## 🌐 RuscaTranslator

Traduzione di documenti Markdown tra le 26 lingue della sezione 9: inglese, italiano, cinese semplificato e tradizionale, spagnolo, hindi, arabo, portoghese brasiliano ed europeo, russo, giapponese, tedesco, francese, coreano, indonesiano, turco, polacco, olandese, ucraino, ceco, vietnamita, svedese, rumeno, ungherese, greco e finlandese.

1. Aprire un documento (Ctrl+O) o trascinarlo nel riquadro “Originale”.
2. Scegliere lingua di partenza (o “Rileva la lingua”), lingua d’arrivo e tipo di testo.
3. Premere “Traduci” (Ctrl+Invio).
4. Rileggere la traduzione nel riquadro di destra e salvarla (Ctrl+S).

Tra italiano e inglese il programma usa una base di conoscenza linguistica, un glossario del documento e la memoria delle traduzioni salvate.

Entrambi i programmi usano **ruscallama-engine**, cioè llama.cpp, software esterno con licenza MIT. Tutto resta sul computer.

## 🎙️ RuscaTranscriber

Trascrizione di video e audio in testo e sottotitoli, con un modello Whisper che gira su questo computer.

1. Copiare un modello Whisper in formato ggml (per esempio `ggml-large-v3-turbo.bin`) in `~/.local/share/ruscawhisper/models/` (dal menu principale: “Apri la cartella dei modelli”).
2. Aprire il video o l’audio (Ctrl+O) o trascinarlo sulla finestra.
3. Scegliere la lingua parlata (o “Rileva la lingua”) e premere “Trascrivi” (Ctrl+Invio).
4. Salvare il testo in Markdown (Ctrl+S) e i sottotitoli in SRT (Ctrl+E).

RuscaTranscriber usa **ruscawhisper-engine**, cioè whisper.cpp, software esterno con licenza MIT, e FFmpeg per leggere l’audio. Non usa la rete. La trascrizione automatica va riletta.

## 🔊 RuscaNarrator

Lettura ad alta voce di documenti e sottotitoli, con un modello di sintesi vocale che gira su questo computer.

1. Copiare il modello e il suo mmproj (per esempio `Qwen3-TTS-12Hz-1.7B-Base-Q8_0.gguf` e `mmproj-Qwen3-TTS-12Hz-1.7B-Base-bf16.gguf`) in `~/.local/share/ruscanarrator/models/` (dal menu principale: “Apri la cartella dei modelli”).
2. Dal menu principale, “Crea una voce”: ascoltare le voci di prova e tenere quella che piace, oppure scegliere nelle Preferenze una registrazione di una decina di secondi. Così la voce è la stessa in tutte le frasi.
3. Aprire un documento Markdown o dei sottotitoli SRT (Ctrl+O), scegliere la lingua della voce e premere “Genera l’audio” (Ctrl+Invio).
4. Ascoltare il risultato e salvarlo in WAV (Ctrl+S), FLAC, Opus o MP3.

Con i sottotitoli ogni frase parte all’ora del suo sottotitolo. RuscaNarrator usa `llama-tts` di **ruscallama-engine** (llama.cpp, licenza MIT) e FFmpeg. Non usa la rete.

## 🗣️ RuscaLLisse

Una conversazione a voce con Ellittica, una donna digitale che ti ascolta, ti risponde e ti spiega le cose in modo semplice. La sua personalità la decidi tu.

1. Servono tre cose, che RuscaLLisse non scarica: un modello Vosk per ascoltare (per esempio la cartella `vosk-model-it-0.22`, da copiare in `~/.local/share/ruscavosk/models/`), un modello linguistico GGUF (lo stesso di RuscaLLama) e una voce Piper (un file `.onnx` con il suo `.onnx.json`: menu principale → “Importa una voce…”). La pagina di benvenuto dice cosa manca e, con “Quali file scaricare?”, da dove prenderlo.
2. Dal menu principale, “Modifica la personalità…”: scrivi il quid di Ellittica, il tratto centrale del suo carattere.
3. Parla: Ellittica ascolta, pensa e risponde a voce. Spazio mette in pausa il microfono, Esc la fa tacere.
4. Se sbaglia l’accento di una parola: menu principale → “Come la pronuncia?…” → “Correggi la pronuncia…”. Da quel momento la dirà giusta.

È un dialogo come nella vita: sullo schermo c’è solo il suo volto, niente viene scritto e la conversazione non si salva. Se non capisce bene una parola la ricava dal contesto, e se proprio non capisce te lo chiede.

Puoi interromperla parlando, come in una conversazione vera. Se il sistema non ha la cancellazione dell’eco, con gli altoparlanti la si interrompe con Spazio o Esc; con le cuffie attiva “Uso le cuffie” nelle Preferenze.

RuscaLLisse usa **ruscavosk-engine** (Vosk, licenza Apache 2.0), **ruscallama-engine** (llama.cpp, licenza MIT) e **ruscapiper-engine** (Piper, licenza GPL-3.0). Non usa la rete: il modello linguistico ascolta solo su 127.0.0.1 e l’audio non viene mai salvato. Ogni modello e ogni voce hanno la propria licenza, mostrata nelle Preferenze: molte voci Piper sono solo per uso non commerciale. Le risposte vanno verificate: Ellittica è un personaggio, non un’esperta.

## 🎱 RuscaPinball

Flipper con il tavolo «Amethyst», visto in prospettiva come nei flipper per home computer degli anni ’80.

1. Aprire RuscaPinball dalla cartella RuscaLinux Apps o fra i giochi; Spazio fa partire la partita.
2. Tenere premuto Spazio (o ↓) e rilasciare per lanciare: più a lungo si tiene, più forte parte la pallina.
3. Flipper con Z e M (o Maiusc sinistro e destro, ← e →); N scuote il tavolo, ma al terzo colpo ravvicinato c’è il tilt.
4. Accendere le lampade dell’anello del bonus fino allo SPECIAL, poi mandare la pallina nella trappola in alto a sinistra: pallina extra.
5. P mette in pausa, F2 attiva l’effetto TV, F3 l’audio, F11 lo schermo intero, I le informazioni.

Si gioca anche con un gamepad (LB e RB i flipper, A il lancio, Start la pausa). Il gioco non usa la rete.

## 🧯 Risoluzione dei problemi

Se un tool non si avvia:

1. Verificare di usare RuscaLinux o Debian Stable.
2. Verificare l’integrità del pacchetto con `sha256sum -c SHA256SUMS`.
3. Reinstallare il pacchetto con `sudo apt install ./nome-del-file.deb`: le dipendenze (GTK 4, libadwaita, Python 3) vengono installate automaticamente.
4. Avviare il tool dal terminale per leggere eventuali messaggi d’errore e includerli nella segnalazione.

Supporto: info@ruscalinux.org

## 🔒 Privacy e sicurezza

Tutti i dati elaborati dalle RuscaLinux OS Apps rimangono in locale. Nessun dato o file viene inviato a server remoti o su internet. Nessun tool contiene telemetria o comandi pericolosi per il sistema.

---

# 🇬🇧 15. ENGLISH GUIDE

## 📋 General information

| Field | Value |
|---|---|
| Project | RuscaLinux OS Apps |
| Operating system | RuscaLinux |
| Website | https://www.ruscalinux.org |
| Email | info@ruscalinux.org |
| Base distribution | Debian Stable |
| Desktop | GNOME |
| Author | Nunzio Curcuruto (ruscalinux-dev) |
| Current version | 1.99.3 |
| Code license | GPL-3.0 — https://www.gnu.org/licenses/gpl-3.0.html |

## 🛠️ Included tools

| Tool | Description |
|---|---|
| RuscaCleaner | GNOME desktop privacy and cleaning |
| RuscaHub | AppImage management |
| RuscaMark | Markdown editing |
| RuscaWriter | Writing and typesetting books |
| RuscaLLama | Chat with local language models and images from a description |
| RuscaTranslator | Translation of Markdown documents, with a RAG optimized for Italian ↔ English |
| ruscallama-engine | Engine that runs the models: llama.cpp, an external component (MIT) |
| RuscaTranscriber | Transcription of video and audio into text (Markdown) and subtitles (SRT) |
| ruscawhisper-engine | Speech recognition engine: whisper.cpp, an external component (MIT) |
| ruscadiffusion-engine | Image and video generation engine of RuscaLLama: stable-diffusion.cpp, an external component (MIT) |
| RuscaNarrator | Reading Markdown documents and SRT subtitles (following their timing) aloud |
| RuscaPinball | 1980s-style pinball, with the “Amethyst” table seen in perspective |
| RuscaLLisse | Voice conversation with an animated digital entity whose personality you decide (the first one is Ellittica) |
| ruscavosk-engine | Real-time speech recognition engine of RuscaLLisse: Vosk, an external component (Apache 2.0) |
| ruscapiper-engine | Speech synthesis engine of RuscaLLisse: Piper (piper1-gpl), an external component (GPL-3.0) |

## 🚀 Requirements

| Requirement | Value |
|---|---|
| System | RuscaLinux or Debian Stable |
| Desktop | GNOME |
| Graphics libraries | GTK 4 and libadwaita |
| Language | Python >= 3.10 |
| Package | deb |

The tools come preinstalled in RuscaLinux. The steps below are only needed to reinstall them or to use them on Debian.

## 📦 Installation

Before installing, verify package integrity (in the folder containing the deb and `SHA256SUMS`):

```bash
sha256sum -c SHA256SUMS
```

Recommended installation:

```bash
sudo apt install ./tool-name-ruscalinux_1.99.3_all.deb
```

Alternative installation:

```bash
sudo dpkg -i tool-name-ruscalinux_1.99.3_all.deb
sudo apt -f install    # only if dependencies are missing
```

## ▶️ Launch

1. From the GNOME applications menu (recommended).
2. By searching for the tool name in Activities.
3. From the terminal, using the lowercase command (e.g. `ruscacleaner`).

In every tool, the menu at the top right contains Preferences, Keyboard Shortcuts and About.

## 🧹 RuscaCleaner

GNOME desktop privacy and cleaning.

1. Open RuscaCleaner.
2. Select the areas to inspect.
3. Review the proposed operations.
4. Confirm only the operations you understand and want.
5. Wait for completion.

RuscaCleaner never performs destructive operations that are unclear to the user and, where possible, moves files to the trash instead of deleting them permanently.

## 📦 RuscaHub

AppImage management.

1. Open RuscaHub.
2. Add an AppImage.
3. Check that the AppImage appears in the list.
4. Launch the AppImage.
5. Remove an AppImage you no longer need.

RuscaHub manages AppImages without modifying their content.

## 📝 RuscaMark

Markdown editor.

1. Open RuscaMark.
2. Create a new Markdown document or open an existing one.
3. Write or edit text.
4. Save the document (Ctrl+S).
5. Export the document if the feature is available.

Spell checking, if present, uses only local dictionaries (including `en_GB` through `hunspell-en-gb`) and never sends text online.

## ✍️ RuscaWriter

Writing and typesetting books.

1. Open RuscaWriter and choose "Create new" or "Open existing" (projects are `.rwr` files).
2. Add chapters with **+** and write; a chapter's title is its name in the chapter column (F2 to change it). Each chapter's notes are on the right.
3. Format with the **Format** button (or Ctrl+B, Ctrl+I, Ctrl+2 for a section, Ctrl+3 for a subsection): RuscaWriter writes the Markdown for you.
4. Set format and margins from the main menu → Page setup.
5. Export from the main menu → Export: PDF, EPUB, AZW3, ODT, DOCX, HTML, Markdown or text. In every format chapters, sections and subsections use real heading styles.

Spell checking and hyphenation use only local dictionaries (including British English through `hunspell-en-gb` and `hyphen-en-gb`). Text is never sent online.

## 💬 RuscaLLama

Chat with language models that run on this computer.

1. Copy a GGUF model into `~/.local/share/ruscallama/models/` (from the settings panel: "Open the Models Folder").
2. Open RuscaLLama and choose the model in the side panel (F9).
3. Write a message and press Enter: the engine starts on its own.
4. Copy or save answers from each answer's menu; save the conversation with Ctrl+S.

Images (**Images** view, Alt+2) and videos (**Videos** view, Alt+3):

1. Copy an image model into `~/.local/share/ruscadiffusion/models/`: a `.safetensors` or `.gguf` file (for example Stable Diffusion 1.5 or SDXL), or a folder with the model and its files (FLUX, Z-Image…). If the model is already in another folder: side panel (F9) → "Add a Folder…".
2. Write the description, choose Square, Landscape or Portrait and press "Generate" (Enter).
3. Save, copy or attach each image to the conversation from its menu. Images you have not saved are deleted when the program closes.
4. For videos: copy a video model (for example Wan2.2-TI2V-5B: "Which Files to Download?") into the same folder, describe the scene and the motion and press "Create Video". A 2-second video takes several minutes; the menu of an image has "Animate in a Video".

The Images and Videos views use **ruscadiffusion-engine**, that is stable-diffusion.cpp, an external component under the MIT license. It does not use the network.

## 🌐 RuscaTranslator

Translation of Markdown documents between the 26 languages of RuscaLinux OS Apps: English, Italian, Simplified and Traditional Chinese, Spanish, Hindi, Arabic, Brazilian and European Portuguese, Russian, Japanese, German, French, Korean, Indonesian, Turkish, Polish, Dutch, Ukrainian, Czech, Vietnamese, Swedish, Romanian, Hungarian, Greek and Finnish.

1. Open a document (Ctrl+O) or drag it onto the "Original" pane.
2. Choose the source language (or "Detect language"), the target language and the text type.
3. Press "Translate" (Ctrl+Enter).
4. Review the translation in the right pane and save it (Ctrl+S).

Between Italian and English the program uses a linguistic knowledge base, a document glossary and the memory of saved translations.

Both programs use **ruscallama-engine**, that is llama.cpp, an external component under the MIT license. Everything stays on the computer.

## 🎙️ RuscaTranscriber

Transcription of video and audio into text and subtitles, with a Whisper model that runs on this computer.

1. Copy a Whisper model in ggml format (for example `ggml-large-v3-turbo.bin`) into `~/.local/share/ruscawhisper/models/` (from the main menu: "Open the Models Folder").
2. Open the video or audio file (Ctrl+O) or drag it onto the window.
3. Choose the spoken language (or "Detect language") and press "Transcribe" (Ctrl+Enter).
4. Save the text as Markdown (Ctrl+S) and the subtitles as SRT (Ctrl+E).

RuscaTranscriber uses **ruscawhisper-engine**, that is whisper.cpp, an external component under the MIT license, and FFmpeg to read the audio. It does not use the network. Automatic transcription must be reviewed.

## 🔊 RuscaNarrator

Reading documents and subtitles aloud, with a speech synthesis model that runs on this computer.

1. Copy the model and its mmproj (for example `Qwen3-TTS-12Hz-1.7B-Base-Q8_0.gguf` and `mmproj-Qwen3-TTS-12Hz-1.7B-Base-bf16.gguf`) into `~/.local/share/ruscanarrator/models/` (from the main menu: "Open the Models Folder").
2. From the main menu, "Create a Voice": listen to trial voices and keep the one you like, or choose in Preferences a recording of about ten seconds. This keeps the same voice in every sentence.
3. Open a Markdown document or SRT subtitles (Ctrl+O), choose the voice language and press "Generate Audio" (Ctrl+Enter).
4. Listen to the result and save it as WAV (Ctrl+S), FLAC, Opus or MP3.

With subtitles every sentence starts at the time of its subtitle. RuscaNarrator uses `llama-tts` from **ruscallama-engine** (llama.cpp, MIT license) and FFmpeg. It does not use the network.

## 🗣️ RuscaLLisse

A voice conversation with Ellittica, a digital woman who listens, answers and explains things simply. You decide her personality.

1. Three things are needed, and RuscaLLisse does not download them: a Vosk model to listen (for example the `vosk-model-en-us-0.22` folder, copied into `~/.local/share/ruscavosk/models/`), a GGUF language model (the same as RuscaLLama) and a Piper voice (an `.onnx` file with its `.onnx.json`: main menu → "Import a Voice…"). The welcome page shows what is missing and, with "Which Files to Download?", where to get it.
2. From the main menu, "Edit Personality…": write Ellittica's quid, the core trait of her character.
3. Talk: Ellittica listens, thinks and answers aloud. Space pauses the microphone, Esc makes her stop.
4. If she stresses a word wrongly: main menu → "How Does She Say It?…" → "Fix Pronunciation…". From then on she says it right.

It is a conversation like in real life: only her face is on screen, nothing is written and the conversation is not saved. If she mishears a word she works it out from the context, and if she really does not understand she asks you.

You can interrupt her by speaking, as in a real conversation. If the system has no echo cancellation, with speakers you interrupt her with Space or Esc; with headphones turn on "I Use Headphones" in Preferences.

RuscaLLisse uses **ruscavosk-engine** (Vosk, Apache 2.0 license), **ruscallama-engine** (llama.cpp, MIT license) and **ruscapiper-engine** (Piper, GPL-3.0 license). It does not use the network: the language model listens only on 127.0.0.1 and audio is never saved. Every model and voice has its own license, shown in Preferences: many Piper voices are for non-commercial use only. Answers must be checked: Ellittica is a character, not an expert.

## 🎱 RuscaPinball

Pinball with the “Amethyst” table, seen in perspective like the 1980s home computer pinball games.

1. Open RuscaPinball from the RuscaLinux Apps folder or from the games; Space starts a game.
2. Hold Space (or ↓) and release to launch: the longer you hold, the harder the ball goes.
3. Flippers with Z and M (or Left and Right Shift, ← and →); N nudges the table, but the third nudge in a row means tilt.
4. Light the bonus ring up to the SPECIAL, then send the ball into the trap at the top left: extra ball.
5. P pauses, F2 toggles the TV effect, F3 the sound, F11 full screen, I the information.

A gamepad works too (LB and RB the flippers, A the launch, Start the pause). The game does not use the network.

## 🌍 Language support

Every tool follows the system language and is translated into 26 languages: English, Italian, Simplified and Traditional Chinese, Spanish, Hindi, Arabic, Brazilian and European Portuguese, Russian, Japanese, German, French, Korean, Indonesian, Turkish, Polish, Dutch, Ukrainian, Czech, Vietnamese, Swedish, Romanian, Hungarian, Greek and Finnish. Slovak users see Czech; English is the fallback for anything not yet translated. Translations other than Italian and English are made with the assistance of AI tools: corrections from native speakers are welcome at info@ruscalinux.org.

## 🧯 Troubleshooting

If a tool does not start:

1. Make sure you are using RuscaLinux or Debian Stable.
2. Verify the package with `sha256sum -c SHA256SUMS`.
3. Reinstall it with `sudo apt install ./file-name.deb`: dependencies (GTK 4, libadwaita, Python 3) are installed automatically.
4. Launch the tool from a terminal to read any error messages and include them in your report.

Support: info@ruscalinux.org

## 🔒 Privacy and security

All data processed by RuscaLinux OS Apps remains local. No data or files are sent to remote servers or over the internet. No tool contains telemetry or commands that could harm the system.

## 🤖 AI note

Development note: “Design, specifications and testing by the author; code written with the assistance of AI tools.”

---

Questo file è il riferimento unico per specifiche, interfaccia, tema, pacchetti, supporto linguistico, privacy, sicurezza e guida utente delle RuscaLinux OS Apps.
