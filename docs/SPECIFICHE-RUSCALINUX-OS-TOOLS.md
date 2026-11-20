# DOCUMENTAZIONE UNICA - RUSCALINUX OS TOOLS

Questo è il file unico e completo dei RuscaLinux OS Tools.
Contiene specifiche tecniche, linee guida d’interfaccia (GNOME), tema grafico RuscaLinux, pacchetti, supporto linguistico, privacy, sicurezza, nota IA e guida utente in italiano e inglese.

Si trova nel repository in `docs/SPECIFICHE-RUSCALINUX-OS-TOOLS.md`. In caso di conflitto con altri documenti, questo file è il riferimento. Le convenzioni sui nomi riprendono `docs/NAMING.md` del repository, con una differenza: file `.desktop`, metainfo e icona prendono il nome dall’App ID (convenzione GNOME). `docs/NAMING.md` va aggiornato di conseguenza.

---

## 📋 INFORMAZIONI GENERALI

| Campo | Valore |
|---|---|
| Progetto | RuscaLinux OS Tools |
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

### 1.1 Gli strumenti di intelligenza artificiale

RuscaLLama e RuscaTranslator usano modelli linguistici in formato GGUF che girano sul computer dell’utente, tramite **ruscallama-engine**.

- **ruscallama-engine è llama.cpp** (<https://github.com/ggml-org/llama.cpp>), software esterno con licenza MIT, copyright The ggml authors. RuscaLinux lo compila dal sorgente senza modificarne il codice, con il backend Vulkan (NVIDIA, AMD, Intel, con ripiego sulla CPU), **senza HTTPS** (`LLAMA_OPENSSL=OFF`) e senza interfaccia web: il motore non può scaricare modelli da Hugging Face né da altri siti. La versione è l’ultima release stabile di llama.cpp, verificata con il commit del tag e con un’impronta SHA-256 (sezioni 6 e 7).
- Il pacchetto del motore non ha interfaccia, quindi non ha traduzioni, icona né finestra Informazioni: lo dichiarano le finestre Informazioni di RuscaLLama e RuscaTranslator, nel gruppo “Componenti esterni”.
- Programmi del pacchetto, in `/usr/lib/ruscallama-engine/`: `llama-server`, che avviano RuscaLLama e RuscaTranslator; `llama-cli` e `llama-bench` per diagnosticare e misurare dal terminale; `llama-tts` per la sintesi vocale, con modelli TTS in GGUF e il loro mmproj (per esempio Qwen3-TTS, Pocket TTS, Soprano): lo avvia RuscaNarrator (sezione 1.4), e si può usare dal terminale. La build controlla che `llama-tts` accetti le opzioni usate da RuscaNarrator (`OPZIONI_TTS`). L’elenco (`KEEP_BINARIES` in `make-deb.sh`) fa parte della firma della cache di compilazione: aggiungere un programma ricompila llama.cpp.
- I modelli non fanno parte dei pacchetti: l’utente li copia in `~/.local/share/ruscallama/models/` o l’amministratore in `/usr/share/ruscallama/models/`. Ogni modello ha la propria licenza, che l’utente deve rispettare.
- Il modulo `rusca_engine.py`, che avvia e interroga il motore, è identico in RuscaLLama e RuscaTranslator, come `style.css` (si modifica una volta e si copia).
- Il modulo `rusca_markdown.py`, motore Markdown comune (sezione 1.2), è identico in RuscaLLama, RuscaMark, RuscaWriter (`src/ruscawriter/`), RuscaTranslator e RuscaNarrator, con la stessa regola; accanto c’è `markdown_it_mark.py`, componente esterno usato dal motore (sezione 6), anch’esso identico nei cinque programmi. RuscaTranslator mostra il Markdown come sorgente: il motore gli serve per dividere i documenti da tradurre senza spezzare un blocco.
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

**Test.** `tests/test_rusca_markdown.py` controlla che le copie del modulo siano identiche, che la configurazione superi tutti i 652 esempi ufficiali di CommonMark 0.30 (`tests/data/commonmark-0.30-spec.json`) e che i link automatici cambino solo i 4 esempi previsti, che `parse_source()` dia gli stessi token di `parser()` su tutti gli esempi, le posizioni nel sorgente, la resa dei blocchi, le regole delle formule e dei link automatici e la validità del markup per Pango. `tests/test_ruscamark_markdown.py` controlla l’HTML, l’anteprima, il PDF (compresi i link cliccabili) e la resa live di RuscaMark, `tests/test_ruscatranslator_markdown.py` la divisione dei documenti di RuscaTranslator; senza GTK 4 e libadwaita si saltano. La suite di RuscaWriter (`tools/ruscawriter/tests/test_ruscawriter.py`) controlla i blocchi del libro, la regola dell’a capo, la regola dei titoli (formato per formato, compreso il ritorno dell’export Markdown reimportato), i comandi di formattazione e la coerenza fra anteprima, PDF, EPUB, ODT, DOCX, HTML e Markdown; `tools/ruscawriter/tests/test_format_gui.py` prova il menu «Formato», le scorciatoie, l’annullamento e il cambio di nome nella finestra vera. La cartella `tests/` sta nella radice del repository, non in `tools/`, che contiene solo programmi da impacchettare. I test si eseguono dalla radice del repository dopo ogni modifica del modulo:

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
- Scheda grafica: whisper-cli non sa elencare le schede, quindi `rusca_whisper.py` le chiede al caricatore Vulkan (`libvulkan.so.1`, tramite `ctypes`) in un processo a parte, perché un driver che si blocca non blocchi la finestra. Si elencano le schede integrate e dedicate, come fa ggml. La scheda scelta nelle Preferenze (“Scheda da usare”) si salva per nome e si passa al motore con `GGML_VK_VISIBLE_DEVICES`, che usa la stessa numerazione; se non c’è più, decide il motore. La build di ruscawhisper-engine controlla che ggml abbia ancora questa variabile.
- Lingue del parlato: quelle della sezione 9 con i codici di Whisper (24 voci, perché Whisper ha un solo cinese e un solo portoghese), più “Rileva la lingua”, che vale anche per le altre lingue che il modello conosce. Al primo avvio è scelta la lingua dell’interfaccia.

Durante lo sviluppo della 1.99.3 RuscaTranscriber si chiamava RuscaDubbing (App ID `org.ruscalinux.RuscaDubbing`, pacchetto `ruscadubbing`). Il pacchetto nuovo dichiara `Replaces` e `Conflicts: ruscadubbing`, così l’aggiornamento rimuove il vecchio; la metainfo dichiara il vecchio identificativo con `<replaces>`, e alla prima apertura le impostazioni passano da `~/.config/ruscadubbing/` a `~/.config/ruscatranscriber/`.

**Test.** `tests/test_ruscatranscriber.py` controlla i formati di uscita, la lettura di ciò che scrive `whisper-cli` e l’intero percorso di una trascrizione (compresi errore, interruzione e pulizia dei file di lavoro) con due programmi finti al posto di `ffmpeg` e di `whisper-cli`: non servono né il motore né un modello. Senza PyGObject si salta.

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
- **Moduli.** `rp_physics.py` (pallina, pareti, bumper, flipper; senza pygame), `rp_table.py` (il tavolo sul piano, 480 × 720 px, e le sue regole fisiche; senza pygame), `rp_view.py` (la prospettiva e il disegno), `rp_sound.py` (suoni sintetizzati all’avvio, onde quadre come il beeper degli anni ’80, nessun file audio), `ruscapinball.py` (partita, punteggi, HUD, lingue).
- **Prospettiva.** La fisica resta in 2D sul piano del tavolo. `project(x, y, z)` porta un punto del piano, a quota `z`, sullo schermo di 800 × 600 px: la riga vicina al giocatore è larga quanto il vero, quella in fondo 1,3 volte più stretta, con l’accorciamento vero della prospettiva (`unproject_row()` è l’inversa, verificata dal test). Il fondo del tavolo si disegna una volta in 2D e si deforma riga per riga in due versioni, tutto spento e tutto acceso: una lampada accesa è un solo blit del suo rettangolo dalla versione accesa (`StaticLayers`), e il test controlla che nessun rettangolo accenda un vicino. Numeri e lettere delle lampade si scrivono diritti, dopo la deformazione, perché le cifre piccole schiacciate si confondono (9 e 0). Bumper a fungo, flipper, pallina (con l’ombra) e pistone si disegnano in rilievo a ogni fotogramma; bumper e pallina in ordine di distanza.
- **Il tavolo «Amethyst».** Quattro corsie in alto (i flipper spostano le lampade accese); tre bumper; la **trappola del bonus** in alto a sinistra, indicata da una freccia: la pallina che ci passa abbastanza piano (`TRAP_MAX_SPEED`) resta presa 1,2 secondi e poi è ributtata verso i bumper; tre bersagli abbattibili a sinistra (moltiplicatore fino a 5×); i bersagli R-U-S-C-A a destra; l’**anello del bonus** al centro, nove lampade (1–9) attorno a 10, 20, 30 e SPECIAL, come nei tavoli elettromeccanici: il bonus va da 0 a 39 e a fine pallina le lampade si spengono una alla volta, 1.000 punti ciascuna per il moltiplicatore. Al bonus 39 si accende lo SPECIAL: la trappola dà 25.000 punti e una pallina extra. Le palline extra (R-U-S-C-A o SPECIAL) sono al massimo due a partita, una per pallina; la spia «Pallina extra» a sinistra resta accesa finché non si gioca. Il tilt spegne i flipper e azzera il bonus.
- **Palette.** Quella della sezione 4.1, più tre toni di ametista solo per il gioco: `#4e236b` (ombre, frontale), `#8e55b8` (cassa), `#cba6ec` (spigoli in luce, etichette). Contrasti verificati sul bordo `#2d0a1d`: `#cba6ec` 8,7:1, `#fff7f0` 16,9:1, `#f5b8d3` 10,8:1, `#f2a7c8` 9,5:1; `#cba6ec` sui riquadri `#40132c` 7,6:1; `#2d0a1d` sulle lampade accese `#f5b8d3` 10,8:1. `#8e55b8` è solo colore della cassa e del nome serigrafato sul tavolo, testo grande e decorativo (3,7:1 sul campo, sopra il 3:1 del testo grande).
- **Accessibilità.** Comandi da tastiera e da gamepad; i caratteri del tavolo e dell’HUD sono senza sfumature, come negli anni ’80, quelli dei pannelli normali; le scritte lunghe si rimpiccioliscono per entrare nel loro spazio (`fit()`). Lo stato delle lampade non è dato solo dal colore: una lampada accesa è piena, una spenta è vuota con il bordo.
- **Dati.** Record in `~/.local/share/ruscapinball/scores.json`, impostazioni (audio, effetto TV) in `~/.config/ruscapinball/settings.json`. Niente rete.

**Test.** `tests/test_ruscapinball.py` controlla la fisica (la pallina non esce dal tavolo e non resta ferma, il lancio, il cancelletto, i flipper), la trappola (cattura, calcio, quanto spesso la si prende giocando), l’anello del bonus, la prospettiva, che le lampade accese non tocchino le vicine, i contrasti, le regole della partita (SPECIAL e pallina extra, conteggio del bonus, tilt), il disegno di ogni schermata, i record, le lingue e l’assenza di moduli di rete. Le prove con pygame usano `SDL_VIDEODRIVER=dummy`; senza pygame si saltano.

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
| Formato pacchetti | deb, `Architecture: all` (`amd64` per ruscallama-engine, ruscawhisper-engine e ruscadiffusion-engine, che sono compilati) |
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

Nota: da GNOME 47 l’utente può scegliere un colore d’accento di sistema. I RuscaLinux OS Tools lo sostituiscono intenzionalmente con l’accento prugna/rosa per coerenza con l’identità della distribuzione.

### 4.5 Foglio di stile di riferimento

Ogni tool include lo stesso file `style.css`, installato in `/usr/share/ruscafoo/style.css`. Il file è identico in tutti i tool: le modifiche si fanno una volta e si copiano ovunque.

La palette chiara e quella scura sono legate alle classi `rusca-light` e `rusca-dark`, che il programma mette sulle proprie finestre seguendo `Adw.StyleManager:dark` (sezione 4.6). Non si usa `@media (prefers-color-scheme: dark)`: il modo in cui GTK valuta questa condizione per i fogli di stile delle applicazioni cambia tra GTK 4.18 (trixie) e GTK 4.20 e successivi, e nelle versioni recenti la palette scura non verrebbe applicata. Con le classi il risultato è identico su tutte le versioni.

```css
/* RuscaLinux OS Tools — style.css — 1.99.3 — GPL-3.0
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

```text
tools/ruscafoo/
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
Categories=GNOME;GTK;Utility;X-RuscaLinux-Tools;
Keywords=keyword;another;
Keywords[it]=parola;altra;
StartupNotify=true
StartupWMClass=org.ruscalinux.RuscaFoo
```

`Comment` e `Keywords` vanno tradotti in tutte le lingue della sezione 9 (`Comment[xx]=`), presi dai file di `lang/`. Il file va validato con `desktop-file-validate`.

Fra le `Categories` di ogni tool c’è sempre **`X-RuscaLinux-Tools`**: è la categoria della cartella **RuscaLinux Tools** della griglia delle applicazioni di GNOME, che raccoglie tutti i tool. La cartella la crea, una volta per utente e dopo le cartelle di GNOME, lo script `/usr/lib/ruscalinux/ruscalinux-tools-folder` della ISO (scritto da `steps/30-custom.sh`, avviato da `/etc/xdg/autostart/`): un elenco di cartelle predefinito con dconf impedirebbe a GNOME Shell 48 di creare le sue (Sistema, Utilità). Un tool nuovo entra nella cartella da solo, grazie alla categoria. GNOME Shell salva la posizione di ogni icona (`org.gnome.shell app-picker-layout`) e non la ricompatta: quando un aggiornamento toglie, rinomina o sposta in una cartella delle applicazioni restano dei buchi, e quelle nuove finiscono in una pagina in più. Succede anche al primo accesso, quando i tool entrano nella cartella: azzerare la disposizione non basta, perché GNOME ha già le icone in memoria e non le ridispone. Per questo `/usr/lib/ruscalinux/ruscalinux-app-grid` (sempre da `steps/30-custom.sh`, avviato a ogni accesso, 25 e 90 secondi dopo) scrive una disposizione completa e compatta: le voci salvate nel loro ordine, senza quelle che non esistono più, che stanno in una cartella o nel dash, poi le altre in ordine alfabetico, a pagine da 24 (tutte le griglie di GNOME Shell 48 ne tengono 24). Scrive solo se cambia qualcosa. I componenti senza interfaccia (ruscallama-engine, ruscawhisper-engine) non hanno file `.desktop`.

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
| EB Garamond e Courier Prime (caratteri tipografici) | inclusi nei sorgenti | SIL Open Font License 1.1 | `tools/ruscawriter/assets/`, installati in `/usr/share/ruscawriter/assets/` con il testo della licenza | RuscaWriter |
| llama.cpp (con ggml e le librerie che include: nlohmann/json e cpp-httplib MIT, xxHash BSD-2-Clause, stb, miniaudio, sha1 e sha256 di pubblico dominio) | ultima release stabile al momento della build (1.99.2: 0.9.0; 1.99.3: 1.0.0), scritta nella descrizione del pacchetto e in `/usr/share/doc/ruscallama-engine/README.md.gz` | MIT | Compilato nel pacchetto `ruscallama-engine`, in `/usr/lib/ruscallama-engine/` | RuscaLLama, RuscaTranslator, RuscaNarrator (`llama-tts`) |
| whisper.cpp (con ggml e le librerie compilate nei programmi impacchettati: sgemm di llamafile, MIT; miniaudio, pubblico dominio o MIT-0; stb_vorbis, pubblico dominio o MIT) | ultima release stabile al momento della build (1.99.3: 1.9.5), scritta nella descrizione del pacchetto e in `/usr/share/doc/ruscawhisper-engine/README.md.gz` | MIT | Compilato nel pacchetto `ruscawhisper-engine`, in `/usr/lib/ruscawhisper-engine/` | RuscaTranscriber |
| stable-diffusion.cpp (con la sua copia di ggml, leejet/ggml, e le librerie compilate in `sd-cli`: nlohmann/json, miniz e sgemm di llamafile, MIT; zip di kuba--, Unlicense; stb, pubblico dominio o MIT; darts-clone, BSD-3-Clause; Oniguruma, BSD-2-Clause; utf8proc, MIT e licenza dei dati Unicode) | ultima release al momento della build (tag `master-<numero>-<commit>`; 1.99.3: master-1106-532d2c1), scritta nella descrizione del pacchetto e in `/usr/share/doc/ruscadiffusion-engine/README.md.gz` | MIT | Compilato nel pacchetto `ruscadiffusion-engine`, in `/usr/lib/ruscadiffusion-engine/` | RuscaLLama (viste Immagini e Video) |
| Regola dell’evidenziato, porting del plugin markdown-it-mark (© Vitaly Puzrin e Alex Kocharin) con la struttura della regola del barrato di markdown-it-py (© ExecutableBookProject) | — | MIT (Expat) | `markdown_it_mark.py`, file a sé accanto a `rusca_markdown.py`; dichiarato nel file `copyright` del pacchetto, nella finestra Informazioni e nei manuali | RuscaLLama, RuscaMark, RuscaWriter, RuscaTranslator, RuscaNarrator |
| Esempi della specifica CommonMark (© John MacFarlane) | 0.30 | CC BY-SA 4.0 | `tests/data/commonmark-0.30-spec.json`, con `README.md`; solo per i test, non installati da nessun pacchetto | Test di `rusca_markdown.py` |

markdown-it-py, mdit-py-plugins e linkify-it-py (licenza MIT) non sono inclusi: sono dipendenze dei pacchetti, installate da Debian.

I file `copyright` di `ruscallama-engine`, `ruscawhisper-engine` e `ruscadiffusion-engine` riportano tutte queste licenze; solo gli script di costruzione e i profili AppArmor sono di RuscaLinux (GPL-3.0).

FFmpeg non è incluso: RuscaTranscriber e RuscaNarrator usano il comando `ffmpeg` del pacchetto Debian, che è una loro dipendenza.

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

**Eccezione: ruscapinball.** È un gioco: `Section: games`, il comando è `/usr/games/ruscapinball` (Debian Policy, 11.11) e la pagina di manuale sta nella sezione 6. Dipende da `python3 (>= 3.10)` e `python3-pygame (>= 2.1)`, raccomanda `fonts-dejavu-core`. Le `Categories` del `.desktop` sono `Game;ArcadeGame;X-RuscaLinux-Tools;`: il gioco sta sia fra i giochi sia nella cartella RuscaLinux Tools.

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

La versione di tutti i RuscaLinux OS Tools è identica alla versione di RuscaLinux, scritta in `release.conf` (`VERSION`). La stessa versione compare in `VER` di `make-deb.sh`, in `APP_VERSION` del programma, nel campo `Version` del pacchetto, nel nome del file deb e nella metainfo.

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
| RuscaCleaner, RuscaHub, RuscaLLama, RuscaTranslator, RuscaTranscriber, RuscaNarrator, RuscaPinball | No |

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

1. Nessun modulo di rete nel codice (`urllib`, `http`, `socket`, `requests`, `Gio.SocketClient` e simili). **Unica eccezione:** RuscaLLama e RuscaTranslator parlano con il proprio motore tramite `http.client` e `socket`, solo verso `127.0.0.1`, attraverso `rusca_engine.py` (vedi sotto).
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

Regole aggiuntive per il flipper (RuscaPinball):

| Regola | Come è applicata |
|---|---|
| Nessuna rete | I moduli non importano moduli di rete (lo controlla il test) |
| Dati | Solo i record e due impostazioni, in locale; il nome del record lo scrive il giocatore, al massimo 10 caratteri |
| Suoni | Sintetizzati in memoria all’avvio; se l’audio non c’è il gioco resta muto e non si ferma |

Dichiarazione:

Tutti i dati elaborati dai RuscaLinux OS Tools rimangono in locale.
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
12. Ha file `.desktop` e metainfo validi, con `StartupWMClass` uguale all’App ID e la categoria `X-RuscaLinux-Tools` (sezione 5.3).
13. Ha icona SVG e icona simbolica.
14. Ha `make-deb.sh` che produce un solo `ruscafoo-ruscalinux_<versione>_all.deb` (o `_amd64.deb` per ruscallama-engine, ruscawhisper-engine e ruscadiffusion-engine) e `SHA256SUMS` in `build-deb/`.
15. Ha la versione uguale a `VERSION` di `release.conf`.
16. È licenziato GPL-3.0, con componenti esterni dichiarati.
17. Non usa rete, telemetria o comandi pericolosi (per RuscaLLama e RuscaTranslator: rete solo verso 127.0.0.1, sezione 11, e le viste Immagini e Video di RuscaLLama non la usano in nessun modo; RuscaTranscriber e RuscaNarrator non usano la rete in nessun modo).
18. Se mostra, converte o divide Markdown, usa `rusca_markdown.py` (sezione 1.2), e i test di `tests/` passano.

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

## 🎱 RuscaPinball

Flipper con il tavolo «Amethyst», visto in prospettiva come nei flipper per home computer degli anni ’80.

1. Aprire RuscaPinball dalla cartella RuscaLinux Tools o fra i giochi; Spazio fa partire la partita.
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

Tutti i dati elaborati dai RuscaLinux OS Tools rimangono in locale. Nessun dato o file viene inviato a server remoti o su internet. Nessun tool contiene telemetria o comandi pericolosi per il sistema.

---

# 🇬🇧 15. ENGLISH GUIDE

## 📋 General information

| Field | Value |
|---|---|
| Project | RuscaLinux OS Tools |
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

Translation of Markdown documents between the 26 languages of RuscaLinux OS Tools: English, Italian, Simplified and Traditional Chinese, Spanish, Hindi, Arabic, Brazilian and European Portuguese, Russian, Japanese, German, French, Korean, Indonesian, Turkish, Polish, Dutch, Ukrainian, Czech, Vietnamese, Swedish, Romanian, Hungarian, Greek and Finnish.

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

## 🎱 RuscaPinball

Pinball with the “Amethyst” table, seen in perspective like the 1980s home computer pinball games.

1. Open RuscaPinball from the RuscaLinux Tools folder or from the games; Space starts a game.
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

All data processed by RuscaLinux OS Tools remains local. No data or files are sent to remote servers or over the internet. No tool contains telemetry or commands that could harm the system.

## 🤖 AI note

Development note: “Design, specifications and testing by the author; code written with the assistance of AI tools.”

---

Questo file è il riferimento unico per specifiche, interfaccia, tema, pacchetti, supporto linguistico, privacy, sicurezza e guida utente dei RuscaLinux OS Tools.
