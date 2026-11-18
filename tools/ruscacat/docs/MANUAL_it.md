# RuscaCat 1.99.3 — Manuale

**Versione** 1.99.3 · **Autore** Nunzio Curcuruto · **Distribuzione** RuscaLinux ([ruscalinux.org](https://www.ruscalinux.org/)) · **Licenza** GNU GPL v3 o successiva

RuscaCat è **Martino**, un gatto nero dagli occhiali tondi con cui si parla **a voce**. È un filosofo heideggeriano: scontroso, cinico e sarcastico, ma in fondo buono. Martino **ascolta** dal microfono, **capisce** con un modello Whisper, **risponde** con un modello linguistico e **parla** con una voce sintetica. Tutto gira **su questo computer**, con i motori di RuscaLinux:

| Che cosa fa | Motore | Lo stesso modello di |
|---|---|---|
| Ascolta e capisce | `whisper-cli` di **ruscawhisper-engine** (whisper.cpp, MIT) | RuscaTranscriber |
| Pensa e risponde | `llama-server` di **ruscallama-engine** (llama.cpp, MIT) | RuscaLLama |
| Parla | `llama-tts` di **ruscallama-engine** | RuscaNarrator |

---

## 1. Requisiti

- RuscaLinux o Debian Stable, GNOME;
- Python ≥ 3.10, GTK ≥ 4.18, libadwaita ≥ 1.7;
- i pacchetti `ruscallama-engine`, `ruscawhisper-engine`, `ffmpeg` e `libgtk-4-media-gstreamer` (li installa il pacchetto `ruscacat`);
- un microfono, scelto in **Impostazioni → Suono → Ingresso**;
- tre modelli, gli stessi degli altri strumenti: vedi il punto seguente.

## 2. I modelli

RuscaCat non ha modelli propri: usa quelli di RuscaLLama, RuscaTranscriber e RuscaNarrator, nelle loro cartelle. Se hai già usato quegli strumenti non devi copiare niente. Le **Preferenze** hanno una riga **Apri la cartella dei modelli** per ognuno; la stessa azione è nella barra che compare in alto quando un modello manca. I modelli nuovi compaiono da soli, senza riavviare.

| Modello | Cartella | Consiglio per una conversazione |
|---|---|---|
| **Cervello**: modello linguistico GGUF | `~/.local/share/ruscallama/models/` | Un modello piccolo e veloce (da 1 a 8 miliardi di parametri): una risposta che arriva subito conta più di una risposta colta |
| **Orecchie**: modello Whisper (`.bin`) | `~/.local/share/ruscawhisper/models/` | `ggml-small.bin`, o `ggml-large-v3-turbo.bin` con la scheda grafica |
| **Voce**: modello vocale GGUF con il suo mmproj | `~/.local/share/ruscanarrator/models/` | Qwen3-TTS, come in RuscaNarrator |

Senza il modello Whisper puoi comunque **scrivere** a Martino; senza il modello vocale (o con la **Voce** spenta nelle Preferenze) risponde solo per iscritto. Senza il modello linguistico dorme.

Ogni modello ha la propria licenza. RuscaCat non scarica nulla.

## 3. Parlare con Martino

1. Premi **Ascolta** (Ctrl+L). Le orecchie si drizzano e accanto all'orecchio compaiono degli archi che seguono la tua voce: Martino ti sta ascoltando, suo malgrado.
2. **Parla**. Quando smetti, dopo una breve pausa (0,9 secondi se non la cambi), Martino capisce che hai finito.
3. Mentre **decifra i tuoi suoni** e **medita sull'Essere** il microfono è **chiuso**: Martino non sente se stesso. Poi risponde: la risposta compare per iscritto a destra e lui la dice ad alta voce, con la bocca che segue la voce.
4. Finito di parlare, il microfono **si riapre** da solo, e puoi rispondergli. Se preferisci premere **Ascolta** ogni volta, spegni **Ascolta di nuovo dopo ogni risposta** nelle Preferenze.

Puoi anche **scrivergli** nella casella in basso e premere Invio: risponde allo stesso modo.

**Zitto** (Esc) lo interrompe subito: si ferma la risposta, si ferma la voce. Quello che aveva già scritto resta nella conversazione.

Martino comincia a parlare **prima di aver finito di pensare**: ogni frase va alla voce appena è completa, e mentre dice una frase si prepara la successiva.

| Martino… | Che cosa succede |
|---|---|
| dorme, con le «z» | Il modello linguistico manca o si sta caricando |
| ha le palpebre a metà e le orecchie di traverso | È in attesa: premi **Ascolta** o scrivigli |
| ha le orecchie dritte e gli archi accanto all'orecchio | Ascolta il microfono |
| guarda di lato, con tre puntini | Trascrive quello che hai detto |
| guarda in alto, con tre puntini | Pensa alla risposta |
| muove la bocca | Parla |

Lo stato è scritto anche sotto il disegno: non serve vedere i colori.

## 4. La conversazione

- **Nuova conversazione** (Ctrl+N, il pulsante **+**) fa dimenticare a Martino tutto quello che vi siete detti.
- **Salva la conversazione…** (Ctrl+S, dal menu principale) la salva come documento **Markdown**, da aprire con RuscaMark. Quello che è stato detto resta testo: asterischi e indirizzi non diventano formattazione né link.
- La conversazione **resta in memoria** e sparisce alla chiusura, salvo che tu la salvi. Martino ricorda gli ultimi 24 scambi.
- Le risposte sono generate da un modello linguistico: possono essere sbagliate o inventate. Martino è un personaggio, non un esperto: verifica quello che dice prima di usarlo.

## 5. Preferenze

| Gruppo | Riga | A che cosa serve |
|---|---|---|
| Aspetto | **Tema**, **Dimensione del testo** | Come negli altri RuscaLinux OS Tools (Ctrl++, Ctrl+−, Ctrl+0) |
| Conversazione | **Lingua** | La lingua in cui parli e in cui Martino risponde: vale per l'ascolto, per la risposta e per la voce. Le lingue sono le dieci di Qwen3-TTS |
| | **Voce** | Spenta: Martino risponde solo per iscritto |
| | **Ascolta di nuovo dopo ogni risposta** | Il microfono si riapre da solo |
| | **Fantasia** | Più alta, risposte più varie e bizzarre (0,8 se non la cambi) |
| Cervello | **Modello**, **Memoria della conversazione** | Il modello linguistico e il suo contesto in token. Si applicano alla chiusura delle Preferenze, riavviando il modello |
| Orecchie | **Modello** | Il modello Whisper |
| | **Sensibilità del microfono** | Da 1 a 10 (5 se non la cambi). Alzala se Martino non ti sente, abbassala se scatta per ogni rumore |
| | **Pausa di fine frase** | Il silenzio dopo il quale Martino capisce che hai finito, da 0,5 a 3 secondi. Alzala se ti interrompe mentre pensi |
| Voce | **Modello**, **Voce di riferimento**, **Voce del modello**, **Seme** | Come in RuscaNarrator. Una voce di riferimento fa parlare Martino sempre con la stessa voce: creane una con **Crea una voce** di RuscaNarrator e sceglila qui |
| Motore | **Scheda grafica**, **Scheda da usare**, **Thread della CPU** | Valgono per tutti e tre i motori |

## 6. Come funziona l'ascolto

RuscaCat legge il microfono con **FFmpeg**, dalla sorgente predefinita di GNOME (PipeWire): campioni a 16 kHz, mono. Ogni 30 millisecondi confronta il volume con il **rumore di fondo**, che misura da solo mentre nessuno parla:

- il parlato **comincia** quando il volume resta sopra il rumore (di un margine che dipende dalla sensibilità) per 150 ms; si tengono anche i 300 ms prima, perché la prima sillaba non si perda;
- il parlato **finisce** dopo la pausa di fine frase; una frase con meno di un quarto di secondo di voce è un rumore e si scarta; una frase più lunga di 30 secondi si chiude da sola;
- la frase diventa un file WAV nella cartella di lavoro, `whisper-cli` la trascrive e il file **si cancella subito**.

Su un rumore Whisper a volte «sente» frasi che non sono state dette, come i titoli di coda dei sottotitoli: RuscaCat le riconosce e le scarta, e così le trascrizioni fatte solo di suoni («[Musica]»).

## 7. Privacy e sicurezza

- Il **microfono è aperto solo mentre Martino ascolta**: il processo FFmpeg parte quando premi **Ascolta** e si ferma quando Martino comincia a pensare, quando premi **Smetti di ascoltare** e alla chiusura. GNOME mostra l'indicatore del microfono in alto.
- L'audio resta **in memoria**; diventa un file solo la frase da trascrivere e la voce di Martino da ascoltare, in `~/.cache/ruscacat/` (permessi 0700), cancellati appena usati, all'avvio e alla chiusura.
- `whisper-cli` e `llama-tts` lavorano su un file ed escono, senza aprire porte. `llama-server` ascolta **solo su 127.0.0.1**, su una porta scelta a ogni avvio, con una **chiave casuale** che gli altri utenti del computer non conoscono, come in RuscaLLama.
- Nulla viene inviato su internet. Nessuna telemetria.
- La conversazione si salva solo se lo chiedi tu.
- Se usi una voce di riferimento, usa la tua o una voce che hai il permesso di usare.

## 8. Scorciatoie da tastiera

| Scorciatoia | Azione |
|---|---|
| Ctrl+L | Ascolta / smetti di ascoltare |
| Esc | Zitto |
| Invio | Invia il testo scritto |
| Ctrl+N | Nuova conversazione |
| Ctrl+S | Salva la conversazione |
| Ctrl+, | Preferenze |
| Ctrl++ / Ctrl+− / Ctrl+0 | Testo più grande / più piccolo / di sistema |
| Ctrl+? | Scorciatoie da tastiera |
| F10 | Menu principale |
| Ctrl+W / Ctrl+Q | Chiudi finestra / Esci |

## 9. Accessibilità

- Il disegno ha un'etichetta per i lettori di schermo che dice che cosa sta facendo Martino; lo stesso testo è scritto sotto il disegno.
- Con **Animazioni ridotte** (Impostazioni → Accessibilità) Martino non si muove da solo: niente coda, respiro, battito di ciglia né puntini, e mentre parla la bocca resta aperta a metà. Gli stati restano riconoscibili dalla forma di occhi, orecchie e segni.
- Con il **contrasto elevato** i contorni del disegno sono più spessi.
- Tutto si fa da tastiera, anche senza microfono: basta scrivere.

## 10. Risoluzione dei problemi

| Problema | Che cosa fare |
|---|---|
| Martino non mi sente | Controlla in **Impostazioni → Suono** il microfono scelto e il suo volume; alza la **Sensibilità** |
| Scatta per ogni rumore | Abbassa la **Sensibilità**; allontana il microfono dalle casse |
| Mi interrompe mentre penso | Alza la **Pausa di fine frase** |
| «Il microfono non funziona» | Il registro dei motori (menu principale) riporta l'errore di FFmpeg. Di solito manca la sorgente: controlla che PipeWire sia attivo (`pactl info`) |
| Capisce male | Controlla la **Lingua**; prova un modello Whisper più grande |
| Risponde ma non parla | Controlla che ci sia un modello vocale con il suo mmproj e che `libgtk-4-media-gstreamer` sia installato; il registro dei motori dice che cosa non va |
| Ci mette troppo a rispondere | Usa la scheda grafica; scegli un modello linguistico più piccolo; un modello vocale più leggero |
| La voce cambia da una frase all'altra | Scegli una **Voce di riferimento** (creala con RuscaNarrator) |
| Il modello linguistico si ferma | Menu principale → **Registro dei motori**, poi **Riavvia il modello linguistico** |

## 11. Componenti esterni

| Componente | Licenza | Uso |
|---|---|---|
| llama.cpp (`llama-server`, `llama-tts`) | MIT — The ggml authors | Pacchetto `ruscallama-engine` |
| whisper.cpp (`whisper-cli`) | MIT — The ggml authors | Pacchetto `ruscawhisper-engine` |
| markdown-it-mark (regola dell'evidenziato) | MIT — Vitaly Puzrin, Alex Kocharin; ExecutableBookProject | File `markdown_it_mark.py`, accanto al motore Markdown comune |

FFmpeg non è incluso: RuscaCat usa il comando `ffmpeg` di Debian. La nota sullo sviluppo è nella finestra **Informazioni** e in `NOTA-IA.md` del repository.
