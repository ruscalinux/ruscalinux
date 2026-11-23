# RuscaPallas — manuale

Pallasio è un manul vecchio, colto e incattivito, con giacca color crema, cravatta rossa, occhialini tondi e un tomo sempre in mano. Vive chiuso in uno sgabuzzino e da una finestra osserva un mondo in mano agli zombi e ai maiali, riflettendo sul senso della vita e sull'assurdità di tutto. Cammina sul desktop, salta sulle finestre e, se lo clicchi, ti ascolta e ti risponde a voce.

Ascolta, pensa e parla con gli stessi motori di RuscaLLisse: ruscavosk-engine (Vosk), ruscallama-engine (llama.cpp) e ruscapiper-engine (Piper).

## Prima volta

1. Pallasio usa gli stessi file di RuscaLLisse: un modello Vosk per ascoltare, un modello GGUF per pensare e una voce Piper. Se RuscaLLisse funziona, funziona anche Pallasio; altrimenti apri RuscaLLisse e segui «Quali file scaricare?». Per una voce maschile scarica `it_IT-riccardo-x_low`.
2. Dopo l'installazione del pacchetto esci dalla sessione e rientra: GNOME vede le estensioni nuove solo all'accesso.
3. Apri **RuscaPallas** dalla cartella RuscaLinux Apps: Pallasio compare sul bordo basso dello schermo.

## Parlargli

- **Clic** su Pallasio: incrocia le braccia, alza un sopracciglio e ascolta. Il fumetto mostra un orecchio.
- Fai la tua domanda. Mentre pensa si siede e consulta il tomo (fumetto con i puntini), poi risponde ringhiando e agitando l'indice (fumetto con le onde).
- Dopo la risposta resta in ascolto qualche secondo per il seguito. Se taci, sbuffa e torna a passeggiare.
- **Clic** mentre parla o ascolta: tace.
- La prima volta ci mette qualche secondo a svegliarsi (fumetto con la clessidra): carica i modelli.

Il fumetto non mostra mai parole: la conversazione non si scrive e non si salva.

## Muoverlo

- **Trascinalo** con il mouse; lasciato andare cade a terra, o sulla finestra che ha sotto.
- **Clic destro**: «Zitto» e «Torna nello sgabuzzino». Per richiamarlo apri di nuovo RuscaPallas.
- Nella panoramica delle attività e con le finestre a schermo intero non c'è.
- Con le animazioni disattivate (Impostazioni → Accessibilità) sta fermo, ma parla lo stesso.

## La personalità

Il carattere di Pallasio è nel file `~/.local/share/ruscapallas/pallasio.md`, con le stesse sezioni delle entità di RuscaLLisse (Quid, Carattere, Modo di parlare, Non fa mai, Voce). Le modifiche valgono dalla domanda successiva.

## Da terminale

    ruscapallas            lo richiama
    ruscapallas --hide     lo rimanda nello sgabuzzino
    ruscapallas --quit     spegne il servizio di dialogo e libera la memoria

Il servizio di dialogo parte al primo clic ed esce da solo dopo un quarto d'ora senza conversare. Per vedere i tempi di ogni turno e ciò che ha capito: `ruscapallas --quit`, poi avvia il servizio a mano con `RUSCALLISSE_DEBUG=2 /usr/share/ruscapallas/ruscapallas-service.py` e clicca Pallasio.

## Privacy

Tutto resta su questo computer. Il modello linguistico ascolta solo su 127.0.0.1; l'audio non viene mai salvato; la conversazione resta in memoria e si dimentica quando il servizio esce. Pallasio guarda solo i bordi delle finestre per camminarci sopra: non legge cosa contengono. È un personaggio, non un esperto: le sue risposte vanno verificate.
