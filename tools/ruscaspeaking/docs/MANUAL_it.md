# RuscaSpeaking 1.99.3 — Manuale

**Versione** 1.99.3 · **Autore** Nunzio Curcuruto · **Distribuzione** RuscaLinux ([ruscalinux.org](https://www.ruscalinux.org/)) · **Licenza** GNU GPL v3 o successiva

RuscaSpeaking legge ad alta voce un **documento Markdown**, oppure dei **sottotitoli SRT** rispettandone i tempi, con un modello di **sintesi vocale** che gira **su questo computer**, tramite `llama-tts` di **ruscallama-engine** (llama.cpp, componente esterno con licenza MIT). L'audio si salva in **WAV**, **FLAC**, **Opus** o **MP3**.

---

## 1. Requisiti

- RuscaLinux o Debian Stable, GNOME;
- Python ≥ 3.10, GTK ≥ 4.18, libadwaita ≥ 1.7;
- i pacchetti `ruscallama-engine` (con `llama-tts`) e `ffmpeg`;
- un **modello di sintesi vocale** in GGUF con il suo file **mmproj**: vedi il punto seguente.

## 2. Il modello

Il modello non fa parte del programma: sono due file da copiare una volta sola.

1. Apri il menu principale → **Apri la cartella dei modelli** (la stessa voce è nelle **Preferenze**). La cartella è `~/.local/share/ruscaspeaking/models/`.
2. Copiaci il modello **e** il suo mmproj, nella stessa cartella. Per esempio, da [ggml-org/Qwen3-TTS-12Hz-1.7B-Base-GGUF](https://huggingface.co/ggml-org/Qwen3-TTS-12Hz-1.7B-Base-GGUF):
   - `Qwen3-TTS-12Hz-1.7B-Base-Q8_0.gguf` (1,85 GB), oppure la versione `bf16` per la qualità massima, o `Q4_K_M` se la memoria è poca;
   - `mmproj-Qwen3-TTS-12Hz-1.7B-Base-bf16.gguf` (669 MB) o `…-Q8_0.gguf` (446 MB).
3. Torna a RuscaSpeaking: il modello compare da solo, senza riavviare.

RuscaSpeaking abbina ogni modello al mmproj con lo stesso nome (a parte la parola «mmproj» e la precisione, come `Q8_0` o `bf16`); se nella cartella c'è un solo mmproj usa quello. Fra più mmproj adatti sceglie il più preciso. Le **Preferenze** mostrano quale mmproj sta usando. Con più modelli propone il file più grande, cioè il più preciso.

Ogni modello ha la propria licenza, da controllare prima di pubblicare l'audio. RuscaSpeaking non scarica nulla.

## 3. Leggere un documento

1. **Apri** il documento (Ctrl+O), trascinalo sulla finestra, oppure dal gestore dei file: **Apri con → RuscaSpeaking**. Si aprono file `.md`, `.markdown` e `.txt`.
2. La finestra mostra **il testo come verrà letto**: senza asterischi, cancelletti, indirizzi dei link e rimandi alle note; le formule in simboli.
3. Scegli la **lingua della voce** e premi **Genera l'audio** (Ctrl+Invio). La frase in lettura è in grassetto e sottolineata; la barra in basso dice a che punto si è e quanto manca, con **Ferma** (Esc).
4. Quando l'audio è pronto lo ascolti nella barra in basso e lo salvi dal pulsante **Salva**: **WAV** (Ctrl+S), **FLAC**, **Opus** o **MP3**.

Come si legge un documento:

| Elemento | Lettura |
|---|---|
| Titoli | Letti, seguiti da una pausa lunga |
| Paragrafi | Letti; i più lunghi si dividono alle fine delle frasi |
| Elenchi | Una voce per volta; negli elenchi numerati si legge il numero |
| Tabelle | Una riga per volta, celle separate da una breve pausa |
| Formule | Lette nei simboli Unicode (x², α, ≈) |
| Linea orizzontale | Una pausa più lunga |
| Blocchi di codice, note a piè di pagina | Saltati, salvo che tu li attivi nelle **Preferenze** |

## 4. Leggere dei sottotitoli

Apri un file `.srt`: la finestra mostra ogni sottotitolo con la sua ora. Con **Genera l'audio** ogni frase parte **all'ora del suo sottotitolo**, e l'audio dura fino alla fine dell'ultimo sottotitolo. Puoi usarlo come traccia di doppiaggio, per esempio dopo una trascrizione fatta con RuscaTranscriber.

- Tag come `<i>` e `{\an8}`, descrizioni di suoni fra parentesi quadre (`[musica]`) e note musicali (♪) non si leggono; i trattini dei dialoghi si tolgono.
- Ogni frase ha a disposizione il tempo fino al sottotitolo dopo. Se la voce è più lunga, si **accelera** senza cambiare il tono, fino alla **velocità massima** scelta nelle Preferenze (1,3 volte se non la cambi).
- Se non basta, la frase **slitta in avanti** quanto serve: due voci non si sovrappongono mai. Alla fine RuscaSpeaking dice quanti sottotitoli ha accelerato e spostato, e di quanto al massimo.

Per stare meglio nei tempi: una lingua più sintetica, una velocità massima un po' più alta, oppure sottotitoli meno fitti.

## 5. Qualità della voce

- **Una voce uguale per tutte le frasi.** I modelli «Base» come Qwen3-TTS, senza una **voce di riferimento**, inventano una voce a ogni frase: il seme non basta, perché cambiando il testo cambia anche la voce. Con una voce di riferimento ogni frase parte dalla stessa voce, dall'inizio alla fine. Ci sono due modi per averne una:
  - **Crea una voce** (menu principale, o Preferenze → Voce). RuscaSpeaking legge una frase di prova con una voce del modello. **Un'altra voce** ne prova un'altra; quando ne trovi una che ti piace, dalle un nome e premi **Tieni questa voce**: viene salvata in `~/.local/share/ruscaspeaking/voices/` e diventa la voce di riferimento. La frase di prova è nella lingua della voce scelta nella finestra.
  - **Una registrazione**: nelle **Preferenze**, il pulsante accanto a **Voce di riferimento** sceglie un file audio (WAV o MP3) con circa 10 secondi di parlato chiaro, senza musica né rumori. Usa la tua voce, o una voce che hai il permesso di usare.

  La riga **Voce di riferimento** elenca le voci salvate: puoi cambiarle quando vuoi, o scegliere **Nessuna**. Per rinominare o eliminare una voce, apri la cartella delle voci.
- **Voce del modello.** Alcuni modelli, come Pocket TTS, hanno voci già pronte: scrivi il nome nella riga **Voce del modello**.
- **Seme.** Lo stesso seme dà sempre la stessa lettura, ed è quello che rende uniforme la voce fra una frase e l'altra. Se una lettura non ti piace, cambialo.
- **Precisione.** `bf16` suona meglio di `Q8_0`, che suona meglio di `Q4_K_M`; i file più precisi sono più grandi e più lenti.
- **Volume.** **Regola il volume** porta tutto l'audio a un livello uniforme (EBU R128, −16 LUFS, come nei podcast).
- **Formati.** WAV e FLAC non perdono nulla; Opus (160 kbit/s) e MP3 (qualità massima) sono più piccoli e vanno bene per l'ascolto.

## 6. Velocità

`llama-tts` legge una frase per volta: a ogni frase carica il modello, genera la voce ed esce. È più lento di un motore sempre acceso, ma non apre nessuna porta, nemmeno dentro il computer. Con la **scheda grafica** la lettura è molto più veloce; un documento lungo o un film richiedono comunque tempo. La barra in basso stima quanto manca.

## 7. Preferenze

| Opzione | Effetto |
|---|---|
| Tema | Segue il sistema, chiaro o scuro |
| Dimensione del testo | Del testo da leggere; anche con Ctrl++ e Ctrl+−, Ctrl+0 torna a quella di sistema |
| Modello | Scelta fra i modelli trovati; sotto il nome, il mmproj abbinato |
| Apri la cartella dei modelli | Apre `~/.local/share/ruscaspeaking/models/` |
| Voce di riferimento | Nessuna, una delle voci salvate, o un file audio scelto con il pulsante accanto |
| Crea una voce | Prova le voci del modello e salva quella che ti piace (punto 5) |
| Apri la cartella delle voci | Apre `~/.local/share/ruscaspeaking/voices/` |
| Voce del modello | Nome di una voce già pronta del modello (facoltativo) |
| Leggi i blocchi di codice / Leggi le note a piè di pagina | Spenti per impostazione predefinita |
| Velocità massima nei sottotitoli | Da 1 (mai accelerare) a 2 |
| Regola il volume | Acceso per impostazione predefinita |
| Seme | 42 se non lo cambi |
| Scheda grafica (Vulkan) | Accesa per impostazione predefinita; spegnila se il driver dà problemi |
| Scheda da usare | Con più schede grafiche: **Automatica** lascia scegliere al motore |
| Thread della CPU | Consigliati tanti quanti i core fisici |

Le impostazioni sono in `~/.config/ruscaspeaking/settings.json`.

## 8. Scorciatoie

| Scorciatoia | Azione |
|---|---|
| Ctrl+O | Apri |
| Ctrl+Invio | Genera l'audio |
| Esc | Ferma |
| Ctrl+S | Salva in WAV |
| Ctrl+, | Preferenze |
| Ctrl++ / Ctrl+− / Ctrl+0 | Testo più grande / più piccolo / dimensione di sistema |
| Ctrl+? | Scorciatoie da tastiera |
| F10 | Menu principale |
| Ctrl+W / Ctrl+Q | Chiudi finestra / Esci |

## 9. Privacy e sicurezza

- Tutto avviene su questo computer. RuscaSpeaking non usa la rete in nessun modo: `llama-tts` legge un testo e scrive un file, senza aprire porte.
- FFmpeg è avviato in modo da leggere solo file locali.
- Le voci create restano in `~/.local/share/ruscaspeaking/voices/` finché non le elimini.
- Durante il lavoro l'audio sta in `~/.cache/ruscaspeaking/`, leggibile solo dall'utente; viene cancellato quando scarti il risultato, all'avvio e alla chiusura. Il documento di partenza non viene mai modificato.
- Niente telemetria.

## 10. Se qualcosa non va

| Problema | Che cosa fare |
|---|---|
| «Il motore della voce non è installato» | Installa o aggiorna `ruscallama-engine`: serve la versione con `llama-tts` |
| «Nessun modello trovato» | Copia il modello **e** il suo mmproj nella cartella dei modelli (punto 2) |
| «La sintesi vocale si è fermata con un errore» | Di solito un file incompleto (copia interrotta), un mmproj che non è di quel modello, o poca memoria. I dettagli sono nel menu principale → **Registro del motore** |
| «Voce di riferimento non trovata» | Il file è stato spostato: sceglilo di nuovo nelle Preferenze |
| La voce cambia da una frase all'altra | Manca la voce di riferimento: creane una con **Crea una voce**, o scegli una registrazione (punto 5) |
| Lingua sbagliata o pronuncia straniera | Controlla la **lingua della voce**. Qwen3-TTS conosce italiano, inglese, tedesco, francese, spagnolo, portoghese, russo, cinese, giapponese e coreano |
| Molto lento | Accendi la scheda grafica e scegli quella dedicata in **Scheda da usare**; un modello `Q4_K_M` è più veloce |
| Si blocca con la scheda grafica | Prova un'altra scheda, oppure spegni **Scheda grafica (Vulkan)** |
| L'audio non si sente nella finestra | Manca il supporto audio e video di GTK: `sudo apt install libgtk-4-media-gstreamer`. Il file salvato si ascolta con qualunque lettore |

Per provare il motore dal terminale: `/usr/lib/ruscallama-engine/llama-tts --version`.

## 11. Componenti esterni

| Componente | Licenza | Dove |
|---|---|---|
| llama.cpp (`llama-tts`, © The ggml authors) | MIT | Pacchetto `ruscallama-engine`, in `/usr/lib/ruscallama-engine/` |
| Regola dell'evidenziato del motore Markdown, porting di markdown-it-mark (© Vitaly Puzrin, Alex Kocharin; ExecutableBookProject) | MIT (Expat) | `/usr/share/ruscaspeaking/markdown_it_mark.py` |

FFmpeg non è incluso: è il pacchetto `ffmpeg` di Debian, usato come programma esterno.

Nota di sviluppo: vedi la finestra **Informazioni** o `NOTA-IA.md` nel repository di RuscaLinux.

Supporto: info@ruscalinux.org
