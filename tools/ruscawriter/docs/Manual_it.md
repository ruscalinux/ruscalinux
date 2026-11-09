# RuscaWriter — Manuale utente

| Campo | Valore |
|---|---|
| Programma | RuscaWriter |
| Versione | 1.99.2 |
| Progetto | RuscaLinux OS Tools |
| Sito | https://www.ruscalinux.org |
| Sorgenti | https://github.com/ruscalinux/ruscalinux (cartella `tools/ruscawriter`) |
| Contatti | info@ruscalinux.org |
| Autore | Nunzio Curcuruto (ruscalinux-dev) |
| Licenza | GPL-3.0 o successiva |

---

## 1. Che cos'è

RuscaWriter è un ambiente di scrittura per libri, pensato per la saggistica. La finestra ha tre colonne: a sinistra l'elenco dei capitoli, al centro il testo, a destra le note del capitolo. Si scrive in Markdown, e lo stesso programma impagina il risultato e lo esporta in PDF, EPUB, AZW3, ODT, DOCX, HTML, Markdown o TXT.

Il programma lavora interamente in locale: non si collega mai alla rete.

---

## 2. Installazione

Requisiti: RuscaLinux o Debian Stable, GNOME, GTK 4.18 e libadwaita 1.7 o successivi, Python 3.10 o successivo. In RuscaLinux RuscaWriter è già installato.

Verifica l'integrità del pacchetto e installalo:

```bash
sha256sum -c SHA256SUMS
sudo apt install ./ruscawriter-ruscalinux_1.99.2_all.deb
```

In alternativa, `sudo dpkg -i` seguito da `sudo apt -f install` per le dipendenze mancanti.

Pacchetti facoltativi, consigliati dal deb:

| Pacchetto | A cosa serve |
|---|---|
| `gir1.2-gtksource-5` | Evidenziazione del Markdown nell'editor |
| `gir1.2-spelling-1` | Controllo ortografico |
| `hunspell-it`, `hunspell-en-gb`, … | Dizionari ortografici per lingua |
| `hyphen-it`, `hyphen-en-gb`, … | Sillabazione nel PDF |
| `python3-pyphen` | Motore di sillabazione del PDF |
| `python3-pil` | Generatore di copertine |
| `calibre` | Solo per l'esportazione AZW3 (Kindle) |

---

## 3. Avvio e finestra

Dal menu delle applicazioni di GNOME, cercando «RuscaWriter» in Attività, con un doppio clic su un file `.rwr`, oppure da terminale:

```bash
ruscawriter                 # avvia il programma
ruscawriter libro.rwr       # apre direttamente un progetto
```

All'avvio, se non apri un file, RuscaWriter chiede se creare un progetto nuovo o aprirne uno esistente.

La finestra:

- **Barra del titolo**: a sinistra mostra/nascondi i capitoli e **+** (nuovo capitolo); al centro il titolo del progetto; a destra mostra/nascondi le note, anteprima, Salva e il **menu principale**.
- **Menu principale**: in alto nuovo progetto, apri, importa ed esporta; poi il sottomenu **Capitolo**, sezioni editoriali, impostazione pagina e obiettivo di parole; poi ricerca, dizionari e ricucitura dei paragrafi; poi i sottomenu **Visualizza** e **Aspetto**; in fondo guida al Markdown, scorciatoie da tastiera e informazioni.
- **Tre colonne**: capitoli (con le frecce per spostarli), testo, note del capitolo.
- **Barra in basso**: parole del capitolo, caratteri e pagine stimate, totale del progetto, lingua del controllo ortografico e dimensione del testo.

La lingua dell'interfaccia è quella del sistema (Impostazioni → Sistema → Regione e lingua), fra le lingue in cui sono tradotti i RuscaLinux OS Tools. Chi usa lo slovacco vede il ceco; se manca una traduzione si usa l'inglese.

---

## 4. Il progetto

Un progetto è un file `.rwr`: un archivio `tar.gz` che contiene un file Markdown per capitolo, uno per le note di ogni capitolo, i metadati in JSON e le immagini allegate. Il testo resta recuperabile con strumenti comuni anche senza RuscaWriter.

