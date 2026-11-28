# Literata — carattere predefinito di RuscaMark

Componente esterno (specifiche, sezione 6): non è codice di RuscaLinux.

| | |
|---|---|
| Carattere | Literata 3 (versione 3.103) |
| Autori | The Literata Project Authors (TypeTogether per Google) |
| Provenienza | <https://github.com/googlefonts/literata>, cartella `fonts/ttf/`, commit `0c2761b727a1b3a7cffd313c37f0f5163dfc7a63` |
| Licenza | SIL Open Font License 1.1, testo completo in `Literata-OFL.txt` |
| File | `Literata-Regular.ttf`, `Literata-Italic.ttf`, `Literata-Bold.ttf`, `Literata-BoldItalic.ttf` (statici, non modificati) |

Literata è nata come carattere di Google Play Books: è disegnata per la
lettura lunga sullo schermo e regge bene la stampa. Copre latino (compreso
il vietnamita), greco e cirillico; per gli altri alfabeti fontconfig sceglie
da sé un carattere del sistema.

RuscaMark la registra solo per il proprio processo (`FcConfigAppFontAddFile`),
senza installarla nel sistema, e la incorpora nei PDF esportati, come la
licenza permette. Si usano i file statici e non quelli variabili: i PDF di
cairo incorporano in modo affidabile solo le istanze fisse.
