# -*- coding: utf-8 -*-
# entity.py — RuscaLinux OS Apps 1.99.3 — GPL-3.0-or-later
#
# Le entità di RuscaLLisse: un file Markdown per entità, con titoli fissi
# (Quid, Carattere, Modo di parlare, Non fa mai, Volto, Voce). Il file si
# legge con il motore Markdown comune; il prompt di sistema mette il quid
# per primo, poi il resto della personalità, poi le regole del parlato.
import os
import re
import shutil

from gi.repository import GLib

try:
    from . import rusca_markdown as md
    from . import speech_text as st
except ImportError:
    import rusca_markdown as md
    import speech_text as st

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
SYSTEM_DIR = os.path.join(BASE_DIR, "entities")
USER_DIR = os.path.join(GLib.get_user_data_dir(), "ruscallisse", "entities")

SECTIONS = {
    "quid": ("quid",),
    "character": ("carattere", "character"),
    "speech": ("modo di parlare", "way of speaking"),
    "never": ("non fa mai", "never does"),
    "face": ("volto", "face"),
    "voice": ("voce", "voice"),
}
LABELS = {
    "it": {"quid": "Il tuo quid, il centro della tua personalità",
           "character": "Carattere", "speech": "Modo di parlare",
           "never": "Non fai mai", "intro": "Sei {name}."},
    "en": {"quid": "Your quid, the core of your personality",
           "character": "Character", "speech": "Way of speaking",
           "never": "You never", "intro": "You are {name}."},
}


def ensure_default():
    """Al primo avvio le entità del pacchetto si copiano nella cartella
    dell'utente; da quel momento sono sue e non si sovrascrivono."""
    os.makedirs(USER_DIR, exist_ok=True)
    if not os.path.isdir(SYSTEM_DIR):
        return
    for name in os.listdir(SYSTEM_DIR):
        if name.endswith(".md") and not os.path.exists(os.path.join(USER_DIR, name)):
            try:
                shutil.copyfile(os.path.join(SYSTEM_DIR, name), os.path.join(USER_DIR, name))
            except OSError:
                pass


def list_entities():
    try:
        return sorted(os.path.join(USER_DIR, n) for n in os.listdir(USER_DIR) if n.endswith(".md"))
    except OSError:
        return []


def parse(text, fallback_name="Entità"):
    """Dizionario: name, quid, character, speech, never, face, voice, speed."""
    lines = text.replace("\r\n", "\n").split("\n")
    tokens = md.parser().parse("\n".join(lines))
    heads = []                    # (livello, riga d'inizio, riga dopo, titolo)
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and tok.map:
            title = tokens[i + 1].content.strip() if i + 1 < len(tokens) else ""
            heads.append((int(tok.tag[1]), tok.map[0], tok.map[1], title))
    ent = {k: "" for k in SECTIONS}
    ent["name"] = fallback_name
    for idx, (level, start, after, title) in enumerate(heads):
        if level == 1 and ent["name"] == fallback_name:
            ent["name"] = title or fallback_name
            continue
        if level != 2:
            continue
        end = len(lines)
        for lv2, s2, _a2, _t2 in heads[idx + 1:]:
            if lv2 <= 2:
                end = s2
                break
        body = "\n".join(lines[after:end]).strip()
        key = next((k for k, names in SECTIONS.items() if title.lower() in names), None)
        if key:
            ent[key] = body
    ent["voice_name"], ent["speed"] = "", 0.0
    for line in ent["voice"].splitlines():
        m = re.match(r"\s*(voce|voice)\s*:\s*(.+?)\s*$", line, re.I)
        if m and not m.group(2).startswith("<"):
            ent["voice_name"] = m.group(2)
        m = re.match(r"\s*(velocità|speed)\s*:\s*([\d.,]+)", line, re.I)
        if m:
            try:
                ent["speed"] = min(1.3, max(0.7, float(m.group(2).replace(",", "."))))
            except ValueError:
                pass
    return ent


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        text = ""
    name = os.path.splitext(os.path.basename(path))[0].capitalize()
    return parse(text, name)


def quid_missing(ent):
    q = ent.get("quid", "").strip()
    return not q or q == st.QUID_DA_SCRIVERE or q.startswith("<")


def system_prompt(ent, lang, max_words, emotions=True):
    lab = LABELS.get(lang, LABELS["en"])
    parts = [lab["intro"].format(name=ent["name"])]
    if not quid_missing(ent):
        parts.append(f"{lab['quid']}:\n{ent['quid']}")
    for key in ("character", "speech", "never"):
        if ent.get(key):
            parts.append(f"{lab[key]}:\n{ent[key]}")
    parts.append(st.rules(lang, max_words, emotions))
    return "\n\n".join(parts)
