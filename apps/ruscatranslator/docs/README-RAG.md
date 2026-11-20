# RuscaTranslator — RAG linguistico (raglin.py)

Il RAG lavora solo tra **italiano e inglese**, in entrambi i versi. Tutto è locale e leggibile: niente pesi nascosti, solo file JSON e regole dichiarate.

## File

| Dove | Cosa | Chi lo modifica |
|---|---|---|
| `raglin.py` (seme interno) | Voci di base e correzioni finali generali | Il pacchetto |
| `/usr/share/ruscatranslator/rag/*.json` | Base di conoscenza del pacchetto | Il pacchetto |
| `~/.config/ruscatranslator/rag/*.json` | Voci personali: vincono su quelle del pacchetto | L'utente |
| `~/.local/share/ruscatranslator/tm_<src>_<tgt>.jsonl` | Memoria di traduzione | Il programma, al salvataggio |
| `~/.local/share/ruscatranslator/glossario_*.json` | Glossari dei documenti già tradotti | Il programma |

## Formato di una voce

```json
{"tipo": "falso_amico", "it": "attuale", "en": "current",
 "rx_it": "\\battual\\w*", "nota": "non 'actual'", "warn": "…"}
```

`tipo` può essere: idioma, falso_amico, pragmatica, terminologia, connettivo, hedging, culturema, metafora, convenzione, latinismo, stile, letteratura, regola. `rx_it` / `rx_en` sono espressioni regolari facoltative per riconoscere la voce nel testo.

## Correzioni finali (post-fix)

```json
{"tipo": "postfix", "rx_en": "\\bsmart\\s+working\\b", "fix_en": "remote work",
 "usi": ["generale", "saggistica"], "nota": "italianismo aziendale"}
```

- Valgono dopo la generazione, solo fuori da codice, link e HTML.
- `usi` (facoltativo) limita la correzione ai tipi di testo indicati: generale, saggistica, letteratura, dialoghi.
- Devono essere **di portata generale**. Una regola costruita su una singola frase di prova non migliora i testi nuovi e può peggiorarli: nella 1.99.2 le regole di questo tipo sono state tolte e, se ancora presenti nei file personali, vengono ignorate.

## Riga di comando

```bash
python3 /usr/share/ruscatranslator/raglin.py stats
python3 /usr/share/ruscatranslator/raglin.py hints testo.md it en
python3 /usr/share/ruscatranslator/raglin.py fix tradotto.md en letteratura
```
