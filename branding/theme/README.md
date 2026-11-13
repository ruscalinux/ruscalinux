# Tema del desktop di RuscaLinux

Pacchetto `ruscalinux-theme`: dà al desktop GNOME i colori prugna/rosa di
RuscaLinux usando **solo meccanismi ufficiali**, così non si rompe quando
cambia la versione di GNOME.

| Parte del desktop | Come prende il colore | File |
|---|---|---|
| GNOME Shell, schermata di accesso, applicazioni libadwaita | Accento di sistema `pink` (GNOME ≥ 47) | `90_ruscalinux-theme.gschema.override` |
| Barra in alto, menu, notifiche, Attività | Tema della Shell, pacchetto a parte | `../shell-theme/` |
| Applicazioni GTK 3 | Tema `Adwaita-Prugna` / `Adwaita-Prugna-dark` | `Adwaita-Prugna/`, `Adwaita-Prugna-dark/` |
| Icone | Tema `Adwaita-Prugna` (pacchetto `ruscalinux-adwaita-prugna`) | `90_ruscalinux-theme.gschema.override` |
| Tool RuscaLinux | Il loro `style.css` (specifiche, sezione 4) | — |

Cosa **non** fa, di proposito: non tocca il gresource di GDM e non ridefinisce
il CSS di libadwaita, che si rompono a ogni versione di GNOME. I colori della
Shell stanno in un pacchetto separato (`ruscalinux-shell-theme`), l’unico
legato a una versione di GNOME: se un giorno non regge, lo si toglie e questo
resta.

## Il tema GTK 3

È Adwaita di GTK 3 con il blu dell’accento convertito nella palette della
sezione 4.1 delle specifiche (`#3584e4` → Prugna 600 `#7a2357`; link su fondo
scuro → Rosa 250 `#f5b8d3`). Forme, grigi e colori semantici restano quelli
di Adwaita. Con il contrasto elevato attivo GTK passa da solo al tema
HighContrast.

I file in `Adwaita-Prugna/gtk-3.0/` sono **generati**: non si modificano a
mano. GTK 3 è in sola manutenzione, quindi si rigenerano solo se cambia la
palette:

```sh
apt source gtk+3.0
./adwaita-gtk3-prugna.py gtk+3.0-*/gtk/theme/Adwaita    # serve python3-pil
```

Derivano da GTK (LGPL-2.0-or-later): lo dicono l’intestazione dei file e il
file `copyright` del pacchetto.

## L’aiuto di sessione

`ruscalinux-theme-session` parte con la sessione e fa due cose che GNOME non
fa da solo con i temi non suoi:

1. **Chiaro e scuro in GTK 3.** GTK 3 sceglie il tema dal nome, non dallo
   stile di Impostazioni → Aspetto: lo script passa da `Adwaita-Prugna` ad
   `Adwaita-Prugna-dark` e viceversa. Le applicazioni aperte cambiano subito.
2. **Contrasto elevato nella Shell.** Un tema della Shell resta attivo anche
   con il contrasto elevato e ne coprirebbe i colori: lo script lo sospende
   e lo ripristina quando il contrasto elevato si spegne.

Tocca solo `Adwaita-Prugna`: se l’utente ha scelto un altro tema non cambia
nulla.

## Costruire e provare

```sh
./make-theme-deb.sh 1.0          # di norma lo lancia make-debs.sh
GTK_THEME=Adwaita-Prugna gtk3-widget-factory        # pacchetto gtk-3-examples
GTK_THEME=Adwaita-Prugna-dark gtk3-widget-factory
```
