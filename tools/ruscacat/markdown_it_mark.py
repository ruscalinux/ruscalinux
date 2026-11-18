"""markdown_it_mark.py — regola dell'evidenziato ==testo== per markdown-it-py

COMPONENTE ESTERNO dei RuscaLinux OS Tools (specifiche, sezione 6). Questo
file non è codice di RuscaLinux: è un porting in Python della regola del
plugin markdown-it-mark per markdown-it (JavaScript), scritto seguendo la
regola del barrato di markdown-it-py 3.0 (rules_inline/strikethrough.py), di
cui la regola dell'evidenziato è la stessa con «=» al posto di «~». Debian
non pacchettizza markdown-it-mark per Python.

    markdown-it-mark   https://github.com/markdown-it/markdown-it-mark
                       Copyright (c) 2014-2015 Vitaly Puzrin, Alex Kocharin
    markdown-it-py     https://github.com/executablebooks/markdown-it-py
                       Copyright (c) 2020 ExecutableBookProject

Entrambi con licenza MIT (Expat), qui sotto. Lo usa rusca_markdown.py, il
motore Markdown comune: mark_plugin(md) aggiunge la regola a un parser
markdown-it. File identico in RuscaLLama, RuscaMark, RuscaWriter e
RuscaTranslator.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from markdown_it.rules_inline.state_inline import Delimiter

__all__ = ["mark_plugin"]

_EQUALS = 0x3D


def tokenize(state, silent):
    start = state.pos
    if silent or state.src[start] != "=":
        return False
    scanned = state.scanDelims(state.pos, True)
    length = scanned.length
    if length < 2:
        return False
    if length % 2:
        token = state.push("text", "", 0)
        token.content = "="
        length -= 1
    for _ in range(0, length, 2):
        token = state.push("text", "", 0)
        token.content = "=="
        state.delimiters.append(Delimiter(marker=_EQUALS, length=0,
                                          token=len(state.tokens) - 1, end=-1,
                                          open=scanned.can_open,
                                          close=scanned.can_close))
    state.pos += scanned.length
    return True


def _balance(state, delimiters):
    lone = []
    for start in delimiters:
        if start.marker != _EQUALS or start.end == -1:
            continue
        end = delimiters[start.end]
        for index, kind, nesting in ((start.token, "mark_open", 1),
                                     (end.token, "mark_close", -1)):
            token = state.tokens[index]
            token.type, token.tag, token.nesting = kind, "mark", nesting
            token.markup, token.content = "==", ""
        before = state.tokens[end.token - 1]
        if before.type == "text" and before.content == "=":
            lone.append(end.token - 1)
    # Una sequenza dispari (===) lascia un «=» davanti: va spostato dopo i
    # mark_close che lo seguono, come fa la regola del barrato.
    while lone:
        i = lone.pop()
        j = i + 1
        while j < len(state.tokens) and state.tokens[j].type == "mark_close":
            j += 1
        j -= 1
        if i != j:
            state.tokens[i], state.tokens[j] = state.tokens[j], state.tokens[i]


def post_process(state):
    _balance(state, state.delimiters)
    for meta in state.tokens_meta:
        if meta and "delimiters" in meta:
            _balance(state, meta["delimiters"])


def mark_plugin(md):
    md.inline.ruler.before("emphasis", "mark", tokenize)
    md.inline.ruler2.before("emphasis", "mark", post_process)
