# RuscaDubbing 1.99.3 — Manuale

**Versione** 1.99.3 · **Autore** Nunzio Curcuruto · **Distribuzione** RuscaLinux ([ruscalinux.org](https://www.ruscalinux.org/)) · **Licenza** GNU GPL v3 o successiva

RuscaDubbing trasforma il parlato di un **video** o di un **file audio** in testo, con un modello di riconoscimento vocale **Whisper** che gira **su questo computer**, tramite **ruscawhisper-engine** (whisper.cpp, componente esterno con licenza MIT). Il risultato si salva come documento **Markdown** e come **sottotitoli SRT**.

---

## 1. Requisiti

- RuscaLinux o Debian Stable, GNOME;
- Python ≥ 3.10, GTK ≥ 4.18, libadwaita ≥ 1.7;
- i pacchetti `ruscawhisper-engine` e `ffmpeg`;
- un **modello Whisper** in formato ggml (un file `.bin`): vedi il punto seguente.

## 2. Il modello

Il modello non fa parte del programma: è un file che si copia una volta sola.

1. Apri il menu principale → **Apri la cartella dei modelli** (la stessa voce è nelle **Preferenze**). La cartella è `~/.local/share/ruscawhisper/models/`.
2. Copiaci il modello che preferisci, per esempio `ggml-large-v3-turbo.bin`.
3. Torna a RuscaDubbing: il modello compare da solo, senza riavviare.

I modelli Whisper per whisper.cpp hanno nomi come `ggml-tiny.bin`, `ggml-base.bin`, `ggml-small.bin`, `ggml-medium.bin`, `ggml-large-v3.bin` e `ggml-large-v3-turbo.bin`. I più grandi sono più precisi, più lenti e chiedono più memoria; quelli con `.en` nel nome capiscono solo l'inglese. RuscaDubbing non scarica nulla: il file si prende da un altro computer o con il browser, e ogni modello ha la propria licenza, che va rispettata.

Con più modelli nella cartella, RuscaDubbing propone il più grande; si cambia nelle **Preferenze** (Ctrl+,). L'amministratore può mettere modelli per tutti gli utenti in `/usr/share/ruscawhisper/models/`.

## 3. Trascrivere

1. **Apri** il video o l'audio (Ctrl+O), oppure trascinalo sulla finestra, oppure dal gestore dei file: **Apri con → RuscaDubbing**.
2. Scegli la **lingua parlata**. **Rileva la lingua** lascia decidere al modello, che ascolta i primi secondi: comodo, ma su un inizio con musica o silenzio può sbagliare.
3. Premi **Trascrivi** (Ctrl+Invio). Il testo compare mentre viene riconosciuto; la barra in basso mostra a che punto si è, con **Ferma** (Esc).
4. Salva dal pulsante **Salva** nella barra del titolo: **Salva in Markdown…** (Ctrl+S) o **Salva i sottotitoli (SRT)…** (Ctrl+E). Puoi salvare entrambi.

Il nome proposto è quello del file di partenza, nella stessa cartella: `lezione.mp4` → `lezione.md` e `lezione.srt`. Un file `.srt` con lo stesso nome del video, accanto al video, viene caricato da solo dalla maggior parte dei lettori.

La durata dipende dal modello e dal computer: con un modello grande e senza scheda grafica, un'ora di parlato può richiedere più di un'ora.

## 4. Che cosa si ottiene

| Formato | Contenuto |
|---|---|
| Markdown (`.md`) | Un titolo con il nome del file e il testo a paragrafi. Un paragrafo nuovo comincia dopo una pausa di almeno due secondi, o alla fine di una frase quando il paragrafo è già lungo. Si apre con RuscaMark o RuscaWriter |
| SRT (`.srt`) | Un sottotitolo numerato per ogni segmento riconosciuto, con l'orario di inizio e di fine. UTF-8 |

Nel Markdown il parlato resta testo: asterischi, cancelletti, indirizzi e altri caratteri che Markdown leggerebbe come formattazione sono protetti con la barra rovesciata.

**La trascrizione automatica va riletta.** Un modello può sbagliare nomi, numeri e parole rare, e nei tratti di silenzio o di musica può scrivere frasi che nessuno ha detto. Per correggere il testo apri il file salvato con RuscaMark; per i sottotitoli, con un editor di testo o di sottotitoli.

## 5. Formati di ingresso

Video e audio che **FFmpeg** sa leggere: MP4, MKV, WebM, MOV, AVI, MPEG, MP3, WAV, FLAC, Ogg, Opus, M4A e altri. Di un video si usa la prima traccia audio. Il file di partenza non viene mai modificato.

## 6. Preferenze

| Opzione | Effetto |
|---|---|
| Tema | Segue il sistema, chiaro o scuro |
| Dimensione del testo | Dimensione del testo della trascrizione; anche con Ctrl++ e Ctrl+−, Ctrl+0 torna a quella di sistema |
| Modello | Scelta tra i modelli trovati nelle cartelle dei modelli |
| Apri la cartella dei modelli | Apre `~/.local/share/ruscawhisper/models/` nel gestore dei file |
| Scheda grafica (Vulkan) | Molto più veloce; spenta per impostazione predefinita perché alcuni driver si bloccano |
| Thread della CPU | Consigliati tanti quanti i core fisici |

Le impostazioni sono in `~/.config/ruscadubbing/settings.json`.

## 7. Scorciatoie

| Scorciatoia | Azione |
|---|---|
| Ctrl+O | Apri |
| Ctrl+Invio | Trascrivi |
| Esc | Ferma |
| Ctrl+S | Salva in Markdown |
| Ctrl+E | Salva i sottotitoli (SRT) |
| Ctrl+, | Preferenze |
| Ctrl++ / Ctrl+− / Ctrl+0 | Testo più grande / più piccolo / dimensione di sistema |
| Ctrl+? | Scorciatoie da tastiera |
| F10 | Menu principale |
| Ctrl+W / Ctrl+Q | Chiudi finestra / Esci |

## 8. Privacy e sicurezza

- Tutto avviene su questo computer. RuscaDubbing non usa la rete in nessun modo: nemmeno le connessioni locali che altri strumenti usano per parlare con il proprio motore.
- Il motore (`whisper-cli`) non contiene codice di rete: lo controlla la costruzione del pacchetto. Parte, trascrive un file ed esce.
- FFmpeg è avviato in modo da leggere solo file locali.
- Durante il lavoro l'audio estratto sta in `~/.cache/ruscadubbing/`, leggibile solo dall'utente; viene cancellato alla fine di ogni trascrizione, all'avvio e alla chiusura.
- Niente telemetria.

## 9. Se qualcosa non va

| Problema | Che cosa fare |
|---|---|
| «ruscawhisper-engine non è installato» | `sudo apt install ruscawhisper-engine` (in RuscaLinux c'è già) |
| «Nessun modello trovato» | Copia un modello nella cartella dei modelli (punto 2) |
| «Impossibile leggere l'audio del file» | Il file non ha una traccia audio, è danneggiato o non è un video o un audio. Il messaggio riporta l'errore di FFmpeg |
| «Il riconoscimento vocale si è fermato con un errore» | Di solito il modello è incompleto (copia interrotta) o la memoria non basta: prova un modello più piccolo. I dettagli sono nel menu principale → **Registro del motore** |
| «Nessun parlato riconosciuto» | Nel file non c'è voce, o la lingua scelta non è quella parlata |
| Testo in una lingua sbagliata | Scegli la lingua a mano invece di **Rileva la lingua** |
| Molto lento | Usa un modello più piccolo, oppure accendi **Scheda grafica (Vulkan)** nelle Preferenze |
| Si blocca con la scheda grafica | Spegni **Scheda grafica (Vulkan)** |

Per provare il motore dal terminale: `/usr/lib/ruscawhisper-engine/whisper-cli --version`.

## 10. Componenti esterni

| Componente | Licenza | Dove |
|---|---|---|
| whisper.cpp (© The ggml authors) | MIT | Pacchetto `ruscawhisper-engine`, in `/usr/lib/ruscawhisper-engine/` |

FFmpeg non è incluso: è il pacchetto `ffmpeg` di Debian, usato come programma esterno.

Nota di sviluppo: vedi la finestra **Informazioni** o `NOTA-IA.md` nel repository di RuscaLinux.

Supporto: info@ruscalinux.org