| Azione | Menu | Scorciatoia |
|---|---|---|
| Nuovo progetto | Menu principale → Nuovo progetto | Ctrl+N |
| Apri | Menu principale → Apri | Ctrl+O |
| Salva | Pulsante Salva nella barra del titolo | Ctrl+S |
| Importa capitoli da file .md/.txt | Menu principale → Importa come capitoli | Ctrl+I |
| Sezioni editoriali (frontespizio, colophon, copertina) | Menu principale → Sezioni editoriali | — |
| Esci | — | Ctrl+Q |

**Salvataggio automatico.** Ogni 60 secondi, se ci sono modifiche, RuscaWriter scrive una copia `nomefile.rwr.autosave` accanto al progetto. Se il programma si chiude in modo anomalo, alla riapertura propone di recuperarla. Un salvataggio normale elimina la copia.

**Salvataggio sicuro.** Il progetto viene scritto prima in un file provvisorio nella stessa cartella e poi rinominato. Un'interruzione lascia quindi il progetto vecchio o quello nuovo, mai un file a metà.

---

## 5. Capitoli e scrittura

| Azione | Scorciatoia |
|---|---|
| Nuovo capitolo | Ctrl+Maiusc+N |
| Rinomina capitolo | F2 |
| Sposta su / giù | Ctrl+Maiusc+↑ / ↓ |
| Trova e sostituisci | Ctrl+F |
| Inserisci immagine (PNG, JPEG, WebP) | Ctrl+Maiusc+I |
| Anteprima del capitolo | Ctrl+E |
| Anteprima dell'intero libro | Ctrl+Maiusc+E |
| Mostra le interruzioni di riga | Ctrl+Maiusc+B |
| Guida al Markdown | Maiusc+F1 |
| Cerca la parola nel dizionario | Ctrl+D oppure Ctrl+clic |

**Ricuci i paragrafi** (menu principale) unisce le righe spezzate a mano, per esempio nei testi incollati da un PDF.

Il Markdown segue lo standard CommonMark, come in RuscaMark e RuscaLLama: anteprima, evidenziazione ed export lo leggono tutti allo stesso modo. Oltre a titoli, grassetto, corsivo, elenchi, citazioni, link, immagini e tabelle si possono usare blocchi di codice tra tre apici, liste di attività (`- [x]`), note a piè di pagina (`testo[^1]` e, più sotto, `[^1]: la nota`, che finiscono in fondo al capitolo) e formule (`$x^2$`, che diventano simboli). Una sola regola è diversa da CommonMark, perché in un libro è più naturale: **ogni a capo va a capo anche nel libro**, e le righe scritte una sotto l'altra non si fondono in un unico paragrafo. Una riga vuota separa i blocchi di testo. Esportando in Markdown, RuscaWriter aggiunge le righe vuote che servono perché il file si legga allo stesso modo con qualunque programma che segue CommonMark.

---

## 6. Vista e aspetto

| Azione | Scorciatoia |
|---|---|
| Mostra/nascondi la colonna dei capitoli | Ctrl+L |
| Mostra/nascondi la colonna delle note | Ctrl+R |
| Schermo intero | F11 |
| Ingrandisci / riduci il carattere | Ctrl++ / Ctrl+− |
| Passa da chiaro a scuro | Ctrl+Maiusc+D |
| Scorciatoie da tastiera | Ctrl+? |

Dal sottomenu Visualizza si sceglie anche il carattere di scrittura (Caratteri…) e la **larghezza della colonna**: *Normale* (68 caratteri per riga, la misura dei libri, predefinita) o *Larga* (80). La colonna resta della stessa larghezza quando sposti o nascondi le colonne laterali e quando ridimensioni la finestra: si ricentra soltanto. Se lo spazio è minore, il testo occupa tutto lo spazio disponibile.

**Aspetto.** Il sottomenu Aspetto offre tre scelte. *Automatico* segue la modalità chiara o scura di GNOME (Impostazioni → Aspetto) e cambia insieme al sistema, anche mentre scrivi. *Chiaro* e *Scuro* fissano la scelta. Ctrl+Maiusc+D passa dall'uno all'altro. Barre, menu e dialoghi seguono il tema comune dei RuscaLinux OS Tools.

**Temi della pagina.** Nello stesso sottomenu si sceglie il colore della pagina di scrittura, dell'anteprima e delle note. Sono due, ciascuno in versione chiara e scura:

