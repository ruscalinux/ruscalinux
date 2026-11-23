# RuscaDubbing 1.99.3 — Manuale

**Versione** 1.99.3 · **Autore** Nunzio Curcuruto · **Distribuzione** RuscaLinux ([ruscalinux.org](https://www.ruscalinux.org/)) · **Licenza** GNU GPL v3 o successiva

RuscaDubbing è la **sala di doppiaggio** di RuscaLinux. Da un video nella sua lingua ottiene:

- i **sottotitoli** nella lingua originale, in quella del doppiaggio e nelle due insieme (SRT);
- l'**audio doppiato** (Opus);
- il **video doppiato** (MKV o MP4): l'immagine originale, l'audio originale e quello doppiato, i sottotitoli nelle due lingue.

Tutto succede **su questo computer**, con tre motori esterni con licenza MIT: **whisper.cpp** (`ruscawhisper-engine`) trascrive, **llama.cpp** (`ruscallama-engine`) traduce e dà la voce, **FFmpeg** missa e scrive il video.

---

## 1. Requisiti

- RuscaLinux o Debian Stable, GNOME;
- Python ≥ 3.10, GTK ≥ 4.18, libadwaita ≥ 1.7;
- i pacchetti `ruscawhisper-engine`, `ruscallama-engine` (con `llama-tts`) e `ffmpeg`;
- tre modelli, gli stessi delle altre app (punto seguente).

Una scheda grafica con Vulkan rende tutto molto più veloce. Su un portatile senza scheda grafica un video di qualche minuto richiede comunque un po' di pazienza.

## 2. I modelli

RuscaDubbing **non ha modelli propri**: usa quelli che hai già copiato per le altre app.

| Passo | Modello | Cartella | Lo usa anche |
|---|---|---|---|
| Trascrizione | Whisper (`ggml-….bin`) | `~/.local/share/ruscawhisper/models/` | RuscaTranscriber |
| Traduzione | modello linguistico GGUF | `~/.local/share/ruscallama/models/` | RuscaTranslator, RuscaLLama |
| Voce | Qwen3-TTS GGUF + mmproj | `~/.local/share/ruscanarrator/models/` | RuscaNarrator |

Alla prima apertura RuscaDubbing usa i modelli che hai scelto nelle altre app. Nelle **Preferenze** scegli quale usare per ogni passo; per la voce conviene il modello **1.7B**: lo 0.6B sbaglia più spesso gli accenti dell’italiano; il pulsante con la cartella apre la cartella giusta. Se ne manca uno, una striscia in alto lo dice.

**La voce.** Senza voce di riferimento il modello inventa una voce per ogni battuta. Per un doppiaggio serve **una voce sola**: crea una voce con **Crea una voce** di RuscaNarrator e sceglila nelle Preferenze → **Voce di riferimento**. Alla prima apertura RuscaDubbing sceglie la prima voce che trova.

### Una voce simile all'originale

La voce di riferimento dovrebbe parlare **la lingua del doppiaggio**: il modello ne copia anche l'accento. Con la voce originale di un video russo, l'italiano esce con l'accento russo (libérta, pérche).

Per avere una voce italiana che somigli all'originale, nella pagina del video premi **Trova una voce simile…**. RuscaDubbing:

1. ascolta fino a un minuto della voce originale e ne **misura** l'altezza, quanto varia e quanto è chiara o cupa (il modello della voce non la sente e non la copia);
2. **inventa** otto voci nella lingua del doppiaggio;
3. te le propone **dalla più simile**, con la percentuale di somiglianza e che cosa cambia («più acuta», «più cupa»…).

Ascoltale, confrontale con l'originale (il pulsante accanto a **Ascolta l'originale**) e premi **Usa** su quella che preferisci: si salva fra le voci di RuscaNarrator e diventa la voce di riferimento. **Altre voci** ne crea altre otto. Le voci trovate somigliano per registro, non per timbro: non sono una copia della persona.

## 3. Doppiare un video

1. **Apri** il video (Ctrl+O), trascinalo sulla finestra, oppure dal gestore dei file: **Apri con → RuscaDubbing**.
2. Scegli la **lingua originale** («Automatica» la riconosce) e la **lingua del doppiaggio**.
3. Scegli **che cosa ottenere**: sottotitoli, audio doppiato, video doppiato.
4. Premi **Doppia** (Ctrl+Invio).

La finestra mostra i quattro passi:

| Passo | Che cosa succede |
|---|---|
| **Trascrizione** | Whisper scrive i sottotitoli originali. I pezzi di una stessa frase separati da una pausa breve diventano una battuta sola, perché la voce li dica di seguito. |
| **Traduzione** | Le battute si raggruppano in **frasi intere**, anche quando una frase è spezzata su più battute o ne finisce una a metà battuta. Il modello linguistico traduce le frasi a gruppi, con le precedenti come contesto: l'italiano viene scorrevole, senza pezzi di frase appesi. I sottotitoli tradotti si ridividono sulle battute originali, che restano ai loro tempi. Per ogni frase il modello sa **quanti caratteri** può usare per stare nel suo tempo; se una traduzione è molto più lunga, gli si chiede una versione breve, come fa un adattatore. Poi il modello si chiude, per lasciare la scheda grafica alla voce. |
| **Doppiaggio** | La voce dice ogni **frase intera al suo tempo**, con l'intonazione di una frase vera. Se è troppo lunga si accelera senza cambiare il tono, fino alla velocità massima; se non basta slitta in avanti: due battute non si sovrappongono mai. |
| **Verifica** | Ogni frase detta si misura. Se una non sta nel suo tempo nemmeno accelerata, il modello di traduzione la riscrive più corta, sapendo quanto parla veloce la voce, e la voce ridice solo quella. |
| **Missaggio** | FFmpeg abbassa l'audio originale mentre parla la voce (musica ed effetti restano, più bassi) e scrive i file. L'immagine **si copia** senza ricodifica: nessuna perdita di qualità e pochi secondi anche per un film. |

**Ferma** (Esc) interrompe in ogni momento. Alla fine RuscaDubbing elenca i file: un clic li apre, **Guarda** apre il video.

### Prova su un minuto e lavoro salvato

**Prova su un minuto** doppia solo l'inizio del video: in un paio di minuti senti voce, livello dell'audio originale e qualità della traduzione, prima di doppiare tutto. I file della prova hanno «.prova» nel nome.

RuscaDubbing **ricorda** trascrizione e traduzione di ogni video. Se lo doppi di nuovo (con un'altra voce, un altro livello dell'audio originale, un altro formato) si rifanno solo voce e missaggio: pochi minuti invece del lavoro intero. Le frasi tradotte nella prova servono anche al doppiaggio completo. La riga **Lavoro salvato**, nella pagina del video, dice che cosa c'è; **Dimentica** lo cancella e fa rifare tutto (per esempio dopo aver cambiato il modello di traduzione con uno migliore, o dopo aver corretto i sottotitoli originali).

### Chi parla e glossario

**Chi parla** serve all'italiano: chi parla di sé dice «sono stato» o «sono stata». Con **Automatico** RuscaDubbing ascolta l'altezza della voce originale e legge la grammatica della trascrizione; se sai chi parla, sceglilo.

Il **Glossario** è facoltativo e vale per il video aperto: nomi e termini da tradurre sempre allo stesso modo, separati da punto e virgola, per esempio `Polyglot = Poliglotta; Dmitrij Petrov`. Un termine senza «=» resta com'è. Prima di tradurre, il modello legge comunque tutto il discorso e si prepara una scheda con argomento, registro e termini ricorrenti: il glossario serve quando vuoi decidere tu.

### Pronuncia

La voce non legge esattamente i sottotitoli, ma una loro copia preparata per lei:
- i **numeri** si scrivono in lettere («16» → «sedici»), se è installato `python3-num2words`;
- le **parole ambigue** come «principi» (princìpi o prìncipi?) o «ancora» ricevono l'accento giusto per il senso: lo decide il modello di traduzione;
- le parole del **lessico delle pronunce** si scrivono come vanno dette. Se la voce sbaglia sempre una parola, aggiungila: Preferenze → Voce → **Lessico delle pronunce** apre il tuo file. Una riga per parola: la parola, un tasto Tab, la parola con l'accento sulla sillaba giusta (`tienila` Tab `tiènila`).

I sottotitoli non cambiano.

## 4. I file

Accanto al video, o nella cartella scelta in **Cartella dei file**. Un video `film.mp4` doppiato dall'inglese all'italiano dà:

| File | Contenuto |
|---|---|
| `film.en.srt` | sottotitoli originali |
| `film.it.srt` | sottotitoli tradotti, divisi come quelli professionali: al massimo due righe da 42 caratteri, a capo dopo la punteggiatura, tempi di lettura comodi |
| `film.en-it.srt` | le due lingue insieme, battuta per battuta: sopra l'originale, sotto la traduzione (utile per studiare o controllare) |
| `film.it.opus` | l'audio doppiato da solo |
| `film.it.mkv` | il video doppiato |

Se un file esiste già non si sovrascrive: il nuovo si chiama `film.it (2).mkv`.

Nel video doppiato la traccia **doppiata è quella predefinita**; l'audio originale e i sottotitoli sono tracce in più, con la loro lingua, da scegliere nel lettore (in Totem/Video: menu → **Lingue** e **Sottotitoli**; in VLC: **Audio** → **Traccia audio**). **MKV** accetta qualsiasi video e copia l'audio originale così com'è; **MP4** è più diffuso su telefoni e televisori, ma non accetta ogni tipo di immagine: se non riesce, scegli MKV.

## 5. Sottotitoli originali da un file

Se hai già i sottotitoli originali (quelli del film, o quelli di RuscaTranscriber corretti a mano), nella riga **Sottotitoli originali** premi il pulsante con la cartella e scegli il file `.srt`: la trascrizione si salta e si usano quelli. Indica la **lingua originale**: dal testo non si riconosce. È anche il modo per doppiare un video **senza audio**.

Per un doppiaggio curato: trascrivi con RuscaTranscriber, correggi il testo, poi dallo a RuscaDubbing.

## 6. Audio originale sotto la voce

**Poco**, **Abbastanza** o **Molto**: quanto si abbassa l'audio originale mentre parla la voce doppiata. È il doppiaggio «a voce sopra» dei documentari: la voce originale si sente appena, sotto. Togliere del tutto la voce originale lasciando musica ed effetti richiede di separare le voci dal resto: arriverà in una versione futura.

## 7. Preferenze

| Gruppo | Che cosa |
|---|---|
| Aspetto | Tema chiaro, scuro o del sistema |
| Modelli | Il modello per trascrivere, tradurre e dare la voce |
| Voce | Voce di riferimento; voce del modello (per i modelli con voci con nome); **velocità massima** (quanto può accelerare una battuta, 1,3 volte se non la cambi); **seme** (lo stesso seme dà la stessa interpretazione) |
| Motore | Scheda grafica sì/no; **una scheda per ogni passo** (trascrizione, traduzione, voce); thread della CPU; contesto della traduzione |

**Due schede grafiche.** I passi lavorano uno dopo l'altro, ma ognuno può usare una scheda diversa: per esempio il modello linguistico, che è il più grande, sulla scheda con più memoria e la voce sull'altra. Alla prima apertura ogni passo usa la scheda scelta nell'app corrispondente (RuscaTranscriber, RuscaTranslator, RuscaNarrator).

## 8. Privacy

- **Nessun dato lascia la macchina.** La sola connessione è quella con `llama-server`, sul computer stesso (`127.0.0.1`), con una chiave casuale che cambia a ogni avvio.
- I programmi si avviano senza shell; FFmpeg legge solo file locali.
- I file di lavoro (audio estratto, battute, voce) stanno in `~/.cache/ruscadubbing/` e **si cancellano** alla fine di ogni doppiaggio, all'avvio e alla chiusura.
- Trascrizione e traduzioni di ogni video restano invece in `~/.local/share/ruscadubbing/progetti/`, leggibili solo da te, finché non premi **Dimentica**.

## 9. Diritti e voci

Doppia solo video che hai il diritto di usare. Ogni modello ha la propria licenza, da controllare prima di pubblicare. Usa come voce di riferimento solo la tua voce o quella di chi ti ha dato il permesso.

## 10. Scorciatoie

| Tasti | Azione |
|---|---|
| Ctrl+O | Apri un video |
| Ctrl+Invio | Doppia |
| Esc | Ferma |
| Ctrl+, | Preferenze |
| Ctrl+? | Scorciatoie |
| F10 | Menu principale |
| Ctrl+W / Ctrl+Q | Chiudi / Esci |

## 11. Problemi

| Problema | Soluzione |
|---|---|
| La striscia in alto dice che manca un modello | Copia il modello nella sua cartella (punto 2) e riapri le Preferenze |
| La voce cambia da una battuta all'altra | Scegli una **voce di riferimento** (punto 2) |
| Molte battute accelerate o spostate | Alza un po' la velocità massima, o usa sottotitoli meno fitti |
| Alcune battute restano nella lingua originale | Il modello linguistico non le ha tradotte: provane uno più grande |
| Il video MP4 non si scrive | Scegli **MKV** |
| Qualcosa non va | Menu principale → **Registro dei motori** mostra che cosa hanno scritto i programmi |
