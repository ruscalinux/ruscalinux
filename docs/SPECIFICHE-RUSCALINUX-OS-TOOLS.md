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
| Versione attuale | 1.99.2 |
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
| RuscaLLama | Chat con modelli linguistici locali | Assistente IA | `org.ruscalinux.RuscaLLama` | `ruscallama` | No |
| RuscaTranslator | Traduzione di documenti Markdown, con RAG ottimizzato per italiano ↔ inglese | Traduttore | `org.ruscalinux.RuscaTranslator` | `ruscatranslator` | No |
| ruscallama-engine | Motore che esegue i modelli per RuscaLLama e RuscaTranslator: **llama.cpp, software esterno** | Componente di sistema, senza interfaccia | — | `ruscallama-engine` | — |

### 1.1 Gli strumenti di intelligenza artificiale

RuscaLLama e RuscaTranslator usano modelli linguistici in formato GGUF che girano sul computer dell’utente, tramite **ruscallama-engine**.

- **ruscallama-engine è llama.cpp** (<https://github.com/ggml-org/llama.cpp>), software esterno con licenza MIT, copyright The ggml authors. RuscaLinux lo compila dal sorgente senza modificarne il codice, con il backend Vulkan (NVIDIA, AMD, Intel, con ripiego sulla CPU), **senza HTTPS** (`LLAMA_OPENSSL=OFF`) e senza interfaccia web: il motore non può scaricare modelli da Hugging Face né da altri siti. La versione è l’ultima release stabile di llama.cpp, verificata con il commit del tag e con un’impronta SHA-256 (sezioni 6 e 7).
- Il pacchetto del motore non ha interfaccia, quindi non ha traduzioni, icona né finestra Informazioni: lo dichiarano le finestre Informazioni di RuscaLLama e RuscaTranslator, nel gruppo “Componenti esterni”.
- I modelli non fanno parte dei pacchetti: l’utente li copia in `~/.local/share/ruscallama/models/` o l’amministratore in `/usr/share/ruscallama/models/`. Ogni modello ha la propria licenza, che l’utente deve rispettare.
- Il modulo `rusca_engine.py`, che avvia e interroga il motore, è identico nei due programmi, come `style.css` (si modifica una volta e si copia).
- Il modulo `rusca_markdown.py`, motore Markdown comune (sezione 1.2), è identico in RuscaLLama, RuscaMark, RuscaWriter (`src/ruscawriter/`) e RuscaTranslator, con la stessa regola. RuscaTranslator mostra il Markdown come sorgente: il motore gli serve per dividere i documenti da tradurre senza spezzare un blocco.
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

L’analisi del Markdown non si scrive a mano: la fa **markdown-it-py** (pacchetto `python3-markdown-it`, >= 3.0, che implementa CommonMark 0.30), con i plugin di `python3-mdit-py-plugins` (>= 0.4) e, per i link automatici, `python3-linkify-it` (>= 2.0), ristretto alle regole di GFM. Sono tutti in Debian Stable. L’evidenziato usa la regola del plugin `markdown-it-mark`, che Debian non pacchettizza: è un porting di poche righe dentro `rusca_markdown.py` (sezione 6). `rusca_markdown.py` configura il parser una volta sola per tutti i programmi (`parser()`) e ne traduce l’albero nei formati che servono all’interfaccia, come i blocchi con markup Pango di `parse_blocks()`. La conversione delle formule LaTeX in testo Unicode (`latex_to_pango()`, `latex_to_text()`) è invece codice di RuscaLinux, perché in Debian non c’è una libreria equivalente.

Regole:

1. Nessun programma interpreta il Markdown con espressioni regolari o con un parser proprio: usa `rusca_markdown.py`. Fanno eccezione gli strumenti che lavorano sul sorgente nell’editor e non interpretano il documento: quelli per riga di `rusca_markdown.py` (`table_at()`, `display_math_at()`, `has_inline_math()`, `sub_inline_math()`), da sostituire con le posizioni dei token di `parser()` (`token.map`), in RuscaMark i comandi sulle tabelle (`find_table_blocks()`, `align_table_lines()`), e in RuscaWriter `classify_md_line()`, che guarda una riga per volta per la ricucitura dei paragrafi spezzati (riconosce le righe con il motore). Un editor che deve sapere dove stanno i marcatori nel testo usa `parse_source()`: gli stessi token di `parser()`, con in più la posizione nel sorgente di ogni elemento in linea; è così che la resa live di RuscaMark riconosce la formattazione esattamente come l’anteprima.
2. L’HTML grezzo scritto nel Markdown resta testo (opzione `html` disattivata): le risposte dei modelli e i documenti aperti non possono inserire markup.
3. I programmi aprono solo link `http://`, `https://` e `mailto:`. markdown-it scarta già `javascript:`, `vbscript:`, `file:` e `data:` (salvo le immagini GIF, PNG, JPEG e WebP).
4. Una riga che continua il paragrafo (a capo morbido) si mostra andando a capo, come nel sorgente: CommonMark lascia questa scelta al programma.
5. Un blocco di codice non chiuso arriva fino alla fine del testo, e una formula `$$` non chiusa resta testo: la resa resta stabile mentre RuscaLLama riceve la risposta.
6. Le estensioni non alterano nessun esempio della specifica CommonMark, tranne i link automatici: per GFM rendono link anche gli indirizzi scritti senza `< >`, che CommonMark lascia come testo (4 esempi della sezione “Autolinks”).
7. Il motore non deve mai bloccarsi né fallire, qualunque testo riceva (un modello in RuscaLLama o chi scrive nella resa live può produrre testo malformato). Tre difetti dei plugin di mdit-py-plugins 0.4.2, trovati con prove su testi casuali, sono coperti in `rusca_markdown.py`: la regola dei blocchi `\[…\]` poteva entrare in un ciclo infinito e, dentro citazioni ed elenchi, leggere anche i `>` (lì vale solo su una riga; la protezione guarda le righe del sorgente e non `state.parentType`, che la regola dei titoli sottolineati di markdown-it-py 3.0 lascia sbagliato dopo un paragrafo); il plugin delle note poteva produrre token sbilanciati (un’ultima regola li riequilibra); le note in linea `^[testo]` facevano fallire l’analisi e sono disattivate. Ogni caso ha il suo test.
8. **Eccezione di RuscaWriter: l’a capo.** In CommonMark le righe consecutive formano un solo paragrafo; in RuscaWriter ogni a capo va a capo anche nel libro, come in un programma di videoscrittura, e la riga vuota separa i blocchi. L’analisi resta quella del motore: RuscaWriter impagina come righe distinte quelle che il motore separa con un a capo morbido (`softbreak`) o forzato (`hardbreak`). L’export Markdown aggiunge le righe vuote necessarie (`commonmark_paragraphs()`), così il file si legge allo stesso modo con RuscaMark e con ogni programma che segue CommonMark.
9. Quando un programma divide un documento Markdown in parti (come RuscaTranslator per la traduzione), usa le posizioni dei token di `parser()`, così non taglia mai un elenco, una tabella, una nota o un blocco di codice.

**Test.** `tests/test_rusca_markdown.py` controlla che le tre copie del modulo siano identiche, che la configurazione superi tutti i 652 esempi ufficiali di CommonMark 0.30 (`tests/data/commonmark-0.30-spec.json`) e che i link automatici cambino solo i 4 esempi previsti, che `parse_source()` dia gli stessi token di `parser()` su tutti gli esempi, le posizioni nel sorgente, la resa dei blocchi, le regole delle formule e dei link automatici e la validità del markup per Pango. `tests/test_ruscamark_markdown.py` controlla l’HTML, l’anteprima, il PDF (compresi i link cliccabili) e la resa live di RuscaMark, `tests/test_ruscatranslator_markdown.py` la divisione dei documenti di RuscaTranslator; senza GTK 4 e libadwaita si saltano. La suite di RuscaWriter (`tools/ruscawriter/tests/test_ruscawriter.py`) controlla i blocchi del libro, la regola dell’a capo e la coerenza fra anteprima, PDF, EPUB, ODT, DOCX, HTML e Markdown. La cartella `tests/` sta nella radice del repository, non in `tools/`, che contiene solo programmi da impacchettare. I test si eseguono dalla radice del repository dopo ogni modifica del modulo:

```bash
python3 -m unittest tests/test_rusca_markdown.py tests/test_ruscamark_markdown.py tests/test_ruscatranslator_markdown.py
```

**Stato nella versione 1.99.2.** Tutti i programmi che leggono Markdown usano il motore comune: RuscaLLama per la chat, la conversazione salvata in HTML (`render_html()`) e il salvataggio dei blocchi di codice (`code_blocks()`); RuscaMark per anteprima, export HTML, export PDF (`MarkdownDoc`) e resa live (`live_elements()`); RuscaWriter per tutti gli export, l’anteprima e l’evidenziazione (`book_blocks()`, `highlight_spans()`); RuscaTranslator per dividere i documenti da tradurre (`block_ranges()`). Fanno eccezione solo gli strumenti per riga della regola 1 e l’export TXT di RuscaWriter, che scrive il sorgente Markdown con formule e tabelle convertite in testo.

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
| Formato pacchetti | deb, `Architecture: all` (`amd64` per ruscallama-engine, che è compilato) |
| Versione tool | 1.99.2 |

Regole tecniche:

1. Usare Python 3 moderno, senza sintassi o moduli deprecati.
2. Usare GTK 4 con **libadwaita** per l’interfaccia. libadwaita fa parte della piattaforma GNOME ed è già presente in RuscaLinux: non conta come dipendenza esterna aggiuntiva, ed è ciò che rende un’applicazione “nativa” in GNOME (stile, modalità scura, adattività, dialoghi standard).
3. Usare solo librerie disponibili nei repository Debian Stable. Nessun pacchetto da PyPI, nessun `pip install`.
4. Preferire GLib/Gio per file, cartelle, cestino e impostazioni (`Gio.File`, `Gio.FileMonitor`, `Gio.File.trash`) invece di soluzioni esterne.
5. Le operazioni lunghe (scansioni, copie, calcoli) non devono bloccare l’interfaccia: eseguirle in un thread o con API asincrone di Gio e aggiornare la UI con `GLib.idle_add`.
6. Mantenere il codice semplice, stabile e mantenibile. Un file principale è accettabile per tool piccoli; oltre le 1.500 righe circa, dividere in moduli.
7. La versione dei tool deve essere identica alla versione di RuscaLinux (vedi sezione 8).

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
/* RuscaLinux OS Tools — style.css — 1.99.2 — GPL-3.0
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
APP_VERSION = "1.99.2"
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
Categories=GNOME;GTK;Utility;
Keywords=keyword;another;
Keywords[it]=parola;altra;
StartupNotify=true
StartupWMClass=org.ruscalinux.RuscaFoo
```

`Comment` e `Keywords` vanno tradotti in tutte le lingue della sezione 9 (`Comment[xx]=`), presi dai file di `lang/`. Il file va validato con `desktop-file-validate`.

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
    <release version="1.99.2" date="2026-01-01"/>
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

Componenti esterni in uso:

| Componente | Versione | Licenza | Dove | Usato da |
|---|---|---|---|---|
| EB Garamond e Courier Prime (caratteri tipografici) | inclusi nei sorgenti | SIL Open Font License 1.1 | `tools/ruscawriter/assets/`, installati in `/usr/share/ruscawriter/assets/` con il testo della licenza | RuscaWriter |
| llama.cpp (con ggml e le librerie che include: nlohmann/json e cpp-httplib MIT, xxHash BSD-2-Clause, stb, miniaudio, sha1 e sha256 di pubblico dominio) | ultima release stabile al momento della build (1.99.2: 0.9.0), scritta nella descrizione del pacchetto e in `/usr/share/doc/ruscallama-engine/README.md.gz` | MIT | Compilato nel pacchetto `ruscallama-engine`, in `/usr/lib/ruscallama-engine/` | RuscaLLama, RuscaTranslator |
| Regola dell’evidenziato, porting del plugin markdown-it-mark (© Vitaly Puzrin e Alex Kocharin) | — | MIT | `_mark_plugin` in `rusca_markdown.py`; indicato nella finestra Informazioni e nei manuali dei quattro programmi | RuscaLLama, RuscaMark, RuscaWriter, RuscaTranslator |
| Esempi della specifica CommonMark (© John MacFarlane) | 0.30 | CC BY-SA 4.0 | `tests/data/commonmark-0.30-spec.json`, con `README.md`; solo per i test, non installati da nessun pacchetto | Test di `rusca_markdown.py` |

markdown-it-py, mdit-py-plugins e linkify-it-py (licenza MIT) non sono inclusi: sono dipendenze dei pacchetti, installate da Debian.

Il file `copyright` di `ruscallama-engine` riporta tutte queste licenze; solo lo script di costruzione e il profilo AppArmor sono di RuscaLinux (GPL-3.0).

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

**Eccezione: ruscallama-engine.** È codice compilato, quindi:

1. architettura `amd64`; file `ruscallama-engine-ruscalinux_<versione>_amd64.deb`;
2. versione del pacchetto uguale a quella di RuscaLinux; la versione di llama.cpp è scritta nella descrizione e in `/usr/share/doc/ruscallama-engine/README.md.gz`;
3. si costruisce l’ultima release stabile di llama.cpp (tag `vX.Y.Z` indicato da GitHub come “Latest”), trovata da `ultima-versione.sh`; `RUSCALLAMA_LLAMA_VERSION` ne fissa una. Il sorgente si scarica da GitHub solo durante la costruzione; il commit dell’archivio deve coincidere con quello del tag, e l’impronta SHA-256 si registra in `checksums/` alla prima costruzione di ogni versione (il file va aggiunto al repository) e si confronta nelle successive;
4. al posto della prova manuale, la build controlla che `llama-server` accetti tutte le opzioni usate da RuscaLLama e RuscaTranslator e che nessuna libreria nuova in `vendor/` manchi dal file `copyright`; una release uscita da meno di 14 giorni dà un avviso, e va provata con i due programmi prima di pubblicare la ISO;
5. compilazione senza rete (`unshare -rn`), con `LLAMA_OPENSSL=OFF`, `LLAMA_BUILD_UI=OFF`, `LLAMA_USE_PREBUILT_UI=OFF` e `LLAMA_CONNECT=OFF`; la build si ferma se i binari usano OpenSSL o curl;
6. binari e librerie private in `/usr/lib/ruscallama-engine/` (non in `/opt`, che Debian riserva ad altro), con RUNPATH su quella cartella, senza simboli di debug e con i flag di sicurezza di `dpkg-buildflags`;
7. dipendenze calcolate con `dpkg-shlibdeps`;
8. compilazione tenuta in cache (`~/.cache/ruscalinux/ruscallama-engine/`): le build successive rifanno solo il pacchetto;
9. dipendenze di costruzione: `build-essential cmake pkg-config dpkg-dev wget git libvulkan-dev glslc spirv-headers`.

Esempio di output:

```text
build-deb/
├── ruscacleaner-ruscalinux_1.99.2_all.deb
└── SHA256SUMS
```

Esempio di file `DEBIAN/control`:

```text
Package: ruscafoo
Version: 1.99.2
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

RuscaLLama, RuscaMark, RuscaWriter e RuscaTranslator, che includono `rusca_markdown.py` (sezione 1.2), aggiungono a `Depends`:

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
1.99.2
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
| RuscaCleaner, RuscaHub, RuscaLLama, RuscaTranslator | No |

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
12. Ha file `.desktop` e metainfo validi, con `StartupWMClass` uguale all’App ID.
13. Ha icona SVG e icona simbolica.
14. Ha `make-deb.sh` che produce un solo `ruscafoo-ruscalinux_<versione>_all.deb` (o `_amd64.deb` per ruscallama-engine) e `SHA256SUMS` in `build-deb/`.
15. Ha la versione uguale a `VERSION` di `release.conf`.
16. È licenziato GPL-3.0, con componenti esterni dichiarati.
17. Non usa rete, telemetria o comandi pericolosi (per RuscaLLama e RuscaTranslator: rete solo verso 127.0.0.1, sezione 11).
18. Se mostra, converte o divide Markdown, usa `rusca_markdown.py` (sezione 1.2), e i test di `tests/` passano.

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
sudo apt install ./nome-tool-ruscalinux_1.99.2_all.deb
```

Installazione alternativa:

```bash
sudo dpkg -i nome-tool-ruscalinux_1.99.2_all.deb
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
2. Aggiungere i capitoli con **+** e scrivere in Markdown; a destra le note di ogni capitolo.
3. Impostare formato e margini dal menu principale → Impostazione pagina.
4. Esportare dal menu principale → Esporta: PDF, EPUB, AZW3, ODT, DOCX, HTML, Markdown o testo.

Controllo ortografico e sillabazione usano solo dizionari locali (incluso l’inglese britannico tramite `hunspell-en-gb` e `hyphen-en-gb`). Il testo non viene mai inviato online.

## 💬 RuscaLLama

Chat con modelli linguistici che girano su questo computer.

1. Copiare un modello GGUF in `~/.local/share/ruscallama/models/` (dal pannello delle impostazioni: “Apri la cartella dei modelli”).
2. Aprire RuscaLLama e scegliere il modello nel pannello laterale (F9).
3. Scrivere un messaggio e premere Invio: il motore parte da solo.
4. Copiare o salvare le risposte dal menu di ogni risposta; salvare la conversazione con Ctrl+S.

## 🌐 RuscaTranslator

Traduzione di documenti Markdown tra le 26 lingue della sezione 9: inglese, italiano, cinese semplificato e tradizionale, spagnolo, hindi, arabo, portoghese brasiliano ed europeo, russo, giapponese, tedesco, francese, coreano, indonesiano, turco, polacco, olandese, ucraino, ceco, vietnamita, svedese, rumeno, ungherese, greco e finlandese.

1. Aprire un documento (Ctrl+O) o trascinarlo nel riquadro “Originale”.
2. Scegliere lingua di partenza (o “Rileva la lingua”), lingua d’arrivo e tipo di testo.
3. Premere “Traduci” (Ctrl+Invio).
4. Rileggere la traduzione nel riquadro di destra e salvarla (Ctrl+S).

Tra italiano e inglese il programma usa una base di conoscenza linguistica, un glossario del documento e la memoria delle traduzioni salvate.

Entrambi i programmi usano **ruscallama-engine**, cioè llama.cpp, software esterno con licenza MIT. Tutto resta sul computer.

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
| Current version | 1.99.2 |
| Code license | GPL-3.0 — https://www.gnu.org/licenses/gpl-3.0.html |

## 🛠️ Included tools

| Tool | Description |
|---|---|
| RuscaCleaner | GNOME desktop privacy and cleaning |
| RuscaHub | AppImage management |
| RuscaMark | Markdown editing |
| RuscaWriter | Writing and typesetting books |
| RuscaLLama | Chat with local language models |
| RuscaTranslator | Translation of Markdown documents, with a RAG optimized for Italian ↔ English |
| ruscallama-engine | Engine that runs the models: llama.cpp, an external component (MIT) |

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
sudo apt install ./tool-name-ruscalinux_1.99.2_all.deb
```

Alternative installation:

```bash
sudo dpkg -i tool-name-ruscalinux_1.99.2_all.deb
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
2. Add chapters with **+** and write in Markdown; each chapter's notes are on the right.
3. Set format and margins from the main menu → Page setup.
4. Export from the main menu → Export: PDF, EPUB, AZW3, ODT, DOCX, HTML, Markdown or text.

Spell checking and hyphenation use only local dictionaries (including British English through `hunspell-en-gb` and `hyphen-en-gb`). Text is never sent online.

## 💬 RuscaLLama

Chat with language models that run on this computer.

1. Copy a GGUF model into `~/.local/share/ruscallama/models/` (from the settings panel: "Open the Models Folder").
2. Open RuscaLLama and choose the model in the side panel (F9).
3. Write a message and press Enter: the engine starts on its own.
4. Copy or save answers from each answer's menu; save the conversation with Ctrl+S.

## 🌐 RuscaTranslator

Translation of Markdown documents between the 26 languages of RuscaLinux OS Tools: English, Italian, Simplified and Traditional Chinese, Spanish, Hindi, Arabic, Brazilian and European Portuguese, Russian, Japanese, German, French, Korean, Indonesian, Turkish, Polish, Dutch, Ukrainian, Czech, Vietnamese, Swedish, Romanian, Hungarian, Greek and Finnish.

1. Open a document (Ctrl+O) or drag it onto the "Original" pane.
2. Choose the source language (or "Detect language"), the target language and the text type.
3. Press "Translate" (Ctrl+Enter).
4. Review the translation in the right pane and save it (Ctrl+S).

Between Italian and English the program uses a linguistic knowledge base, a document glossary and the memory of saved translations.

Both programs use **ruscallama-engine**, that is llama.cpp, an external component under the MIT license. Everything stays on the computer.

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
