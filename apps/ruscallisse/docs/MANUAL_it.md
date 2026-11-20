# RuscaLLisse — manuale

Una conversazione a voce con Ellittica, una donna digitale intellettuale, dolce e sensibile, che ti spiega le cose in modo semplice. È un dialogo come nella vita: sullo schermo c'è solo il suo volto, niente viene scritto e la conversazione non si salva.

**Versione di prova.** I motori per ascoltare (Vosk) e per parlare (Piper) sono quelli già compilati dei pacchetti ufficiali, in `/usr/lib/ruscallisse/prova/`.

## Prima volta

Servono tre cose, che RuscaLLisse non scarica (menu principale → “Quali file scaricare?”):

1. **Un modello per ascoltare (Vosk):** per esempio `vosk-model-it-0.22` o `vosk-model-small-it-0.22`, scompattato in `~/.local/share/ruscavosk/models/`.
2. **Un modello per pensare (GGUF):** lo stesso di RuscaLLama, in `~/.local/share/ruscallama/models/`.
3. **Una voce (Piper):** i due file `nome.onnx` e `nome.onnx.json`; menu principale → “Importa una voce…”.

Poi, dal menu principale, “Modifica la personalità…”: scrivi il **quid** di Ellittica, il tratto centrale del suo carattere.

## Parlare

- Parla normalmente: Ellittica ascolta, pensa e risponde a voce.
- **Spazio** mette in pausa il microfono e lo riprende.
- **Esc** la fa tacere.
- **Ctrl+N** ricomincia: dimentica la conversazione.

Mentre parla il microfono non ascolta, così non sente la sua voce.

## Privacy

Tutto resta su questo computer. Il modello linguistico ascolta solo su 127.0.0.1; l'audio non viene mai salvato; la conversazione resta in memoria e si dimentica alla chiusura. Ogni modello e ogni voce hanno la propria licenza: molte voci Piper sono solo per uso non commerciale. Ellittica è un personaggio, non un'esperta: le sue risposte vanno verificate.

## Per chi sviluppa

`RUSCALLISSE_DEBUG=1 ruscallisse` scrive sul terminale i tempi di ogni turno; con `RUSCALLISSE_DEBUG=2` anche ciò che è stato capito e la risposta.
