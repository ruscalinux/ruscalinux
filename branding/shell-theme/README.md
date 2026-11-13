# Tema di GNOME Shell di RuscaLinux

Pacchetto `ruscalinux-shell-theme`: colora la “cornice” del desktop, cioè
quello che resta a schermo qualunque programma si apra.

| Parte | Colore (specifiche, sezione 4.1) |
|---|---|
| Barra in alto | Prugna 900 `#2d0a1d` |
| Menu rapido, calendario, notifiche, dialoghi | Prugna 800 `#3a1028` |
| Vista Attività | Prugna 850 `#230716` |
| Pulsanti e riquadri dentro i menu | Prugna 800 schiarito da GNOME (come fa con il suo grigio) |
| Testo | Crema `#fff7f0` (contrasto ≥ 8,7:1 sui fondi pieni del tema) |
| Interruttori, cursori, selezione | Accento di sistema (non modificato) |
| Errore, avviso, successo | Quelli di GNOME (non modificati) |

## Come funziona

Non sostituisce nessun file di GNOME Shell. `gnome-shell.css` è uno **strato
di soli colori** che la Shell carica sopra il proprio foglio di stile tramite
User Themes, l’estensione ufficiale di GNOME per i temi della Shell
(pacchetto `gnome-shell-extension-user-theme`). Forme, misure, caratteri e
animazioni restano quelli di GNOME.

Limiti voluti:

- **Schermata di accesso (GDM):** non è toccata. Lì le estensioni non
  girano, e cambiarla vuol dire sostituire un file di GNOME Shell.
- **Contrasto elevato:** il tema si sospende da solo (lo fa
  `ruscalinux-theme-session` del pacchetto `ruscalinux-theme`).
- **Accento:** resta quello di sistema, così la Shell e le finestre delle
  applicazioni usano lo stesso colore.

## A ogni nuova versione di GNOME

Il CSS è generato per una versione maggiore di GNOME Shell, scritta in
`GNOME_SHELL_VERSION`, e il pacchetto dipende da quella versione: passando a
una nuova Debian, apt rimuove il tema invece di lasciarne uno vecchio su una
Shell nuova, e la Shell torna ai colori di GNOME. Per rigenerarlo:

```sh
sudo apt install sassc
apt source gnome-shell
./shell-theme-prugna.py gnome-shell-*/data/theme
```

Lo script cambia sei righe nei colori di GNOME Shell, ricompila, e tiene
solo le dichiarazioni di colore. Se GNOME ha rinominato una variabile si
ferma e dice quale: si aggiorna l’elenco `PATCHES` in cima allo script.

Il CSS deriva da GNOME Shell (GPL-2.0-or-later): lo dicono l’intestazione
del file e il file `copyright` del pacchetto.

## Provare e spegnere

```sh
./make-shell-theme-deb.sh 1.0            # di norma lo lancia make-debs.sh
sudo apt install ./ruscalinux-theme_*.deb ./ruscalinux-shell-theme_*.deb
# uscire e rientrare nella sessione

gsettings get org.gnome.shell.extensions.user-theme name     # 'Adwaita-Prugna'
journalctl --user -b | grep "loading user theme"             # il file caricato

gsettings set org.gnome.shell.extensions.user-theme name "''"   # spegne
gsettings reset org.gnome.shell.extensions.user-theme name      # riaccende
```
