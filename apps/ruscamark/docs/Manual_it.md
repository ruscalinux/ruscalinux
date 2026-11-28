# Manuale di RuscaMark 1.99.3

RuscaMark è l'editor Markdown delle RuscaLinux OS Apps. È pensato per scrivere articoli, report, appunti e documentazione: la formattazione compare mentre scrivi, la pagina resta centrata come un foglio e tutto il lavoro avviene sul tuo computer.

| Campo | Valore |
|---|---|
| Versione | 1.99.3 |
| Autore | Nunzio Curcuruto (ruscalinux-dev) |
| Sito web | [ruscalinux.org](https://www.ruscalinux.org) |
| Contatto | info@ruscalinux.org |
| Licenza | GPL-3.0 — <https://www.gnu.org/licenses/gpl-3.0.html> |

---

## 1. Requisiti e installazione

| Requisito | Valore |
|---|---|
| Sistema | RuscaLinux o Debian Stable |
| Desktop | GNOME |
| Librerie grafiche | GTK 4.18 o successivo e libadwaita 1.7 o successiva |
| Linguaggio | Python 3.10 o successivo |

Prima di installare, verifica l'integrità del pacchetto nella cartella che contiene il file `SHA256SUMS`:

```bash
sha256sum -c SHA256SUMS
```

Installazione consigliata:

```bash
sudo apt install ./ruscamark-ruscalinux_1.99.3_all.deb
```

In alternativa `sudo dpkg -i ruscamark-ruscalinux_1.99.3_all.deb`, seguito da `sudo apt -f install` se mancano dipendenze.

Pacchetti consigliati (installati automaticamente da `apt` se disponibili):

| Pacchetto | A cosa serve |
|---|---|
| `gir1.2-gtksource-5` | Editor avanzato: annulla/ripeti, ricerca evidenziata |
| `gir1.2-spelling-1` | Controllo ortografico live |
| `hunspell-it`, `hunspell-en-gb` | Dizionari italiano e inglese britannico |
| `ruscavosk-engine`, `ruscawhisper-engine` | Dettatura e trascrizione di file audio (sezione 12) |
| `ruscapiper-engine` | Lettura ad alta voce |
| `pipewire-bin`, `ffmpeg` | Microfono e riproduzione; lettura dei file audio e video |

Per altre lingue installa il dizionario corrispondente, ad esempio `hunspell-fr` o `hunspell-de-de`.

## 2. Avvio

Apri RuscaMark dal menu applicazioni di GNOME oppure cercandolo in Attività. Da terminale:

```bash
ruscamark                 # documento nuovo
ruscamark relazione.md    # apre un file
```

Al primo avvio RuscaMark mostra un documento di benvenuto che presenta le sue funzioni; dalle volte successive si apre con un documento vuoto.

Puoi anche trascinare un file `.md` dentro la finestra.

## 3. La finestra

- **Barra del titolo**: a sinistra Nuovo e Apri; a destra il microfono della dettatura, l'anteprima, Salva e il menu principale. Dal menu principale si raggiungono anche Importa da audio, esportazione, resa live, controllo ortografico, schermo intero, formato, ricerca, obiettivo di parole, dettatura, Leggi ad alta voce, Preferenze, Scorciatoie da tastiera e Informazioni.
- **Carattere**: il testo è in **Literata**, un carattere disegnato per leggere a lungo sullo schermo che rende bene anche stampato; è incluso in RuscaMark e si usa anche nel PDF. Nelle Preferenze puoi sceglierne un altro.
- **Stile chiaro o scuro**: RuscaMark segue l'impostazione di GNOME; nelle Preferenze puoi anche forzare lo stile chiaro o quello scuro.
- **Pagina di scrittura**: il testo occupa una colonna centrata, larga quanto impostato nelle Preferenze (68 caratteri di default). I margini si ricalcolano quando ridimensioni, massimizzi o metti a schermo intero la finestra, e quando apri l'anteprima.
- **Barra di stato**: parole, caratteri e righe, posizione del cursore e obiettivo di parole.
- **Barra ortografia**: compare sotto il testo quando accendi il controllo ortografico.
- **Barra della voce**: compare sopra la barra di stato durante la dettatura e la lettura ad alta voce, con il pulsante **Ferma** (sezione 12).

## 4. Due modi di vedere il testo

**Resa live (Ctrl+L)** — modalità predefinita. Titoli, grassetti, corsivi, codice, link, citazioni ed elenchi assumono subito il loro aspetto e i marcatori (`**`, `#`, `>`…) si nascondono. Quando porti il cursore su un elemento, la sua sintassi riappare per poterla modificare. Le tabelle restano in carattere monospazio, così le colonne allineate rimangono incolonnate. La resa live riconosce il Markdown esattamente come l'anteprima e gli export, anche quando un grassetto o un corsivo continua sulla riga successiva. Le formule `$…$` appaiono in corsivo, con esponenti e pedici veri (`x^2`, `a_{i}`); le righe `$$` delle formule su più righe spariscono e la formula è centrata; le barre rovesciate degli escape (`\*`) e dell'a capo forzato si nascondono; `---` diventa una linea. I trattini degli elenchi restano trattini: un editor di testo non può mostrare un carattere diverso da quello scritto nel file.

**Anteprima classica (Ctrl+P)** — divide la finestra: a sinistra il sorgente con la sintassi colorata, a destra il documento impaginato. Solo l'anteprima mostra le immagini vere, le tabelle disegnate a griglia e le note raccolte in fondo. Con lo stile chiaro l'anteprima usa i colori del tema di PDF e HTML scelto nelle Preferenze; con lo stile scuro resta prugna.

Le due modalità si escludono: accendendone una, l'altra si spegne.

## 5. Guida rapida al Markdown

### Testo

| Scrivi | Ottieni |
|---|---|
| `**grassetto**` o `__grassetto__` | **grassetto** |
| `*corsivo*` o `_corsivo_` | *corsivo* |
| `***entrambi***` | ***entrambi*** |
| `~~barrato~~` | ~~barrato~~ |
| `==evidenziato==` | testo evidenziato |
| `` `codice` `` | `codice` |
| `\*non corsivo\*` | \*non corsivo\* (il backslash annulla il marcatore) |

Per andare a capo senza iniziare un nuovo paragrafo, termina la riga con due spazi oppure con `\`. Una riga vuota separa i paragrafi.

### Titoli

```markdown
# Titolo di livello 1
## Titolo di livello 2
###### Titolo di livello 6

Titolo alternativo di livello 1
===============================

Titolo alternativo di livello 2
-------------------------------
```

Nell'HTML esportato ogni titolo riceve un'ancora (`id`), utile per i link interni come `[vai ai risultati](#risultati)`.

### Elenchi

```markdown
- punto
- altro punto
  - punto annidato (rientro di due spazi)

1. primo
2. secondo

3. un elenco può iniziare da qualsiasi numero
```

Liste di attività:

```markdown
- [x] bozza completata
- [ ] revisione
```

### Citazioni

```markdown
> Una citazione può occupare più righe
> e contenere **formattazione**.
>
> > Citazioni annidate con più `>`.
```

### Link

```markdown
[testo del link](https://ruscalinux.org "titolo facoltativo")
<https://ruscalinux.org>
https://ruscalinux.org          (gli indirizzi nudi diventano link)

Link a riferimento: vedi [Debian][deb].

[deb]: https://debian.org "Debian"
```

I link a riferimento tengono pulito il testo degli articoli lunghi: le definizioni possono stare in fondo al documento.

### Immagini

```markdown
![Descrizione dell'immagine](img/grafico.png "titolo facoltativo")
```

- Il percorso può essere relativo alla cartella del documento (consigliato), assoluto o `file://`.
- Un'immagine da sola su una riga viene mostrata a tutta pagina nell'anteprima, ridotta alla larghezza della colonna e mai ingrandita.
- Le immagini su internet (`https://…`) **non vengono scaricate** dall'anteprima, per rispetto della privacy: al loro posto compare un avviso. Nell'HTML esportato restano come link e le carica il browser.
- Il testo tra parentesi quadre è la descrizione alternativa: scrivila sempre, serve all'accessibilità.

### Tabelle

```markdown
| Voce    | Q1    | Note     |
|:--------|------:|:--------:|
| Ricavi  | 1.200 | in linea |
| Costi   |   800 | `ok`     |
```

I due punti nella riga di separazione decidono l'allineamento: `:---` a sinistra, `---:` a destra, `:---:` al centro. Per scrivere una barra verticale dentro una cella usa `\|`. Non serve allineare le colonne a mano: ci pensa **Ctrl+Maiusc+T** (vedi sezione 6).

### Note a piè di pagina

```markdown
Il dato è stimato[^fonte].

[^fonte]: Rilevazione interna, settembre 2026.
```

Le note sono numerate nell'ordine in cui compaiono nel testo e raccolte in fondo al documento.

### Codice

````markdown
```python
print("Ciao")
```
````

Sono accettati anche i blocchi con `~~~` e i blocchi rientrati di quattro spazi.

### Linea orizzontale

Una riga con `---`, `***` o `___` (preceduta da una riga vuota).

## 6. Comandi di scrittura

Si trovano nel menu principale e hanno scorciatoie dedicate.

| Comando | Scorciatoia | Comportamento |
|---|---|---|
| Grassetto | Ctrl+B | Avvolge la selezione in `**…**`; se è già in grassetto lo toglie. Senza selezione inserisce `****` con il cursore in mezzo. |
| Corsivo | Ctrl+I | Come sopra con `*…*`. |
| Titolo 1…6 | Ctrl+1 … Ctrl+6 | Trasforma la riga corrente nel titolo del livello scelto. |
| Testo normale | Ctrl+0 | Toglie i `#` dalla riga corrente. |
| Inserisci link | Ctrl+K | Con del testo selezionato crea `[testo](https://)` e seleziona l'indirizzo da sostituire; con un URL selezionato crea `[](URL)` e mette il cursore sul testo. |
| Inserisci immagine | Ctrl+Maiusc+I | Sceglie un file immagine e inserisce `![nome](percorso)`. Se il documento è già salvato il percorso è relativo alla sua cartella, altrimenti è assoluto. |
| Inserisci/allinea tabella | Ctrl+Maiusc+T | Fuori da una tabella ne inserisce una di 3 colonne; con il cursore dentro una tabella ne riallinea tutte le colonne, rispettando l'allineamento scelto e i caratteri larghi (cinese, giapponese, coreano). |

Consiglio: salva il documento prima di inserire immagini, così i percorsi saranno relativi e il documento resterà portabile insieme alla sua cartella.

## 7. Tutte le scorciatoie

| Scorciatoia | Azione |
|---|---|
| Ctrl+N | Nuovo documento |
| Ctrl+O | Apri/Importa Markdown |
| Ctrl+S | Salva |
| Ctrl+Maiusc+S | Salva con nome |
| Ctrl+Maiusc+E | Esporta HTML |
| Ctrl+Maiusc+P | Esporta PDF |
| Ctrl+L | Resa live |
| Ctrl+P | Anteprima |
| F11 | Schermo intero |
| F7 | Controllo ortografico acceso/spento |
| F10 | Menu principale |
| Ctrl+, | Preferenze |
| Ctrl+? | Scorciatoie da tastiera |
| Ctrl+Z / Ctrl+Maiusc+Z | Annulla / Ripeti |
| Ctrl+F | Trova |
| Ctrl+H | Trova e sostituisci |
| Ctrl+B / Ctrl+I | Grassetto / Corsivo |
| Ctrl+K | Link |
| Ctrl+Maiusc+I | Immagine |
| Ctrl+Maiusc+T | Inserisci o allinea tabella |
| Ctrl+1 … Ctrl+6, Ctrl+0 | Livello del titolo / testo normale |
| Ctrl+Maiusc+D | Dettatura accesa/spenta |
| Ctrl+Maiusc+R | Leggi ad alta voce / ferma la lettura |
| Ctrl+Maiusc+O | Importa da audio |
| Ctrl+W | Chiudi la finestra |
| Ctrl+Q | Esci |

L'elenco completo si apre anche dal programma con **Ctrl+?** o dal menu principale → **Scorciatoie da tastiera**.

## 8. Trova e sostituisci

**Ctrl+F** apre la barra di ricerca, **Ctrl+H** aggiunge il campo di sostituzione.

- **Invio** o la freccia giù vanno al risultato successivo, la freccia su al precedente; la ricerca riparte dall'inizio quando arriva in fondo.
- **Aa** distingue maiuscole e minuscole.
- **Sostituisci** cambia il risultato corrente e passa al successivo; **Tutti** sostituisce ogni occorrenza in un solo passo, annullabile con Ctrl+Z.
- **Esc** chiude la barra.

## 9. Controllo ortografico

Premi **F7** oppure scegli **Controllo ortografico** dal menu principale. Le parole sconosciute vengono sottolineate mentre scrivi; con il **tasto destro** su una parola ottieni i suggerimenti e puoi aggiungerla al dizionario personale. La lingua del dizionario si sceglie dal menu a tendina nella barra ortografia ed è indipendente dalla lingua dell'interfaccia: puoi avere i menu in italiano e controllare un testo in inglese britannico (`en_GB`, pacchetto `hunspell-en-gb`).

Per italiano e francese RuscaMark aggiunge al dizionario personale i frammenti di elisione (`dell'`, `quest'`, `qu'`, `jusqu'`…), così non vengono segnalati come errori. La scelta acceso/spento viene ricordata al riavvio.

Il controllo avviene solo con i dizionari installati sul computer: il testo non viene mai inviato in rete.

## 10. Obiettivo di parole

Fai clic su **🎯 Obiettivo** nella barra di stato (o usa il menu) e imposta il numero di parole da raggiungere; 0 lo disattiva. Una barra di avanzamento indica quante parole mancano e cambia colore quando l'obiettivo è raggiunto.

## 11. Esportare in PDF e in HTML

PDF e HTML hanno lo **stesso stile**, indipendentemente dallo stile chiaro o scuro dell'editor: quello del **tema** scelto in Preferenze → Esportazione → *Tema di PDF e HTML*. Con lo stile chiaro anche l'anteprima usa i colori del tema.

### Temi

| Tema | Aspetto |
|---|---|
| **RuscaLinux – Guida** (predefinito) | Lo stile delle guide di riferimento delle RuscaLinux OS Apps: titolo di livello 1 in un **banner** sfumato dal rosa al prugna, titoli di livello 2 prugna con filetto rosa, codice su prugna scuro con barra rosa, tabelle con intestazione prugna, testo in Literata. |
| **Neutro** | Sobrio, in grigi: titolo con filetto, codice su grigio chiaro, link blu. Stampa bene anche in bianco e nero. |
| **RuscaLinux – Fascia** | La palette RuscaLinux in forma leggera: fascia sfumata in cima alla prima pagina, titolo prugna senza riquadro, codice su prugna scuro, piè di pagina diviso (titolo a sinistra, pagine a destra). |
| **Classico** | Carattere con grazie (Literata) e toni seppia, come un libro. |
| **Mare** | Blu e azzurri, con il banner sfumato del titolo. |

In tutti i temi il paragrafo subito dopo il titolo principale è un'introduzione in corpo più grande, il codice in linea è una «pillola» colorata, le tabelle occupano tutta la larghezza con righe alternate e in fondo a ogni pagina c'è il piè di pagina «*titolo* - pag. *N* / *totale*», dove il titolo è il primo titolo di livello 1 (o il nome del file). Non ci sono riferimenti al programma o al sito.

### Temi personali

Un tema è un file `.css` con variabili, come un foglio di stile. Per crearne uno:

1. In Preferenze → Esportazione premi **Apri la cartella** accanto a *Temi personali*: si apre `~/.local/share/ruscamark/themes/`.
2. Copia lì uno dei temi inclusi da `/usr/share/ruscamark/themes/` (in `ruscalinux.css` ogni variabile è spiegata) e dagli un nome nuovo, per esempio `mio-tema.css`.
3. Cambia i valori e scegli il tema nelle Preferenze (riaprile se erano aperte). Gli export rileggono il file ogni volta, quindi non serve riavviare.

Un tema può anche cambiare solo poche cose e prendere il resto da un altro tema con `--base`:

```css
:root {
  --name: "Neutro blu";
  --base: neutral;
  --title: #1A5FB4;
  --rule-h2: #99C1F1;
}
```

Le variabili principali: colori di testo e titoli (`--fg`, `--title`, `--h3`, `--link`…), codice (`--code-bg`, `--pre-bg`, `--pre-bar-width`…), citazioni, tabelle (`--th-bg`, `--stripe`), caratteri (`--font`, `--mono`, elenchi di famiglie come in `font-family`), forma del titolo (`--h1-style: banner | text | rule`), fascia in cima (`--strip: none | top`) e piè di pagina (`--footer-align: center | split`). Un valore non valido viene ignorato e resta quello del tema di base. RuscaMark legge solo le variabili: le altre regole CSS del file non contano, e un file con lo stesso nome di un tema incluso lo sostituisce.

### PDF

**Ctrl+Maiusc+P** (oppure menu → *Esporta PDF…*) crea direttamente il file PDF, senza passare dalla finestra di stampa.

- Il formato carta è quello predefinito del sistema (A4 in Europa, Letter negli Stati Uniti), con margini di 2 cm; il testo è a 10 punti.
- I paragrafi lunghi continuano sulla pagina successiva; un titolo non resta mai da solo in fondo a una pagina; i blocchi di codice brevi non vengono spezzati, quelli lunghi continuano nella pagina successiva con il loro riquadro.
- Le tabelle vanno a capo dentro la cella e, se continuano sulla pagina successiva, la riga di intestazione viene ripetuta.
- Le immagini locali sono inserite alla loro dimensione naturale, ridotte se più larghe della pagina. Le immagini remote non vengono scaricate: al loro posto compare il testo alternativo.
- I link sono cliccabili: quelli web e di posta aprono il browser o il programma di posta, quelli interni come `[vai ai risultati](#risultati)` portano al titolo. I link a file o a percorsi relativi restano testo, perché fuori dalla cartella del documento non porterebbero da nessuna parte; anche un link interno a un titolo che non esiste resta testo.

### HTML

**Ctrl+Maiusc+E** crea una pagina HTML con lo stile descritto sopra, il titolo preso dal primo titolo di livello 1 e la lingua del documento presa dal dizionario ortografico in uso. Sullo schermo il documento appare come un foglio bianco centrato su un fondo leggermente colorato.

- **Immagini locali**: i percorsi vengono ricalcolati rispetto alla cartella in cui salvi l'HTML, quindi funzionano anche esportando in un'altra cartella.
- **File unico**: attivando in Preferenze «Incorpora le immagini nell'export HTML» le immagini vengono inserite dentro il file (base64). Il file è più pesante ma si può inviare o spostare da solo.
- **Stampa dal browser**: l'HTML contiene uno stile di stampa A4 con margini di 2 cm, colori di sfondo conservati, titoli non separati dal testo che segue, codice, citazioni e immagini non spezzati e lo stesso piè di pagina del PDF (nei browser che supportano i margini di pagina CSS, come Chromium e i derivati).

Il codice HTML scritto dentro il Markdown (ad esempio `<br>` o `<div>`) non viene eseguito ma mostrato come testo: è una scelta di sicurezza.

## 12. La voce: dettatura, trascrizione e lettura

RuscaMark scrive quello che dici, trasforma un file audio o video in un documento e legge ad alta voce. Usa i motori delle RuscaLinux OS Apps, che sono pacchetti a parte: **ruscavosk-engine** (Vosk), **ruscawhisper-engine** (whisper.cpp) e **ruscapiper-engine** (Piper). Se ne manca uno, RuscaMark lo dice quando serve e nelle Preferenze → Voce. I modelli e le voci non sono nei pacchetti: si copiano nelle cartelle indicate qui sotto, e ognuno ha la propria licenza, che va rispettata.

### Dettatura

Premi il **microfono** nella barra del titolo (**Ctrl+Maiusc+D**) e parla: il testo compare dove c'è il cursore e, se c'è una selezione, la sostituisce. Sopra la barra di stato compare la barra della voce, con il livello del microfono, lo stato e, con Vosk, le parole che sta riconoscendo. **Ferma** (o di nuovo Ctrl+Maiusc+D) smette di ascoltare. Ogni frase entra nel testo in un solo passo, annullabile con Ctrl+Z.

Il motore si sceglie in Preferenze → Voce → *Motore*:

| | Vosk | Whisper |
|---|---|---|
| Come scrive | Parola per parola mentre parli; la frase entra nel testo dopo un secondo di pausa | Una frase per volta, dopo ogni pausa di circa 0,7 secondi |
| Punteggiatura e maiuscole | Le dici tu (vedi sotto) | Le scrive da solo |
| Precisione | Buona | Molto buona |
| Dove lavora | Sempre sul processore | Sul processore o sulla scheda grafica (Vulkan) |
| Modelli | Cartelle in `~/.local/share/ruscavosk/models/`, per esempio `vosk-model-it-0.22` (1,2 GB) o `vosk-model-small-it-0.22` (48 MB) | File `.bin` in `~/.local/share/ruscawhisper/models/`, per esempio `ggml-large-v3-turbo.bin` |

Con Whisper ogni frase avvia il motore, che rilegge il modello: sulla scheda grafica un modello grande risponde in un paio di secondi, sul processore per dettare conviene un modello piccolo come `ggml-small.bin`. A Whisper si passano anche le ultime parole già scritte, così mantiene lo stesso stile e la stessa punteggiatura.

**Punteggiatura a voce (solo Vosk).** Vosk scrive le parole, non i segni: in italiano e in inglese queste parole diventano segni.

| Dici | Scrive |
|---|---|
| virgola · punto · due punti · punto e virgola | `,` `.` `:` `;` |
| punto interrogativo · punto esclamativo | `?` `!` |
| a capo · nuovo paragrafo | una riga nuova · una riga vuota |
| apri parentesi · chiudi parentesi | `(` `)` |
| apri virgolette · chiudi virgolette | `«` `»` |

In inglese: *comma, full stop / period, colon, semicolon, question mark, exclamation mark, new line, new paragraph, open/close parenthesis, open/close quote*. Dopo punto, punto interrogativo, punto esclamativo e a capo la parola che segue prende la maiuscola. Un comando vale sempre, anche dentro una frase: «il punto è» diventa «il. È». Se ti capita spesso, spegni *Punteggiatura a voce* o usa Whisper.

Il parlato è testo: se dici qualcosa che il Markdown leggerebbe come formattazione (un asterisco, «1.» a inizio riga), RuscaMark lo protegge con la barra rovesciata, come fa RuscaTranscriber.

**Lingua parlata.** *Come il documento* (predefinita) usa la lingua del dizionario ortografico; puoi sceglierne una delle 24 lingue delle RuscaLinux OS Apps, oppure *Automatica* (solo Whisper). Con Vosk la lingua la decide il modello: RuscaMark usa quello scelto nelle Preferenze o, con *Scelta automatica*, il più grande della lingua parlata.

**Processore o scheda grafica (Whisper).** In Preferenze → Voce → Whisper, *Esegui su* vale *Processore (CPU)* (predefinito) o *Scheda grafica (Vulkan)*. Con la scheda grafica, *Scheda da usare* offre *Automatica* e le schede integrate e dedicate del computer, con la loro memoria: la scelta si salva per nome, e se la scheda non c'è più decide il motore. Se il driver di una scheda dà problemi, torna al processore. Vosk e Piper lavorano sempre sul processore.

### Importa da audio

Menu principale → **Importa da audio…** (**Ctrl+Maiusc+O**): scegli un file audio o video, in qualunque formato che FFmpeg sappia leggere. Il motore è quello della dettatura. Il documento che ottieni ha un titolo con il nome del file e il testo a paragrafi (uno nuovo dopo una pausa di almeno due secondi); non è ancora salvato, e Salva propone lo stesso nome del file con `.md`. Il documento aperto viene sostituito: se ha modifiche non salvate, RuscaMark chiede prima. **Annulla** ferma il lavoro.

- Con *Come il documento* la lingua di un file è *Automatica*: un audio in un'altra lingua, trascritto come se fosse italiano, diventerebbe un testo inventato.
- Con Vosk ogni frase prende la maiuscola e il punto finale. Per i file lunghi Whisper è più preciso.
- Se fra i modelli Whisper c'è il modello di rilevamento del parlato `ggml-silero-v6.2.0.bin`, Whisper trascrive solo i tratti con voce, come in RuscaTranscriber.

### Leggi ad alta voce

Menu principale → **Leggi ad alta voce** (**Ctrl+Maiusc+R**) legge la selezione, oppure il documento dal paragrafo del cursore fino alla fine. Lo stesso comando, o **Ferma**, la interrompe. Si legge il testo come nell'anteprima: senza marcatori, il testo dei link e non l'indirizzo, le formule in simboli; blocchi di codice e note a piè di pagina si saltano (i blocchi di codice si possono leggere, dalle Preferenze).

- Le voci Piper sono coppie `nome.onnx` e `nome.onnx.json` in `~/.local/share/ruscapiper/voices/` (le stesse di RuscaLLisse). Con *Scelta automatica* RuscaMark usa la voce della lingua del documento. La velocità va da 0,7 a 1,3.
- Le Preferenze mostrano la licenza della voce, se il file MODEL_CARD che l'accompagna la dichiara. Molte voci Piper derivano dalla voce inglese «lessac», distribuita per la sola ricerca non commerciale: per usi pubblici o commerciali scegli una voce con una licenza libera verificata.
- Le correzioni dell'accento del lessico delle pronunce di RuscaLLisse (`~/.local/share/ruscallisse/pronunce.tsv`) valgono anche qui.

Mentre RuscaMark legge, la dettatura resta spenta (il microfono sentirebbe la voce), e viceversa.

## 13. Preferenze

Dal menu principale → **Preferenze…** (Ctrl+,). Ogni modifica vale subito. Le Preferenze hanno due pagine: **Generale** e **Voce**.

| Gruppo | Opzione | Effetto |
|---|---|---|
| Aspetto | Stile | *Segui il sistema* (predefinito), *Chiaro* o *Scuro*. |
| Aspetto | Carattere del testo e Dimensione | Carattere dell'editor e dell'anteprima: Literata (predefinito, in cima all'elenco) o uno dei caratteri installati. Il carattere del PDF e dell'HTML è quello del tema (sezione 11). |
| Aspetto | Interlinea | *Compatta*, *Normale* (predefinita) o *Ariosa*: lo spazio tra le righe dell'editor e dell'anteprima, in proporzione al corpo del font (1,25 – 1,5 – 1,75 volte). Blocchi di codice e tabelle restano compatti. |
| Scrittura | Resa live della formattazione | Come Ctrl+L. |
| Scrittura | Pagina centrata | Se attiva, il testo resta in una colonna centrata; se disattiva occupa tutta la larghezza e una linea guida verticale indica la larghezza di pagina. |
| Scrittura | Larghezza pagina (caratteri) | Da 40 a 140; misurata sul carattere medio del font scelto. 60–75 è la misura più comoda da leggere. |
| Esportazione | Tema di PDF e HTML | Colori, caratteri e titoli degli export e dell'anteprima: vedi sezione 11. |
| Esportazione | Temi personali | *Apri la cartella* apre `~/.local/share/ruscamark/themes/`, dove mettere i propri temi `.css`. |
| Esportazione | Incorpora le immagini nell'export HTML | Vedi sezione 11. |
| Voce → Dettatura | Motore, Lingua parlata, Punteggiatura a voce | Vedi sezione 12. |
| Voce → Vosk | Modello, Cartella dei modelli | *Scelta automatica* usa il modello più grande della lingua parlata. |
| Voce → Whisper | Modello, Esegui su, Scheda da usare, Cartella dei modelli | Processore o scheda grafica (Vulkan) e quale scheda: vedi sezione 12. |
| Voce → Lettura ad alta voce | Voce, Licenza della voce, Velocità, Leggi anche i blocchi di codice, Cartella delle voci | Vedi sezione 12. |

I margini laterali si adattano alla finestra: nelle finestre strette restano almeno al 4% della larghezza (da 16 a 48 pixel), in quelle larghe lo spazio libero viene diviso in parti uguali ai due lati.

## 14. Lingue dell'interfaccia

Inglese, cinese semplificato, spagnolo, hindi, arabo, portoghese brasiliano, russo, giapponese, tedesco, francese, italiano, coreano, indonesiano, turco e polacco. RuscaMark usa sempre la lingua del sistema; per cambiarla si usa Impostazioni di GNOME → Sistema → Regione e lingua. Con l'arabo tutta l'interfaccia passa da destra a sinistra.

Le traduzioni sono file JSON in `/usr/share/ruscamark/lang/`. Per correggere o personalizzare una traduzione copia il file in `~/.config/ruscamark/lang/` e modificalo: la copia personale ha la precedenza. Se una frase manca, viene mostrata in inglese.

## 15. File e cartelle

| Percorso | Contenuto |
|---|---|
| `~/.config/ruscamark/config.json` | Preferenze, dimensioni della finestra, stato dell'ortografia |
| `~/.config/ruscamark/lang/` | Traduzioni personalizzate (facoltative) |
| `~/.config/ruscamark/icons/` | Copia dell'icona del programma |
| `~/.local/share/gtksourceview-5/styles/` | Schemi colore rosa e prugna dell'editor |
| `~/.config/enchant/<lingua>.dic` | Dizionario personale (con i frammenti di elisione) |
| `~/.config/enchant/<lingua>.dic.ruscamark-added` | Elenco dei frammenti aggiunti da RuscaMark, per non toccare le parole aggiunte da te |
| `~/.local/share/ruscavosk/models/` | Modelli Vosk (una cartella per modello; anche `/usr/share/ruscavosk/models/`) |
| `~/.local/share/ruscawhisper/models/` | Modelli Whisper, file `.bin` (anche `/usr/share/ruscawhisper/models/`) |
| `~/.local/share/ruscapiper/voices/` | Voci Piper, `.onnx` e `.onnx.json` (anche `/usr/share/ruscapiper/voices/`) |
| `~/.cache/ruscamark/trascrizione/` | File di lavoro di una trascrizione con Whisper, cancellati alla fine e a ogni avvio |
| `$XDG_RUNTIME_DIR/ruscamark/` | Una frase dettata con Whisper, in memoria, cancellata appena letta |

Per tornare alle impostazioni iniziali chiudi RuscaMark e cancella `config.json`.

## 16. Privacy e sicurezza

| Principio | Come lo rispetta RuscaMark |
|---|---|
| Dati elaborati | Solo in locale, sul tuo computer |
| Invio a server remoti o su internet | Mai: il programma non apre connessioni di rete |
| Telemetria e statistiche d'uso | Nessuna |
| Raccolta di dati personali | Nessuna |
| Comandi pericolosi o dannosi | Nessuno; non servono permessi di amministratore |
| Operazioni sensibili | Avvengono solo su tua richiesta e sono sempre visibili |

**Tutti i dati elaborati restano in locale.** Nessun testo, documento o file viene inviato a server remoti o su internet.

### Rete

RuscaMark non contiene codice che si collega alla rete. In particolare:

- l'anteprima mostra solo immagini presenti sul computer; quelle con indirizzo `https://…` non vengono scaricate e al loro posto compare un avviso;
- il controllo ortografico usa esclusivamente i dizionari installati (hunspell); il testo non lascia mai il computer;
- nella finestra Informazioni, le righe «Sito web», «Supporto» e «Licenza» aprono il browser o il programma di posta, e solo quando le scegli;
- dettatura, trascrizione e lettura ad alta voce lavorano sul computer, con i motori delle RuscaLinux OS Apps, che non aprono connessioni né porte.

### Microfono e audio

- Il microfono si apre solo quando accendi la dettatura, e la barra della voce lo mostra finché resta aperto.
- Con Vosk l'audio del microfono passa solo in memoria e non si scrive mai su disco.
- Whisper legge un file: ogni frase dettata diventa un breve file WAV in una cartella privata della sessione (`$XDG_RUNTIME_DIR/ruscamark/`, di solito in memoria), cancellato appena letto. La trascrizione di un file usa `~/.cache/ruscamark/trascrizione/`, che si svuota alla fine e a ogni avvio.
- Né l'audio né il testo dettato vengono conservati altrove: resta solo quello che salvi.

L'HTML esportato è un file come un altro: se il documento contiene immagini remote, sarà il **browser** che apre l'HTML a scaricarle. Per un file completamente autonomo usa immagini locali e attiva «Incorpora le immagini nell'export HTML».

### Sicurezza dei contenuti

- Il codice HTML scritto dentro il Markdown non viene eseguito, né nell'anteprima né nell'export: viene mostrato come testo.
- I link pericolosi (`javascript:`, `vbscript:`, `data:text/html`) vengono neutralizzati nell'HTML esportato.
- Aprire un file Markdown non esegue nulla: è solo testo.

### File scritti sul computer

RuscaMark scrive soltanto i documenti che salvi o esporti tu, più i file di configurazione elencati nella sezione 15, tutti nella tua cartella personale. Non modifica file di sistema. Nel dizionario personale aggiunge solo i frammenti di elisione italiani e francesi, tenendone un elenco separato per non alterare mai le parole che hai aggiunto tu.

### Integrità del pacchetto

Verifica sempre il pacchetto prima di installarlo:

```bash
sha256sum -c SHA256SUMS
```

### Rimuovere ogni traccia

```bash
sudo apt remove ruscamark
rm -rf ~/.config/ruscamark ~/.cache/ruscamark
rm -f ~/.local/share/gtksourceview-5/styles/ruscamark-*.xml
```

Il dizionario personale in `~/.config/enchant/` è condiviso con altri programmi: se vuoi, cancella a mano le parole che non ti servono.

## 17. Risoluzione dei problemi

| Problema | Soluzione |
|---|---|
| Il programma non si avvia | Verifica Python 3, GTK 4 (`gir1.2-gtk-4.0`) e libadwaita (`gir1.2-adw-1`); controlla il pacchetto con `sha256sum -c SHA256SUMS` e reinstallalo. |
| «Controllo ortografico non disponibile» | Installa `gir1.2-spelling-1` e il dizionario della lingua (es. `hunspell-it`). |
| Annulla/Ripeti o la ricerca evidenziata non funzionano | Installa `gir1.2-gtksource-5`. |
| L'export PDF segnala «python3-gi-cairo» | Installa il pacchetto `python3-gi-cairo` (normalmente arriva insieme a RuscaMark). |
| Nel pannello compare un'icona generica | Avvia RuscaMark dal menu delle applicazioni dopo averlo installato dal pacchetto: l'icona dipende dal file `org.ruscalinux.RuscaMark.desktop`. Se avevi fissato RuscaMark nella dash con una versione precedente alla 1.99.2, toglilo e fissalo di nuovo: l'identificativo è cambiato. Avviando `ruscamark.py` direttamente dalla cartella dei sorgenti, GNOME non trova il lanciatore e mostra l'icona generica. |
| Un'immagine non compare in anteprima | Controlla il percorso: se relativo, parte dalla cartella del documento salvato. Le immagini remote non vengono mostrate per scelta. |
| Le colonne di una tabella sono storte | Metti il cursore nella tabella e premi Ctrl+Maiusc+T. |
| Una riga con `---` sotto diventa un titolo | Lascia una riga vuota prima di `---` per avere una linea orizzontale. |
| La dettatura non parte | Leggi il messaggio: dice se manca il motore (`ruscavosk-engine` o `ruscawhisper-engine`), il modello o `pipewire-bin`. Preferenze → Voce mostra che cosa c'è. |
| La barra della voce resta «In ascolto» ma non scrive nulla | Controlla il microfono in Impostazioni → Audio. Con Vosk la frase entra dopo un secondo di pausa; con Whisper dopo circa 0,7 secondi. |
| Whisper è lento | Usa un modello più piccolo, oppure *Scheda grafica (Vulkan)* in Preferenze → Voce. |
| Whisper si ferma con un errore sulla scheda grafica | Scegli un'altra scheda in *Scheda da usare*, oppure *Processore (CPU)*. |
| Vosk scrive «.» al posto della parola «punto» | È un comando a voce: spegni *Punteggiatura a voce* o usa Whisper. |
| La lettura ad alta voce non parte | Installa `ruscapiper-engine` e copia una voce (`.onnx` con il suo `.onnx.json`) nella cartella delle voci. |

Assistenza: info@ruscalinux.org

## 18. Licenza e nota di sviluppo

RuscaMark è software libero distribuito con licenza GPL-3.0: <https://www.gnu.org/licenses/gpl-3.0.html>.

Il motore Markdown comune include un componente esterno: la regola dell'evidenziato `==testo==`, porting del plugin [markdown-it-mark](https://github.com/markdown-it/markdown-it-mark) (licenza MIT, © Vitaly Puzrin e Alex Kocharin; struttura in Python da markdown-it-py, © ExecutableBookProject), nel file a sé `markdown_it_mark.py`. È elencato anche nella finestra Informazioni, alla voce «Componenti esterni».

Il carattere del testo è **Literata 3.103** (© The Literata Project Authors, <https://github.com/googlefonts/literata>), con licenza SIL Open Font License 1.1, compatibile con la distribuzione insieme a software GPL: i file del carattere non sono modificati e il testo della licenza è in `/usr/share/ruscamark/fonts/Literata-OFL.txt`. La licenza permette di incorporarlo nei PDF esportati.

Dettatura, trascrizione e lettura usano tre motori che sono pacchetti a parte, elencati anche loro tra i «Componenti esterni»: Vosk (licenza Apache 2.0, © Alpha Cephei Inc.), whisper.cpp (licenza MIT, © The ggml authors) e Piper (licenza GPL-3.0, © Michael Hansen e gli autori di Piper).

La nota sull'uso di strumenti di intelligenza artificiale si trova nella finestra Informazioni del programma e nel file `NOTA-IA.md` del repository.