| Tema | Carattere |
|---|---|
| Ametista | I colori ufficiali di RuscaLinux: pagina bianca con un soffio di rosa, titoli e codice prugna; nello scuro pagina prugna e titoli rosa. È il predefinito. |
| Classico | Lo stile di uno studio di scrittura professionale: pagina bianca nitida, inchiostro quasi nero, grigi freddi e titoli, codice e selezione in blu; nello scuro pagina carbone con testo grigio chiaro e blu smorzato. |

In entrambi il testo da scrivere sta intorno a 11:1, titoli, codice e note ad almeno 7:1 e i segni del Markdown (`**`, `#`, `` ` ``) ad almeno 4,5:1: smorzati, ma sempre leggibili.

---

## 7. Controllo ortografico

Si attiva quando sono installati `gir1.2-spelling-1` e un dizionario Hunspell. La lingua si sceglie per documento e viene salvata nel progetto. Gli apostrofi delle elisioni (per esempio *dell'anima*) sono gestiti correttamente. Per l'inglese britannico installa `hunspell-en-gb` e `hyphen-en-gb`.

---

## 8. Dizionari MDict

RuscaWriter consulta dizionari nel formato MDict senza bisogno di programmi aggiuntivi.

**Aggiungere un dizionario.** Apri menu principale → Dizionari. Ci sono due modi.

- **Aggiungi cartella…** è il modo consigliato: scegli la cartella del dizionario così come l'hai scaricata. RuscaWriter la copia intera nella libreria e aggiunge ogni `.mdx` che contiene, con i suoi `.mdd`, l'icona e i fogli di stile.
- **Aggiungi** sceglie un singolo file. Puoi indicare il `.mdx`, il `.mdd` o il `.png`: il programma prende sempre il `.mdx` con lo stesso nome e porta con sé i file che gli appartengono.

Un dizionario MDict è spesso una famiglia di file con lo stesso nome:

| File | Contenuto | Uso in RuscaWriter |
|---|---|---|
| `nome.mdx` | Lemmi e definizioni | Il dizionario vero e proprio |
| `nome.mdd`, `nome.1.mdd`, … | Immagini, suoni, fogli di stile | Le immagini delle voci, in «Mostra tutto» |
| `nome.png` | Icona | Accanto al nome, nell'elenco e nel foglietto |
| `nome.css` | Stile | Copiato insieme al dizionario |

I suoni e i fogli di stile non vengono usati: il foglietto mostra il testo con grassetto e corsivo, non una pagina web. Le immagini vengono prese solo dagli archivi `.mdd`, mai da internet.

**Formati supportati:** motore MDict 1.x, 2.x e 3.0; compressione assente, zlib o LZO; codifiche UTF-8, UTF-16, GB18030 e Big5; indice delle chiavi protetto. Non sono supportati i dizionari registrati, cioè quelli che richiedono un codice d'acquisto: vengono rifiutati con un messaggio chiaro.

**Prima apertura.** La prima volta il dizionario viene indicizzato in background, con una barra di avanzamento. L'indice resta in `~/.cache/ruscawriter/mdict/`, quindi le volte successive il dizionario è subito pronto. Se cancelli quella cartella, l'indice viene ricostruito.

**Consultazione.** Ci sono tre modi:

| Come | Cosa fare |
|---|---|
| Tastiera | Cursore sulla parola (o parola selezionata) e **Ctrl+D** |
| Mouse | **Ctrl+clic** sulla parola |
| Menu | Clic destro sulla parola → **Cerca nel dizionario** |

Accanto alla parola compare un piccolo foglietto con la definizione. **Mostra tutto** apre la voce completa con le sue immagini; se è lunga, scorre dentro il foglietto.

Per chiudere il foglietto basta un clic sulla **✕**, un clic in un punto qualsiasi del testo, il tasto **Esc**, oppure ricominciare a scrivere.

Se la parola esatta non c'è, RuscaWriter prova le forme di dizionario: *case* → *casa*, *houses* → *house*. Altrimenti mostra il lemma più vicino, indicando chiaramente che non è la parola cercata.

**Cartella dei dizionari.** Per impostazione predefinita i file aggiunti vengono copiati in `~/.local/share/ruscawriter/dictionaries/`, e le cartelle vi diventano sottocartelle. Quando togli un dizionario puoi cancellarne anche i file: vengono eliminati il `.mdx` con i suoi file compagni oppure, per una cartella copiata, esattamente i file copiati. Niente fuori dalla libreria viene mai cancellato. Nella stessa finestra si può cambiare cartella o disattivare la copia. L'ordine dell'elenco è l'ordine di consultazione e si modifica con le frecce.

**Se un dizionario non funziona.** Nell'elenco compare «⚠» seguito dal motivo. Gli altri dizionari continuano a funzionare. Se non ne funziona nessuno, il messaggio appare in una finestra.

---

## 9. Esportazione

Menu principale → Esporta:

| Formato | Note |
|---|---|
| PDF | Formati di pagina da libro, margini di rilegatura, testo giustificato, font incorporati. La sillabazione richiede `python3-pyphen` e `hyphen-<lingua>`. |
| EPUB | Con copertina, frontespizio, colophon e indice |
| AZW3 | Richiede Calibre (`ebook-convert`), avviato in locale |
| ODT, DOCX | Per LibreOffice o Word |
| HTML, Markdown, TXT | Formati aperti e semplici |

### Impostazione pagina

Menu principale → Impostazione pagina (Ctrl+Maiusc+P) decide formato e margini del libro. Lo stesso dialogo si apre prima di ogni esportazione PDF, insieme alle opzioni di giustificazione e sillabazione.

| Campo | Significato |
|---|---|
| Formato | A5, 17 × 24 cm, A4, 5 × 8 pollici… |
| Modello | *Margini del formato* (quelli studiati per ciascun formato), *Canone classico* (interno, superiore, esterno e inferiore in proporzione 2:3:4:6, come nei libri tradizionali), *Esterno ampio per le note*, *Manoscritto* (2,54 cm su ogni lato). Modificando un valore il modello diventa *Personalizzati*. |
| Pagine affiancate | Margini speculari: l'interno sta a sinistra sulle pagine dispari e a destra su quelle pari. Senza questa opzione i margini sono semplicemente sinistro e destro. |
| Superiore, inferiore, interno, esterno | I quattro margini, in millimetri, centimetri o pollici. |
| Rilegatura | Spazio aggiunto al lato interno per la piega o la colla della rilegatura. |

L'anteprima mostra la doppia pagina con la gabbia del testo. Sotto si leggono la misura della gabbia e le battute per riga: fra 45 e 75 la lettura è comoda, e fuori da questa fascia compare un consiglio. Un margine sotto i 5 mm, o una gabbia troppo stretta o troppo bassa, spegne il pulsante e spiega il motivo.

I margini si salvano **nel documento**, un insieme per ogni formato: un libro riaperto si stampa come prima. Valgono per il PDF e anche per ODT e DOCX, che si aprono in LibreOffice o in Word già impaginati. Testatine e numeri di pagina si centrano sulla gabbia del testo.

---

## 10. File usati dal programma

| Percorso | Contenuto |
|---|---|
| `~/.config/ruscawriter/settings.json` | Impostazioni |
| `~/.local/share/ruscawriter/dictionaries/` | Dizionari aggiunti |
| `~/.cache/ruscawriter/mdict/` | Indici dei dizionari, eliminabili |
| `<progetto>.rwr.autosave` | Copia automatica, accanto al progetto |
| `/usr/share/ruscawriter/` | Programma installato |
| `/usr/share/doc/ruscawriter/` | Questo manuale e la versione inglese |

---

## 11. Risoluzione dei problemi

| Problema | Cosa fare |
|---|---|
| Il programma non parte | Verifica che siano presenti `python3`, `python3-gi` e `gir1.2-gtk-4.0`; avvia `ruscawriter` da terminale per leggere l'errore |
| Niente controllo ortografico | Installa `gir1.2-spelling-1` e il dizionario `hunspell-<lingua>` |
| PDF senza sillabazione | Installa `python3-pyphen` e `hyphen-<lingua>` |
| Esportazione AZW3 impossibile | Installa Calibre, oppure esporta in EPUB |
| Dizionario con «⚠» | Leggi il motivo nell'elenco; verifica di aver scelto il `.mdx` e non il `.mdd` |
| Impostazioni strane | Chiudi il programma e rinomina `~/.config/ruscawriter/settings.json` |
| Pacchetto sospetto | `sha256sum -c SHA256SUMS`, poi reinstalla |

---

## 12. Privacy e sicurezza

### Principi

| Principio | Regola |
|---|---|
| Dati elaborati | Solo in locale |
| Invio a server remoti | No |
| Invio su internet | No |
| Telemetria | No |
| Comandi pericolosi o dannosi | No |
| Raccolta di dati personali | No |
| Operazioni sensibili | Chiare e sotto il controllo dell'utente |

Tutti i dati elaborati da RuscaWriter rimangono in locale. Nessun dato o file viene inviato a server remoti né su internet. Il programma non contiene comandi pericolosi o dannosi per il sistema operativo.

### Come è realizzato

- **Nessuna rete.** Il codice non apre connessioni. I due collegamenti nella finestra Informazioni (sito e sorgenti) si aprono nel browser solo se li clicchi.
- **Progetti `.rwr`.** L'archivio viene letto in memoria e non viene mai estratto su disco, così un percorso malevolo all'interno (per esempio `../../.bashrc`) non può scrivere da nessuna parte. Ci sono anche dei limiti (20.000 file e 1 GB decompresso) contro gli archivi costruiti per esaurire la memoria. Un testo con codifica errata viene aperto lo stesso, senza crash.
- **Dizionari `.mdx` e `.mdd`.** Sono trattati come file non fidati. Ogni dimensione letta viene confrontata con un tetto prima di allocare memoria, la decompressione ha un limite per blocco e ogni lettura e rimando del decompressore LZO è controllato. Il testo delle definizioni viene ripulito prima di essere mostrato: niente script, niente stili, niente collegamenti esterni. Le immagini arrivano solo dagli archivi `.mdd` del dizionario (mai da internet né da altri file del disco); se ne decodificano solo i formati PNG, JPEG, GIF e WebP, fino a 8 MB ciascuna. Copiando una cartella, i collegamenti simbolici non vengono seguiti. Il programma è stato provato su centinaia di file corrotti di proposito: rispondono sempre con un messaggio d'errore, mai con un crash.
- **Cifrari.** RIPEMD-128, Salsa20/8 e XXH64 sono presenti solo per *leggere* i dizionari che li usano, mai per proteggere dati dell'utente.
- **Salvataggi atomici.** Progetti e impostazioni vengono scritti in un file provvisorio e poi rinominati.
- **Programmi esterni.** L'unico è Calibre (`ebook-convert`), avviato solo quando esporti in AZW3, senza shell e con gli argomenti passati come elenco, con un limite di 5 minuti.
- **Permessi.** I file di progetto vengono creati leggibili solo dal proprietario (0600). Il programma non richiede né usa privilegi di amministratore. Solo l'installazione del pacchetto richiede `sudo`.
- **Dipendenze.** Solo la libreria standard di Python e GTK 4. I componenti facoltativi vengono dai repository Debian.
- **Integrità.** Ogni pacchetto è accompagnato da `SHA256SUMS`: verificalo sempre prima di installare.

### Segnalare un problema di sicurezza

Scrivi a **info@ruscalinux.org** indicando la versione (menu principale → Informazioni), i passi per riprodurre il problema e, se puoi, un file di esempio. Non pubblicare il dettaglio della vulnerabilità prima che sia corretta. È supportata solo l'ultima versione pubblicata.

---

## 13. Licenze

Il codice è distribuito con licenza GPL-3.0 o successiva: https://www.gnu.org/licenses/gpl-3.0.html

| Componente | Licenza | Percorso |
|---|---|---|
| EB Garamond (font) | SIL OFL 1.1 | `assets/EBGaramond-*.ttf`, `assets/EBGaramond-OFL.txt` |
| Courier Prime (font) | SIL OFL 1.1 | `assets/CourierPrime-*.ttf`, `assets/CourierPrime-OFL.txt` |
| Regola dell'evidenziato `==testo==` (porting di markdown-it-mark) | MIT | `src/ruscawriter/rusca_markdown.py` |

Il lettore MDict, i decompressori e i cifrari sono scritti da zero per questo progetto e ricadono sotto la GPL-3.0.

---

## 14. Nota IA

La nota sull'uso di strumenti di intelligenza artificiale è nella finestra Informazioni del programma e nel file `NOTA-IA.md` del repository di RuscaLinux.
