# RuscaPinball — manuale

Flipper in stile anni ’80 per RuscaLinux. Il tavolo, «Amethyst», è visto in prospettiva come nei flipper per home computer degli anni ’80: il tavolo inclinato con la sua cassa, bumper e flipper in rilievo, i punteggi ai lati. Tavolo, grafica e suoni originali.

Lo schermo alterna i record a una partita dimostrativa; premi Spazio per giocare.

## Avvio

Dal menu delle applicazioni (cerca «RuscaPinball») o dal terminale con `ruscapinball`.
Opzioni: `--fullscreen` (schermo intero), `--version`.

## Comandi

| Azione | Tastiera | Gamepad |
|---|---|---|
| Flipper sinistro | Z, Maiusc sinistro, Ctrl sinistro, ← | LB |
| Flipper destro | M, Maiusc destro, Ctrl destro, → | RB |
| Lancio | tieni premuto Spazio o ↓, poi rilascia | A o B |
| Scuoti il tavolo | N | Y |
| Pausa | P (Esc in pausa termina la partita) | Start |
| Effetto TV | F2 | — |
| Audio | F3 | — |
| Schermo intero | F11 | — |
| Informazioni | I (dal menu) | — |
| Esci | Esc dal menu, Ctrl+Q sempre | — |

## Regole

- Tre palline a partita. Nei primi 6 secondi dopo il lancio la pallina persa viene restituita (spia lampeggiante sopra i flipper).
- **Bumper**: 100 punti, che salgono fino a 500 completando le corsie.
- **Corsie in alto** (quattro): 500 punti ciascuna; i flipper spostano le spie accese. Con tutte e quattro accese: 5.000 punti e bumper più ricchi.
- **Trappola del bonus** (in alto a sinistra, la freccia la indica): la pallina che ci passa abbastanza piano resta presa, poi viene ributtata verso i bumper. 2.000 punti più 1.000 per ogni grado del moltiplicatore, e tre passi di bonus.
- **Bersagli abbattibili** (a sinistra): 500 punti ciascuno; abbattuti tutti, 2.500 punti e moltiplicatore del bonus (fino a 5×, indicato a destra).
- **Lettere R-U-S-C-A** (a destra): 1.000 punti ciascuna; restano accese da una pallina all’altra. Completate: 15.000 punti e una pallina extra.
- **Anello del bonus** (al centro): corsie, bersagli e lettere accendono le lampade 1–9 e 10, 20, 30, fino a 39. A fine pallina le lampade si spengono una alla volta, 1.000 punti ciascuna, per il moltiplicatore.
- **SPECIAL**: con il bonus a 39 si accende la lampada SPECIAL; allora la trappola del bonus dà 25.000 punti e una pallina extra.
- Palline extra: al massimo due a partita e una per pallina. La spia **PALLINA EXTRA** a sinistra resta accesa finché non la giochi.
- **Tilt**: scuotere aiuta, ma al terzo colpo ravvicinato i flipper si spengono e il bonus è perso.

## Dati

Record in `~/.local/share/ruscapinball/scores.json`, impostazioni in `~/.config/ruscapinball/settings.json`.
Il gioco non usa la rete.

Licenza GNU GPL 3.0 — www.ruscalinux.org — info@ruscalinux.org
