#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# RuscaWriter — three-column writing editor for non-fiction
# Copyright (C) 2026  Nunzio Curcuruto
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
EN — MDict (.mdx) dictionary reader.

This module is INDEPENDENT from the graphical interface (it never imports
GTK) and uses only the Python standard library: zlib for decompression,
sqlite3 for the on-disk index, struct for the binary layout. It can be
tested on its own and reused by other tools.

The .mdx format is not documented by its authors; the layout implemented
here comes from the public reverse engineering of the format and is
written from scratch for this project. A file is read in four steps:

    1. header      an XML string in UTF-16LE, with its adler32
    2. key index   the list of headwords and where their text starts
    3. record info the size of every block of definitions
    4. records     the definitions, one compressed block at a time

Only step 4 happens while you write: opening a dictionary builds the index
once and keeps it in a sqlite file under the cache folder, so the second
time the dictionary is ready at once and a lookup reads a single block.

What is deliberately NOT supported: registered dictionaries, whose records
are encrypted with a purchase key (Encrypted=1). They are refused with a
clear message instead of being half-read.

IT — Lettore di dizionari MDict (.mdx).

Questo modulo è INDIPENDENTE dall'interfaccia grafica (non importa mai GTK)
e usa soltanto la libreria standard di Python: zlib per la decompressione,
sqlite3 per l'indice su disco, struct per la struttura binaria. Può essere
testato da solo ed essere riusato da altri strumenti.

Il formato .mdx non è documentato dai suoi autori; la struttura qui
implementata viene dallo studio pubblico del formato ed è riscritta da zero
per questo progetto. Un file si legge in quattro passi:

    1. intestazione  una stringa XML in UTF-16LE, con il suo adler32
    2. indice chiavi l'elenco dei lemmi e dove comincia il loro testo
    3. info record   la dimensione di ogni blocco di definizioni
    4. record        le definizioni, un blocco compresso per volta

Solo il passo 4 avviene mentre scrivi: aprire un dizionario costruisce
l'indice una volta e lo tiene in un file sqlite nella cartella cache, così
la seconda volta il dizionario è pronto subito e una ricerca legge un solo
blocco.

Cosa NON è supportato di proposito: i dizionari registrati, i cui record
sono cifrati con una chiave d'acquisto (Encrypted=1). Vengono rifiutati con
un messaggio chiaro invece di essere letti a metà.
"""
import os
import re
import zlib
import difflib
import html
import html.parser
import unicodedata
import struct
import sqlite3
import hashlib
import threading
from collections import OrderedDict

__all__ = [
    "MdxError",
    "MdxUnsupported",
    "MdxDictionary",
    "MddResources",
    "entry_images",
    "DictionarySet",
    "to_pango_markup",
    "to_plain_text",
    "shorten",
    "NEAR_RATIO",
    "inflections",
    "cache_dir",
    "ripemd128",
]

# EN: schema version of the sqlite index. Bump it when the tables change:
#     an old cache is then rebuilt instead of being misread.
# IT: versione dello schema dell'indice sqlite. Da aumentare quando le
#     tabelle cambiano: una cache vecchia viene così ricostruita invece di
#     essere letta male.
INDEX_SCHEMA = 2

# EN/IT: sanity limits. A .mdx is an untrusted file: every number read from
# it is checked against these ceilings before being used to allocate memory
# or to seek. / limiti di sicurezza. Un .mdx è un file non fidato: ogni
# numero letto viene confrontato con questi tetti prima di essere usato per
# allocare memoria o per spostarsi nel file.
MAX_HEADER = 8 * 1024 * 1024          # 8 MB di intestazione XML
MAX_BLOCK = 256 * 1024 * 1024         # 256 MB per blocco decompresso
MAX_ENTRIES = 50_000_000              # 50 milioni di lemmi
MAX_BLOCKS = 5_000_000                # 5 milioni di blocchi

# EN/IT: how many decompressed record blocks to keep in memory. Blocks are
# a few dozen KB each, so this is a small cache that makes the common case
# (looking up several words in the same page of the dictionary) instant.
CACHE_BLOCKS = 12

# EN/IT: how close a headword must be to be offered when the exact word is
# not in the dictionary. Tuned on plurals and verb endings across several
# languages: high enough that an unrelated word is never proposed, low enough
# that "mangiando" reaches *mangiare*. It is one number, in one place, so it
# can be moved. / quanto vicino deve essere un lemma per essere proposto
# quando la parola esatta non c'è nel dizionario. Tarato su plurali e
# desinenze verbali di più lingue: alto abbastanza da non proporre mai una
# parola senza rapporto, basso abbastanza perché "mangiando" arrivi a
# *mangiare*. È un numero solo, in un posto solo, così si può spostare.
NEAR_RATIO = 0.58

_LINK_RE = re.compile(r"^@@@LINK=(.*?)\s*$", re.S)
_ATTR_RE = re.compile(r'(\w+)="((?:[^"\\]|\\.)*)"')


class MdxError(Exception):
    """EN: the file is not a readable .mdx (broken or not an .mdx at all).
    IT: il file non è un .mdx leggibile (rovinato o non è affatto un .mdx)."""


class MdxUnsupported(MdxError):
    """EN: valid .mdx, but using a feature this reader does not implement.
    IT: .mdx valido, ma usa una funzione che questo lettore non implementa."""


# ---------------------------------------------------------------------------
# RIPEMD-128
# ---------------------------------------------------------------------------
# EN: needed only by dictionaries whose key index is scrambled (Encrypted=2).
#     hashlib does not provide RIPEMD-128, so it is implemented here. It is
#     used as a key derivation step, never to protect anything of ours.
# IT: serve solo ai dizionari con l'indice delle chiavi offuscato
#     (Encrypted=2). hashlib non fornisce RIPEMD-128, quindi è implementato
#     qui. Serve a derivare una chiave, mai a proteggere qualcosa di nostro.

_RMD_R = (
    tuple(range(16)) +
    (7, 4, 13, 1, 10, 6, 15, 3, 12, 0, 9, 5, 2, 14, 11, 8) +
    (3, 10, 14, 4, 9, 15, 8, 1, 2, 7, 0, 6, 13, 11, 5, 12) +
    (1, 9, 11, 10, 0, 8, 12, 4, 13, 3, 7, 15, 14, 5, 6, 2)
)
_RMD_RR = (
    (5, 14, 7, 0, 9, 2, 11, 4, 13, 6, 15, 8, 1, 10, 3, 12) +
    (6, 11, 3, 7, 0, 13, 5, 10, 14, 15, 8, 12, 4, 9, 1, 2) +
    (15, 5, 1, 3, 7, 14, 6, 9, 11, 8, 12, 2, 10, 0, 4, 13) +
    (8, 6, 4, 1, 3, 11, 15, 0, 5, 12, 2, 13, 9, 7, 10, 14)
)
_RMD_S = (
    (11, 14, 15, 12, 5, 8, 7, 9, 11, 13, 14, 15, 6, 7, 9, 8) +
    (7, 6, 8, 13, 11, 9, 7, 15, 7, 12, 15, 9, 11, 7, 13, 12) +
    (11, 13, 6, 7, 14, 9, 13, 15, 14, 8, 13, 6, 5, 12, 7, 5) +
    (11, 12, 14, 15, 14, 15, 9, 8, 9, 14, 5, 6, 8, 6, 5, 12)
)
_RMD_SS = (
    (8, 9, 9, 11, 13, 15, 15, 5, 7, 7, 8, 11, 14, 14, 12, 6) +
    (9, 13, 15, 7, 12, 8, 9, 11, 7, 7, 12, 7, 6, 15, 13, 11) +
    (9, 7, 15, 11, 8, 6, 6, 14, 12, 13, 5, 14, 13, 13, 7, 5) +
    (15, 5, 8, 11, 14, 14, 6, 14, 6, 9, 12, 9, 12, 5, 15, 8)
)
_RMD_K = (0x00000000, 0x5A827999, 0x6ED9EBA1, 0x8F1BBCDC)
_RMD_KK = (0x50A28BE6, 0x5C4DD124, 0x6D703EF3, 0x00000000)


def _rol(x, n):
    x &= 0xFFFFFFFF
    return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF


def _rmd_f(j, x, y, z):
    if j < 16:
        return x ^ y ^ z
    if j < 32:
        return (x & y) | (~x & 0xFFFFFFFF & z)
    if j < 48:
        return (x | (~y & 0xFFFFFFFF)) ^ z
    return (x & z) | (y & (~z & 0xFFFFFFFF))


def ripemd128(data):
    """EN: RIPEMD-128 digest of *data*, 16 bytes.
    IT: digest RIPEMD-128 di *data*, 16 byte."""
    msg = bytearray(data)
    length = len(msg) * 8
    msg.append(0x80)
    while len(msg) % 64 != 56:
        msg.append(0x00)
    msg += struct.pack("<Q", length & 0xFFFFFFFFFFFFFFFF)

    h0, h1, h2, h3 = 0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476
    for off in range(0, len(msg), 64):
        x = struct.unpack("<16I", msg[off:off + 64])
        a, b, c, d = h0, h1, h2, h3
        aa, bb, cc, dd = h0, h1, h2, h3
        for j in range(64):
            t = _rol((a + _rmd_f(j, b, c, d) + x[_RMD_R[j]]
                      + _RMD_K[j // 16]) & 0xFFFFFFFF, _RMD_S[j])
            a, d, c, b = d, c, b, t
            t = _rol((aa + _rmd_f(63 - j, bb, cc, dd) + x[_RMD_RR[j]]
                      + _RMD_KK[j // 16]) & 0xFFFFFFFF, _RMD_SS[j])
            aa, dd, cc, bb = dd, cc, bb, t
        t = (h1 + c + dd) & 0xFFFFFFFF
        h1 = (h2 + d + aa) & 0xFFFFFFFF
        h2 = (h3 + a + bb) & 0xFFFFFFFF
        h3 = (h0 + b + cc) & 0xFFFFFFFF
        h0 = t
    return struct.pack("<4I", h0, h1, h2, h3)


def _unscramble(data, key):
    """EN: undo the byte scrambling MDict applies to an encrypted key index.
    IT: annulla il rimescolamento dei byte che MDict applica a un indice
    delle chiavi cifrato."""
    out = bytearray(data)
    prev = 0x36
    klen = len(key)
    for i in range(len(out)):
        cur = out[i]
        t = ((cur >> 4) | (cur << 4)) & 0xFF
        out[i] = t ^ prev ^ (i & 0xFF) ^ key[i % klen]
        prev = cur
    return bytes(out)


# ---------------------------------------------------------------------------
# EN/IT: helpers
# ---------------------------------------------------------------------------

def cache_dir():
    """EN: folder where the dictionary indexes are kept.
    IT: cartella dove vengono tenuti gli indici dei dizionari."""
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "ruscawriter", "mdict")


def _inflate(blob, expected=None):
    """EN: zlib decompression with a ceiling, so a malicious file cannot
    ask us for gigabytes of memory.
    IT: decompressione zlib con un tetto, così un file malevolo non può
    chiederci gigabyte di memoria."""
    limit = MAX_BLOCK if expected is None else min(expected, MAX_BLOCK)
    try:
        obj = zlib.decompressobj()
        out = obj.decompress(blob, limit + 1)
    except zlib.error as exc:
        raise MdxError("dati compressi non validi / invalid compressed data") from exc
    if len(out) > limit:
        raise MdxError("blocco troppo grande / block too large")
    return out


def _lzo1x(src, out_len):
    """EN: LZO1X decompression, written from the published algorithm. Old
    dictionaries (engine 1.x) and some 2.x ones compress with LZO, and Debian
    ships no LZO module for Python, so it lives here. It is the "safe"
    variant: every read and every back-reference is checked, so a damaged
    file raises MdxError instead of reading out of bounds.
    IT: decompressione LZO1X, scritta dall'algoritmo pubblicato. I dizionari
    vecchi (motore 1.x) e alcuni 2.x comprimono con LZO, e Debian non ha un
    modulo LZO per Python, quindi vive qui. E' la variante "sicura": ogni
    lettura e ogni rimando all'indietro sono controllati, così un file
    rovinato solleva MdxError invece di leggere fuori dai limiti."""
    if out_len > MAX_BLOCK:
        raise MdxError("blocco troppo grande / block too large")
    src = memoryview(bytes(src))
    n = len(src)
    out = bytearray()
    ip = 0

    def need(k):
        if ip + k > n:
            raise MdxError("LZO: dati troncati / truncated data")

    def lit(count):
        nonlocal ip
        need(count)
        out.extend(src[ip:ip + count])
        ip += count
        if len(out) > out_len:
            raise MdxError("LZO: uscita oltre il previsto / output overrun")

    def ext(t, base):
        nonlocal ip
        while True:
            need(1)
            if src[ip] != 0:
                break
            t += 255
            ip += 1
            if t > out_len:
                raise MdxError("LZO: sequenza troppo lunga / run too long")
        t += base + src[ip]
        ip += 1
        return t

    def copy(dist, length):
        start = len(out) - dist
        if start < 0:
            raise MdxError("LZO: rimando non valido / invalid back-reference")
        if len(out) + length > out_len:
            raise MdxError("LZO: uscita oltre il previsto / output overrun")
        if dist >= length:
            out.extend(out[start:start + length])
        else:
            chunk = out[start:]
            reps, rest = divmod(length, dist)
            out.extend(chunk * reps + chunk[:rest])

    need(1)
    state = "loop"
    t = 0
    if src[0] > 17:
        t = src[0] - 17
        ip = 1
        lit(t)
        state = "first" if t >= 4 else "match_next_read"
    while True:
        if state == "loop":
            need(1)
            t = src[ip]; ip += 1
            if t >= 16:
                state = "match"
                continue
            if t == 0:
                t = ext(0, 15)
            lit(t + 3)
            state = "first"
            continue
        if state == "first":
            need(1)
            t = src[ip]; ip += 1
            if t >= 16:
                state = "match"
                continue
            need(1)
            dist = 1 + 0x0800 + (t >> 2) + (src[ip] << 2); ip += 1
            copy(dist, 3)
            state = "done"
            continue
        if state == "match_next_read":
            need(1)
            t = src[ip]; ip += 1
            state = "match"
            continue
        if state == "match":
            if t >= 64:
                need(1)
                dist = 1 + ((t >> 2) & 7) + (src[ip] << 3); ip += 1
                copy(dist, (t >> 5) + 1)
            elif t >= 32:
                t &= 31
                if t == 0:
                    t = ext(0, 31)
                need(2)
                dist = 1 + ((src[ip] >> 2) + (src[ip + 1] << 6)); ip += 2
                copy(dist, t + 2)
            elif t >= 16:
                high = (t & 8) << 11
                t &= 7
                if t == 0:
                    t = ext(0, 7)
                need(2)
                dist = high + ((src[ip] >> 2) + (src[ip + 1] << 6)); ip += 2
                if dist == 0:
                    break                       # end of stream
                copy(dist + 0x4000, t + 2)
            else:
                need(1)
                dist = 1 + (t >> 2) + (src[ip] << 2); ip += 1
                copy(dist, 2)
            state = "done"
            continue
        if state == "done":
            t = src[ip - 2] & 3
            if t == 0:
                state = "loop"
                continue
            lit(t)
            state = "match_next_read"
            continue
    if len(out) != out_len:
        raise MdxError("LZO: dimensione incoerente / size mismatch")
    return bytes(out)


# EN/IT: ciphers needed to read protected indexes / cifrari per leggere
# gli indici protetti
_M32 = 0xFFFFFFFF
_M64 = 0xFFFFFFFFFFFFFFFF

def _r32(x, n):
    return ((x << n) | (x >> (32 - n))) & _M32

def _salsa20_8(data, key):
    """EN: Salsa20/8 with a 128-bit key and a zero nonce, the cipher MDict
    uses for encrypted blocks. Used only to READ a dictionary.
    IT: Salsa20/8 con chiave a 128 bit e nonce nullo, il cifrario che MDict
    usa per i blocchi cifrati. Serve solo a LEGGERE un dizionario."""
    if len(key) != 16:
        raise ValueError("key must be 16 bytes")
    k = struct.unpack("<4I", key)
    c = (0x61707865, 0x3120646E, 0x79622D36, 0x6B206574)   # "expand 16-byte k"
    out = bytearray(data)
    for blk in range(0, len(out), 64):
        ctr = blk // 64
        x = [c[0], k[0], k[1], k[2], k[3], c[1], 0, 0,
             ctr & _M32, (ctr >> 32) & _M32, c[2], k[0], k[1], k[2], k[3], c[3]]
        s = list(x)
        for _ in range(4):        # 8 rounds = 4 double rounds
            for a, b, cc, d in ((0, 4, 8, 12), (5, 9, 13, 1), (10, 14, 2, 6), (15, 3, 7, 11),
                                (0, 1, 2, 3), (5, 6, 7, 4), (10, 11, 8, 9), (15, 12, 13, 14)):
                s[b] ^= _r32((s[a] + s[d]) & _M32, 7)
                s[cc] ^= _r32((s[b] + s[a]) & _M32, 9)
                s[d] ^= _r32((s[cc] + s[b]) & _M32, 13)
                s[a] ^= _r32((s[d] + s[cc]) & _M32, 18)
        stream = struct.pack("<16I", *((s[i] + x[i]) & _M32 for i in range(16)))
        chunk = out[blk:blk + 64]
        out[blk:blk + 64] = bytes(p ^ q for p, q in zip(chunk, stream))
    return bytes(out)

_P1, _P2, _P3, _P4, _P5 = (0x9E3779B185EBCA87, 0xC2B2AE3D27D4EB4F,
                           0x165667B19E3779F9, 0x85EBCA77C2B2AE63,
                           0x27D4EB2F165667C5)

def _r64(x, n):
    return ((x << n) | (x >> (64 - n))) & _M64

def _xround(acc, lane):
    acc = (acc + lane * _P2) & _M64
    return (_r64(acc, 31) * _P1) & _M64

def _xxh64(data, seed=0):
    """EN: XXH64 digest, 8 big-endian bytes. MDict 3 derives its block key
    from the dictionary UUID with it. IT: digest XXH64, 8 byte big-endian.
    MDict 3 lo usa per ricavare la chiave dei blocchi dall'UUID."""
    n = len(data)
    i = 0
    if n >= 32:
        v = [(seed + _P1 + _P2) & _M64, (seed + _P2) & _M64, seed & _M64,
             (seed - _P1) & _M64]
        while i + 32 <= n:
            lanes = struct.unpack_from("<4Q", data, i)
            v = [_xround(v[j], lanes[j]) for j in range(4)]
            i += 32
        h = (_r64(v[0], 1) + _r64(v[1], 7) + _r64(v[2], 12) + _r64(v[3], 18)) & _M64
        for lane in v:
            h ^= _xround(0, lane)
            h = (h * _P1 + _P4) & _M64
    else:
        h = (seed + _P5) & _M64
    h = (h + n) & _M64
    while i + 8 <= n:
        h ^= _xround(0, struct.unpack_from("<Q", data, i)[0])
        h = (_r64(h, 27) * _P1 + _P4) & _M64
        i += 8
    if i + 4 <= n:
        h ^= (struct.unpack_from("<I", data, i)[0] * _P1) & _M64
        h = (_r64(h, 23) * _P2 + _P3) & _M64
        i += 4
    while i < n:
        h ^= (data[i] * _P5) & _M64
        h = (_r64(h, 11) * _P1) & _M64
        i += 1
    h ^= h >> 33
    h = (h * _P2) & _M64
    h ^= h >> 29
    h = (h * _P3) & _M64
    h ^= h >> 32
    return struct.pack(">Q", h)

def _decode_block(blob, expected, version, key=None):
    """EN: one key or record block. The first 4 bytes say how it is stored:
    the low 4 bits the compression (0 none, 1 LZO, 2 zlib), the next 4 the
    encryption (0 none, 1 MDict scrambling, 2 Salsa20/8) and the next 8 how
    many leading bytes are encrypted. Then 4 bytes of adler32: of the plain
    data up to engine 2, of the still-compressed data from engine 3.
    IT: un blocco di chiavi o di record. I primi 4 byte dicono come e'
    registrato: i 4 bit bassi la compressione (0 nessuna, 1 LZO, 2 zlib), i
    4 successivi la cifratura (0 nessuna, 1 rimescolamento MDict, 2
    Salsa20/8) e gli 8 dopo quanti byte iniziali sono cifrati. Poi 4 byte di
    adler32: dei dati in chiaro fino al motore 2, dei dati ancora compressi
    dal motore 3."""
    if len(blob) < 8:
        raise MdxError("blocco troncato / truncated block")
    info = struct.unpack("<I", blob[:4])[0]
    comp, enc, enc_size = info & 0xF, (info >> 4) & 0xF, (info >> 8) & 0xFF
    checksum = struct.unpack(">I", blob[4:8])[0]
    body = blob[8:]
    if enc:
        k = key if key is not None else ripemd128(blob[4:8])
        head, tail = body[:enc_size], body[enc_size:]
        if enc == 1:
            body = _unscramble(head, k) + tail
        elif enc == 2:
            body = _salsa20_8(head, k) + tail
        else:
            raise MdxUnsupported("cifratura sconosciuta / unknown encryption")
    if version >= 3 and zlib.adler32(body) & 0xFFFFFFFF != checksum:
        raise MdxError("blocco rovinato / corrupt block")
    if comp == 2:
        data = _inflate(body, expected)
    elif comp == 0:
        data = bytes(body)
    elif comp == 1:
        if expected is None:
            raise MdxError("blocco LZO senza dimensione / LZO block without size")
        data = _lzo1x(body, expected)
    else:
        raise MdxUnsupported(
            "compressione non supportata / unsupported compression")
    if expected is not None and len(data) != expected:
        raise MdxError("dimensione del blocco incoerente / block size mismatch")
    if version < 3 and zlib.adler32(data) & 0xFFFFFFFF != checksum:
        raise MdxError("blocco rovinato / corrupt block")
    return data


def _fold(text):
    """EN: drop the accents, for comparing words only. A writer who types
    "citta" should still reach *città*; the headword itself is never changed.
    IT: toglie gli accenti, solo per confrontare parole. Chi scrive "citta"
    deve comunque arrivare a *città*; il lemma in sé non viene mai toccato."""
    return "".join(c for c in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(c))


def _similarity(word, candidate):
    """EN: how close two words are, from 0.0 to 1.0, weighted towards the
    beginning. Two words that start alike and end differently are the normal
    shape of a plural or a conjugation; two words that start differently are
    a different word, however many letters they share.
    IT: quanto due parole sono vicine, da 0.0 a 1.0, con più peso all'inizio.
    Due parole che cominciano uguali e finiscono diverse sono la forma
    normale di un plurale o di una coniugazione; due parole che cominciano
    diverse sono un'altra parola, per quante lettere abbiano in comune."""
    if not word or not candidate:
        return 0.0
    if word == candidate:
        return 1.0
    shared = 0
    for a, b in zip(word, candidate):
        if a != b:
            break
        shared += 1
    if shared < 2:
        return 0.0
    base = difflib.SequenceMatcher(None, word, candidate).ratio()
    # EN/IT: the shared opening counts as much as the overall likeness.
    head = shared / max(len(word), len(candidate))
    return (base + head) / 2


def _canonical_encoding(name):
    n = (name or "").strip().upper().replace("-", "").replace("_", "")
    return {
        "": "utf-8",
        "UTF8": "utf-8",
        "UTF16": "utf-16-le",
        "UTF16LE": "utf-16-le",
        # EN/IT: GB18030 is a superset of both / GB18030 li contiene entrambi
        "GBK": "gb18030",
        "GB2312": "gb18030",
        "GB18030": "gb18030",
        "BIG5": "big5",
        "ASCII": "ascii",
    }.get(n, "utf-8")


# ---------------------------------------------------------------------------
# EN/IT: the dictionary
# ---------------------------------------------------------------------------

class MdxDictionary:
    """EN — one open .mdx dictionary.

    Opening is cheap: the header is read, and the index is taken from the
    sqlite cache if it is there and still matches the file. If it is not,
    call build_index() (from a worker thread, with a progress callback)
    before looking words up.

    IT — un dizionario .mdx aperto.

    Aprirlo costa poco: si legge l'intestazione e l'indice si prende dalla
    cache sqlite se c'è e corrisponde ancora al file. Se non c'è, chiama
    build_index() (da un thread di lavoro, con una callback di
    avanzamento) prima di cercare le parole.
    """

    # EN/IT: True only in MddResources / vero solo in MddResources
    RESOURCE = False

    def __init__(self, path, cache_folder=None):
        self.path = os.path.abspath(path)
        self._res = None                  # file .mdd collegati, aperti al bisogno
        if self.path.lower().endswith(".mdd") and not self.RESOURCE:
            # EN/IT: the .mdd holds pictures, sounds and style sheets, not
            # words. Its header looks like an .mdx one, so without this check
            # it would be "accepted" and then never answer.
            raise MdxError(
                "questo e' il file delle risorse (.mdd): aggiungi il file "
                ".mdx con lo stesso nome / this is the resource file (.mdd): "
                "add the .mdx file with the same name")
        try:
            st = os.stat(self.path)
        except OSError as exc:
            raise MdxError(f"file non leggibile / unreadable file: {path}") from exc
        self._size = st.st_size
        self._mtime = int(st.st_mtime)
        self._lock = threading.RLock()
        self._blocks = OrderedDict()      # cache dei blocchi decompressi
        self._fh = None
        self._db = None
        self._cache_folder = cache_folder or cache_dir()

        try:
            with open(self.path, "rb") as f:
                self._read_header(f)
                self._key_section_offset = f.tell()
        except OSError as exc:
            raise MdxError(f"file non leggibile / unreadable file: {path}") from exc

        self._open_cache()

    # -- EN/IT: header -----------------------------------------------------

    def _read_header(self, f):
        raw = f.read(4)
        if len(raw) < 4:
            raise MdxError("file vuoto o troppo corto / empty or too short")
        size = struct.unpack(">I", raw)[0]
        if size < 4 or size > MAX_HEADER or size > self._size:
            raise MdxError("intestazione non plausibile / implausible header")
        blob = f.read(size)
        if len(blob) != size:
            raise MdxError("intestazione troncata / truncated header")
        checksum = f.read(4)
        if len(checksum) != 4:
            raise MdxError("intestazione senza checksum / header without checksum")
        if zlib.adler32(blob) & 0xFFFFFFFF != struct.unpack("<I", checksum)[0]:
            raise MdxError("intestazione rovinata / corrupt header")
        # EN/IT: UTF-16LE ending in two NULs is the norm; a few builders
        # write UTF-8 ending in one. / UTF-16LE con due NUL in fondo e' la
        # norma; qualche compilatore scrive UTF-8 con un NUL solo.
        try:
            if blob[-2:] == b"\x00\x00" or blob[1:2] == b"\x00":
                text = blob.decode("utf-16-le").rstrip("\x00")
            else:
                text = blob.decode("utf-8").rstrip("\x00")
        except UnicodeDecodeError as exc:
            raise MdxError("intestazione illeggibile / unreadable header") from exc

        attrs = {}
        for key, value in _ATTR_RE.findall(text):
            # EN/IT: every HTML entity, numeric ones included (&#x27;)
            attrs[key] = html.unescape(value)
        self.header = attrs

        if "GeneratedByEngineVersion" not in attrs and "Title" not in attrs:
            raise MdxError("non sembra un file .mdx / does not look like .mdx")

        try:
            self.version = float(attrs.get("GeneratedByEngineVersion", "2.0"))
        except ValueError:
            self.version = 2.0
        self.encoding = _canonical_encoding(attrs.get("Encoding", "UTF-8"))
        if self.version >= 3:
            self.encoding = "utf-8"            # MDict 3 e' solo UTF-8
        elif self.RESOURCE:
            # EN/IT: an .mdd names its files in UTF-16 whatever the header
            # says / un .mdd nomina i suoi file in UTF-16 qualunque cosa dica
            # l'intestazione
            self.encoding = "utf-16-le"
        self.title = attrs.get("Title", "") or os.path.basename(self.path)
        self.description = attrs.get("Description", "")
        self.strip_key = attrs.get("StripKey", "Yes").strip().lower() != "no"

        enc = attrs.get("Encrypted", "No").strip()
        if enc in ("", "No"):
            self.encrypted = 0
        elif enc == "Yes":
            self.encrypted = 1
        else:
            try:
                self.encrypted = int(enc)
            except ValueError:
                self.encrypted = 0
        # EN/IT: engine 3 encrypts every block with a key taken from the
        # dictionary's own UUID: readable without any purchase code.
        # / il motore 3 cifra i blocchi con una chiave presa dall'UUID del
        # dizionario stesso: leggibile senza alcun codice d'acquisto.
        self._key = None
        if self.version >= 3:
            uuid = attrs.get("UUID", "").encode("utf-8")
            if uuid:
                mid = (len(uuid) + 1) // 2
                self._key = _xxh64(uuid[:mid]) + _xxh64(uuid[mid:])
        elif self.encrypted & 1:
            raise MdxUnsupported(
                "dizionario registrato (record cifrati), non supportato / "
                "registered dictionary (encrypted records), not supported")

        self._num_width = 8 if self.version >= 2.0 else 4
        self._num_fmt = ">Q" if self.version >= 2.0 else ">I"

        # EN/IT: compact dictionaries replace repeated HTML with `n` marks,
        # declared in the header as groups of three lines: number, opening,
        # closing. / i dizionari compatti sostituiscono l'HTML ripetuto con
        # segni `n`, dichiarati nell'intestazione a gruppi di tre righe:
        # numero, apertura, chiusura.
        self._styles = {}
        lines = attrs.get("StyleSheet", "").splitlines()
        for i in range(0, len(lines) - 2, 3):
            self._styles[lines[i].strip()] = (lines[i + 1], lines[i + 2])

    # -- EN/IT: sqlite index ----------------------------------------------

    def _cache_path(self):
        digest = hashlib.sha256(self.path.encode("utf-8")).hexdigest()[:16]
        return os.path.join(self._cache_folder, f"{digest}.sqlite")

    def _connect(self, path):
        db = sqlite3.connect(path, check_same_thread=False)
        db.execute("PRAGMA journal_mode=OFF")
        db.execute("PRAGMA synchronous=OFF")
        return db

    def _open_cache(self):
        """EN: attach to the cached index if it still matches the file.
        IT: si aggancia all'indice in cache se corrisponde ancora al file."""
        self.indexed = False
        try:
            os.makedirs(self._cache_folder, exist_ok=True)
            self._cache_file = self._cache_path()
            self._db = self._connect(self._cache_file)
        except (OSError, sqlite3.Error):
            # EN/IT: no writable cache: work in memory, rebuilt every time.
            self._cache_file = None
            self._db = self._connect(":memory:")
            return
        try:
            rows = dict(self._db.execute("SELECT k, v FROM meta").fetchall())
        except sqlite3.Error:
            return
        if (rows.get("schema") == str(INDEX_SCHEMA)
                and rows.get("size") == str(self._size)
                and rows.get("mtime") == str(self._mtime)
                and rows.get("complete") == "1"):
            self.entry_count = int(rows.get("entries", "0"))
            self.indexed = True

    def build_index(self, progress=None):
        """EN: read the key index and the record table, and store them.
        Slow the first time (seconds on a large dictionary), instant after.
        *progress* is called with a fraction between 0.0 and 1.0.

        IT: legge l'indice delle chiavi e la tabella dei record, e li
        registra. Lento la prima volta (secondi su un dizionario grande),
        immediato dopo. *progress* viene chiamata con una frazione fra 0.0
        e 1.0."""
        with self._lock:
            if self.indexed:
                return
            self._blocks.clear()
            db = self._db
            db.executescript(
                "DROP TABLE IF EXISTS meta;"
                "DROP TABLE IF EXISTS blocks;"
                "DROP TABLE IF EXISTS entries;"
                "CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT);"
                "CREATE TABLE blocks (i INTEGER PRIMARY KEY, off INTEGER,"
                " comp INTEGER, decomp INTEGER, start INTEGER);"
                "CREATE TABLE entries (id INTEGER PRIMARY KEY, norm TEXT,"
                " word TEXT, a INTEGER, b INTEGER);")
            try:
                with open(self.path, "rb") as f:
                    f.seek(self._key_section_offset)
                    if self.version >= 3:
                        keys = self._read_v3(f, db, progress)
                    else:
                        keys = self._read_keys(f, progress)
                        self._read_record_table(f, db)
                    self._store_keys(db, keys)
                    total = db.execute(
                        "SELECT COALESCE(MAX(start + decomp), 0) FROM blocks"
                    ).fetchone()[0]
                    db.execute("UPDATE entries SET b = ? WHERE b < 0", (total,))
            except MdxError:
                raise
            except (OSError, ValueError, IndexError, KeyError, OverflowError,
                    struct.error, sqlite3.Error, MemoryError) as exc:
                # EN/IT: whatever goes wrong inside a strange file becomes a
                # message the interface can show, never a dead thread.
                # / qualunque cosa vada storta dentro un file strano diventa
                # un messaggio che l'interfaccia puo' mostrare, mai un thread
                # morto in silenzio.
                raise MdxError(f"dizionario illeggibile / unreadable "
                               f"dictionary ({type(exc).__name__}: {exc})") from exc
            db.execute("CREATE INDEX idx_norm ON entries(norm)")
            db.executemany(
                "INSERT OR REPLACE INTO meta (k, v) VALUES (?, ?)",
                [("schema", str(INDEX_SCHEMA)),
                 ("size", str(self._size)),
                 ("mtime", str(self._mtime)),
                 ("entries", str(len(keys))),
                 ("title", self.title),
                 ("complete", "1")])
            db.commit()
            self.entry_count = len(keys)
            self.indexed = True
            if progress:
                progress(1.0)

    def _read_exact(self, f, n, what):
        if n < 0 or n > self._size:
            raise MdxError(f"{what}: dimensione non plausibile / implausible size")
        blob = f.read(n)
        if len(blob) != n:
            raise MdxError(f"{what}: file troncato / truncated file")
        return blob

    def _read_keys(self, f, progress=None):
        """EN: the list of (headword, start offset of its text).
        IT: l'elenco di (lemma, offset iniziale del suo testo)."""
        w, fmt = self._num_width, self._num_fmt
        if self.version >= 2.0:
            head = self._read_exact(f, w * 5, "indice chiavi")
            checksum = self._read_exact(f, 4, "indice chiavi")
            if zlib.adler32(head) & 0xFFFFFFFF != struct.unpack(">I", checksum)[0]:
                raise MdxError("indice delle chiavi rovinato / corrupt key index")
            (n_blocks, n_entries, info_decomp,
             info_size, blocks_size) = struct.unpack(">5Q", head)
        else:
            head = self._read_exact(f, w * 4, "indice chiavi")
            n_blocks, n_entries, info_size, blocks_size = struct.unpack(">4I", head)
            info_decomp = None

        if not (0 < n_blocks <= MAX_BLOCKS) or not (0 < n_entries <= MAX_ENTRIES):
            raise MdxError("indice delle chiavi non plausibile / implausible key index")

        info = self._read_exact(f, info_size, "info chiavi")
        if self.version >= 2.0:
            if self.encrypted & 2:
                if len(info) < 8:
                    raise MdxError("info chiavi troncate / truncated key info")
                key = ripemd128(info[4:8] + struct.pack("<I", 0x3695))
                info = info[:8] + _unscramble(info[8:], key)
            info = _decode_block(info, info_decomp, self.version)
        sizes = self._decode_key_info(info, n_blocks)
        if sum(c for c, _ in sizes) != blocks_size:
            raise MdxError("blocchi delle chiavi incoerenti / inconsistent key blocks")

        keys = []
        seen = 0
        for i, (comp, decomp) in enumerate(sizes):
            blob = self._read_exact(f, comp, "blocco chiavi")
            block = _decode_block(blob, decomp, self.version, self._key)
            keys.extend(self._split_key_block(block))
            seen += 1
            if progress and (seen % 16 == 0 or seen == n_blocks):
                # EN/IT: keys are about half of the work, records the rest.
                progress(0.5 * seen / n_blocks)
        if len(keys) != n_entries:
            raise MdxError("numero di lemmi incoerente / headword count mismatch")
        return keys

    def _read_v3(self, f, db, progress=None):
        """EN — engine 3 layout. After the header come tagged sections, each
        a 4-byte type and an 8-byte size: 1 records, 2 record index, 3 keys,
        4 key index. Keys and records are runs of blocks, each preceded by
        its plain and stored size. Returns the key list and fills the block
        table, so the rest of the reader does not know which engine wrote
        the file.

        IT — struttura del motore 3. Dopo l'intestazione vengono sezioni con
        etichetta, ciascuna un tipo di 4 byte e una dimensione di 8: 1
        record, 2 indice dei record, 3 chiavi, 4 indice delle chiavi. Chiavi
        e record sono sequenze di blocchi, ciascuno preceduto dalla sua
        dimensione in chiaro e registrata. Restituisce l'elenco delle chiavi
        e riempie la tabella dei blocchi, così il resto del lettore non sa
        quale motore ha scritto il file."""
        sections = {}
        pos = self._key_section_offset
        while pos + 12 <= self._size and len(sections) < 16:
            f.seek(pos)
            kind, size = struct.unpack(">IQ", self._read_exact(f, 12, "sezione"))
            if pos + 12 + size > self._size:
                raise MdxError("sezione fuori dal file / section past EOF")
            sections[kind] = pos + 12
            pos += 12 + size
        if 0x03000000 not in sections or 0x01000000 not in sections:
            raise MdxError("dizionario v3 incompleto / incomplete v3 dictionary")

        def blocks(offset):
            f.seek(offset)
            count, _total = struct.unpack(">IQ", self._read_exact(f, 12, "blocchi"))
            if not (0 < count <= MAX_BLOCKS):
                raise MdxError("numero di blocchi non plausibile / implausible block count")
            here = offset + 12
            for _ in range(count):
                f.seek(here)
                decomp, comp = struct.unpack(">II", self._read_exact(f, 8, "blocco"))
                if decomp > MAX_BLOCK or here + 8 + comp > self._size:
                    raise MdxError("blocco non plausibile / implausible block")
                yield here + 8, comp, decomp, count
                here += 8 + comp

        keys = []
        seen = 0
        for off, comp, decomp, count in blocks(sections[0x03000000]):
            f.seek(off)
            block = _decode_block(self._read_exact(f, comp, "blocco chiavi"),
                                  decomp, self.version, self._key)
            keys.extend(self._split_key_block(block))
            if len(keys) > MAX_ENTRIES:
                raise MdxError("troppi lemmi / too many headwords")
            seen += 1
            if progress and (seen % 16 == 0 or seen == count):
                progress(0.9 * seen / count)
        if not keys:
            raise MdxError("dizionario vuoto / empty dictionary")

        rows, start = [], 0
        for i, (off, comp, decomp, _count) in enumerate(
                blocks(sections[0x01000000])):
            rows.append((i, off, comp, decomp, start))
            start += decomp
        db.executemany("INSERT INTO blocks VALUES (?, ?, ?, ?, ?)", rows)
        return keys

    def _decode_key_info(self, info, n_blocks):
        """EN: sizes of every key block. Also the first and last headword of
        each, which we skip: the sqlite index makes them useless.
        IT: dimensioni di ogni blocco di chiavi. Ci sono anche il primo e
        l'ultimo lemma di ciascuno, che saltiamo: l'indice sqlite li rende
        inutili."""
        w, fmt = self._num_width, self._num_fmt
        if self.version >= 2.0:
            tfmt, tw, term = ">H", 2, 1
        else:
            tfmt, tw, term = ">B", 1, 0
        wide = 2 if self.encoding == "utf-16-le" else 1
        out = []
        i = 0
        n = len(info)
        for _ in range(n_blocks):
            if i + w > n:
                raise MdxError("info chiavi troncate / truncated key info")
            i += w                                   # numero di lemmi
            for _ in range(2):                       # testa e coda
                if i + tw > n:
                    raise MdxError("info chiavi troncate / truncated key info")
                size = struct.unpack(tfmt, info[i:i + tw])[0]
                i += tw + (size + term) * wide
            if i + 2 * w > n:
                raise MdxError("info chiavi troncate / truncated key info")
            comp = struct.unpack(fmt, info[i:i + w])[0]
            decomp = struct.unpack(fmt, info[i + w:i + 2 * w])[0]
            i += 2 * w
            if comp > self._size or decomp > MAX_BLOCK:
                raise MdxError("blocco chiavi non plausibile / implausible key block")
            out.append((comp, decomp))
        return out

    def _split_key_block(self, block):
        """EN: inside a key block: offset, headword, NUL, and again.
        IT: dentro un blocco di chiavi: offset, lemma, NUL, e daccapo."""
        w, fmt = self._num_width, self._num_fmt
        term = b"\x00\x00" if self.encoding == "utf-16-le" else b"\x00"
        step = 2 if self.encoding == "utf-16-le" else 1
        out = []
        i = 0
        n = len(block)
        while i + w <= n:
            offset = struct.unpack(fmt, block[i:i + w])[0]
            i += w
            end = i
            while True:
                end = block.find(term, end)
                if end < 0:
                    raise MdxError("lemma senza terminatore / unterminated headword")
                if (end - i) % step == 0:
                    break
                end += 1
            word = block[i:end].decode(self.encoding, errors="replace")
            i = end + len(term)
            out.append((word.strip(), offset))
        return out

    def _read_record_table(self, f, db):
        """EN: where every block of definitions sits in the file.
        IT: dove sta nel file ogni blocco di definizioni."""
        w, fmt = self._num_width, self._num_fmt
        head = self._read_exact(f, w * 4, "tabella record")
        if self.version >= 2.0:
            n_blocks, n_entries, info_size, blocks_size = struct.unpack(">4Q", head)
        else:
            n_blocks, n_entries, info_size, blocks_size = struct.unpack(">4I", head)
        if not (0 < n_blocks <= MAX_BLOCKS) or info_size != n_blocks * 2 * w:
            raise MdxError("tabella dei record non plausibile / implausible record table")

        info = self._read_exact(f, info_size, "info record")
        offset = f.tell()
        start = 0
        rows = []
        for i in range(n_blocks):
            comp, decomp = struct.unpack(
                fmt + fmt[-1], info[i * 2 * w:(i + 1) * 2 * w])
            if comp > self._size or decomp > MAX_BLOCK:
                raise MdxError("blocco record non plausibile / implausible record block")
            if offset + comp > self._size:
                raise MdxError("blocco record fuori dal file / record block past EOF")
            rows.append((i, offset, comp, decomp, start))
            offset += comp
            start += decomp
        db.executemany("INSERT INTO blocks VALUES (?, ?, ?, ?, ?)", rows)

    def _store_keys(self, db, keys):
        """EN: a headword ends where the next one starts; the last one ends
        with the file. -1 is a placeholder patched in build_index().
        IT: un lemma finisce dove comincia il successivo; l'ultimo finisce
        col file. -1 è un segnaposto corretto in build_index()."""
        def rows():
            n = len(keys)
            for i, (word, start) in enumerate(keys):
                end = keys[i + 1][1] if i + 1 < n else -1
                yield (i, self._norm(word), word, start, end)
        db.executemany("INSERT INTO entries VALUES (?, ?, ?, ?, ?)", rows())

    def _norm(self, word):
        """EN: how a headword is compared. Case folded, and if the
        dictionary says so, stripped of spaces and punctuation, so that
        "self-respect", "Self Respect" and "selfrespect" all find it.
        IT: come si confronta un lemma. Ridotto a minuscole e, se il
        dizionario lo dichiara, privato di spazi e punteggiatura, così che
        "self-respect", "Self Respect" e "selfrespect" lo trovino."""
        s = word.strip().casefold()
        if self.strip_key:
            s = "".join(c for c in s if c.isalnum())
        return s

    # -- EN/IT: lookup -----------------------------------------------------

    def _block(self, i, off, comp, decomp):
        """EN/IT: one decoded record block, from the small cache or the file.
        / un blocco di record decodificato, dalla piccola cache o dal file."""
        block = self._blocks.get(i)
        if block is None:
            if self._fh is None:
                self._fh = open(self.path, "rb")
            self._fh.seek(off)
            try:
                block = _decode_block(self._fh.read(comp), decomp,
                                      self.version, self._key)
            except (OSError, ValueError, struct.error) as exc:
                raise MdxError(f"blocco illeggibile / unreadable block "
                               f"({exc})") from exc
            self._blocks[i] = block
            while len(self._blocks) > CACHE_BLOCKS:
                self._blocks.popitem(last=False)
        self._blocks.move_to_end(i)
        return block

    def _record_bytes(self, a, b, limit=MAX_BLOCK):
        """EN: the raw bytes of one record. A large resource (a picture, a
        sound) may run over more than one block, so blocks are joined until
        the end of the record, never past *limit*.
        IT: i byte grezzi di un record. Una risorsa grande (un'immagine, un
        suono) può stare su più blocchi, quindi i blocchi si uniscono fino alla
        fine del record, mai oltre *limit*."""
        out = bytearray()
        pos = a
        with self._lock:
            while b < 0 or pos < b:
                row = self._db.execute(
                    "SELECT i, off, comp, decomp, start FROM blocks "
                    "WHERE start <= ? ORDER BY start DESC LIMIT 1",
                    (pos,)).fetchone()
                if row is None:
                    break
                i, off, comp, decomp, start = row
                block = self._block(i, off, comp, decomp)
                lo = pos - start
                if lo >= len(block):
                    break
                hi = len(block) if b < 0 else min(len(block), b - start)
                out += block[lo:hi]
                if len(out) > limit:
                    raise MdxError("risorsa troppo grande / resource too large")
                if b < 0 or hi < len(block):
                    break
                pos = start + len(block)
        return bytes(out)

    def _record(self, a, b):
        text = self._record_bytes(a, b, MAX_BLOCK).decode(
            self.encoding, errors="replace")
        return text.rstrip("\x00").strip()

    # -- EN/IT: companion files -----------------------------------------------
    def companions(self):
        """EN — the files that belong with this dictionary: the resource
        archives (name.mdd, name.1.mdd, name.2.mdd ...) and the icon.
        IT — i file che appartengono a questo dizionario: gli archivi delle
        risorse (nome.mdd, nome.1.mdd, nome.2.mdd ...) e l'icona."""
        stem = os.path.splitext(self.path)[0]
        mdd = [c for c in (stem + ".mdd", stem + ".MDD") if os.path.isfile(c)][:1]
        for n in range(1, 100):           # nome.1.mdd, nome.2.mdd, ...
            cand = f"{stem}.{n}.mdd"
            if not os.path.isfile(cand):
                break
            mdd.append(cand)
        return mdd

    @property
    def icon_path(self):
        """EN/IT: name.png (or .jpg) beside the .mdx, or None."""
        stem = os.path.splitext(self.path)[0]
        for ext in (".png", ".PNG", ".jpg", ".jpeg", ".JPG"):
            if os.path.isfile(stem + ext):
                return stem + ext
        return None

    def resources(self):
        """EN/IT: the .mdd archives, opened once / gli archivi .mdd, aperti
        una volta sola. Broken ones are skipped / quelli rotti si saltano."""
        if self.RESOURCE:
            return []
        if self._res is None:
            self._res = []
            for p in self.companions():
                try:
                    self._res.append(MddResources(p, self._cache_folder))
                except MdxError:
                    continue
        return self._res

    def build_resources(self, progress=None):
        """EN/IT: index the .mdd archives; a broken one does not spoil the
        dictionary / indicizza gli archivi .mdd; uno rotto non guasta il
        dizionario."""
        for r in self.resources():
            if r.indexed:
                continue
            try:
                r.build_index(progress)
            except MdxError:
                continue

    def resource(self, name, limit=8 * 1024 * 1024):
        """EN — the bytes of a file referenced by an entry (an image, say),
        from the dictionary's .mdd archives, or None. Only names inside the
        archives are reachable: never a file on disk, never the network.
        IT — i byte di un file citato da una voce (un'immagine, per esempio),
        dagli archivi .mdd del dizionario, o None. Si raggiungono solo nomi
        dentro gli archivi: mai un file su disco, mai la rete."""
        name = (name or "").strip()
        if not name:
            return None
        low = name.lower()
        if low.startswith("data:"):
            return _data_uri(name, limit)
        if "://" in name and not low.startswith(("file://", "entry://")):
            return None                   # http, https, sound...: no
        name = re.sub(r"^(file|entry)://", "", name, flags=re.I)
        name = name.split("#", 1)[0].split("?", 1)[0]
        for r in self.resources():
            if not r.indexed:
                continue
            data = r.get(name, limit)
            if data:
                return data
        return None

    def lookup(self, word, _depth=0):
        """EN: the first definition of *word*, or None. Redirects inside the
        dictionary (@@@LINK=) are followed.
        IT: la prima definizione di *word*, o None. I rimandi interni al
        dizionario (@@@LINK=) vengono seguiti."""
        found = self.lookup_all(word, _depth)
        return found[0] if found else None

    def lookup_all(self, word, _depth=0):
        """EN: every definition filed under *word* (a headword can appear
        more than once).
        IT: tutte le definizioni registrate sotto *word* (un lemma può
        comparire più di una volta)."""
        if not self.indexed:
            self.build_index()
        norm = self._norm(word)
        if not norm:
            return []
        with self._lock:
            rows = self._db.execute(
                "SELECT a, b FROM entries WHERE norm = ? ORDER BY id",
                (norm,)).fetchall()
        out = []
        for a, b in rows:
            text = self._record(a, b)
            link = _LINK_RE.match(text)
            if link:
                if _depth >= 5:
                    continue
                target = link.group(1).strip()
                if self._norm(target) != norm:
                    out.extend(self.lookup_all(target, _depth + 1))
                continue
            if text:
                out.append(self._apply_styles(text))
        return out

    def _apply_styles(self, text):
        """EN/IT: expand the `n` marks of a compact dictionary / espande i
        segni `n` di un dizionario compatto."""
        if not self._styles or "`" not in text:
            return text
        parts = re.split(r"`(\d+)`", text)
        out = [parts[0]]
        for num, chunk in zip(parts[1::2], parts[2::2]):
            begin, end = self._styles.get(num, ("", ""))
            out.append(begin + chunk + end)
        return "".join(out)

    def prefix(self, start, limit=20):
        """EN: headwords beginning with *start*, for a suggestion list.
        IT: lemmi che cominciano per *start*, per un elenco di
        suggerimenti."""
        if not self.indexed:
            self.build_index()
        norm = self._norm(start)
        if not norm:
            return []
        with self._lock:
            rows = self._db.execute(
                "SELECT word FROM entries WHERE norm >= ? AND norm < ? "
                "ORDER BY norm LIMIT ?",
                (norm, norm + "\uffff", int(limit))).fetchall()
        seen, out = set(), []
        for (word,) in rows:
            if word not in seen:
                seen.add(word)
                out.append(word)
        return out

    def near(self, word, limit=4, min_ratio=NEAR_RATIO, pool=400):
        """EN — headwords close to *word*, best first, as (headword, score).

        A dictionary files the singular and the infinitive; a writer selects
        whatever is on the page. "case" has to reach *casa*, "houses" to
        reach *house*, "cadendo" to reach *cadere*. Rather than guess at the
        grammar of a language the dictionary never declares, this looks for
        headwords that begin like the word and scores them on how much of
        them matches: an ending that changes costs little, a beginning that
        changes costs everything.

        The candidates come from the index, by asking for shorter and
        shorter openings of the word until there are enough of them, so a
        near miss costs one or two more queries and not a walk through a
        million entries.

        IT — lemmi vicini a *word*, il migliore per primo, come (lemma,
        punteggio).

        Un dizionario registra il singolare e l'infinito; chi scrive
        seleziona quello che ha sulla pagina. "case" deve arrivare a *casa*,
        "houses" a *house*, "cadendo" a *cadere*. Invece di indovinare la
        grammatica di una lingua che il dizionario non dichiara, si cercano
        lemmi che cominciano come la parola e si valuta quanto di loro
        combacia: una desinenza che cambia costa poco, un inizio che cambia
        costa tutto.

        I candidati vengono dall'indice, chiedendo inizi di parola sempre
        più corti finché non bastano, così un quasi-errore costa una o due
        interrogazioni in più e non una passeggiata su un milione di voci.
        """
        if not self.indexed:
            self.build_index()
        norm = self._norm(word)
        if len(norm) < 3:
            # EN/IT: too short to guess from: "il" would reach anything.
            return []
        target = _fold(norm)

        found = {}
        floor = max(3, (len(norm) * 3) // 5)
        with self._lock:
            for cut in range(len(norm), floor - 1, -1):
                start = norm[:cut]
                rows = self._db.execute(
                    "SELECT norm, word FROM entries WHERE norm >= ? "
                    "AND norm < ? ORDER BY norm LIMIT ?",
                    (start, start + "\uffff", 80)).fetchall()
                for nrm, w in rows:
                    found.setdefault(nrm, w)
                if len(found) >= pool:
                    break

        scored = []
        for nrm, w in found.items():
            if nrm == norm:
                continue                    # gia' provato per via esatta
            score = _similarity(target, _fold(nrm))
            if score >= min_ratio:
                scored.append((score, len(nrm), nrm, w))
        # EN/IT: best score first; between equals, the shorter headword, which
        # is the one a dictionary is more likely to have filed as the lemma.
        scored.sort(key=lambda r: (-r[0], r[1], r[2]))
        out, seen = [], set()
        for score, _len, _nrm, w in scored:
            if w.casefold() in seen:
                continue
            seen.add(w.casefold())
            out.append((w, score))
            if len(out) >= limit:
                break
        return out

    def headword(self, word):
        """EN: how the dictionary itself spells this headword, or None. What
        a rule builds is a probe; what is shown to the reader must be the
        dictionary's own word, capital letters, accents and all.
        IT: come il dizionario stesso scrive questo lemma, o None. Quello che
        una regola costruisce e' una sonda; quello che si mostra a chi legge
        deve essere la parola del dizionario, maiuscole, accenti e tutto."""
        if not self.indexed:
            self.build_index()
        norm = self._norm(word)
        if not norm:
            return None
        with self._lock:
            row = self._db.execute(
                "SELECT word FROM entries WHERE norm = ? ORDER BY id LIMIT 1",
                (norm,)).fetchone()
        return row[0] if row else None

    def __contains__(self, word):
        return bool(self.lookup_all(word))

    def close(self):
        for r in self._res or ():
            r.close()
        self._res = None
        with self._lock:
            self._blocks.clear()
            if self._fh is not None:
                try:
                    self._fh.close()
                except OSError:
                    pass
                self._fh = None
            if self._db is not None:
                try:
                    self._db.close()
                except sqlite3.Error:
                    pass
                self._db = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
        return False

    def __repr__(self):
        return f"<MdxDictionary {self.title!r} {os.path.basename(self.path)}>"


class MddResources(MdxDictionary):
    """EN — an .mdd archive: the pictures, sounds and style sheets of a
    dictionary, filed under names like \\img\\cat.png. Same container as an
    .mdx, so the same reader; only the names and the contents differ.
    IT — un archivio .mdd: immagini, suoni e fogli di stile di un dizionario,
    registrati sotto nomi come \\img\\gatto.png. Stesso contenitore di un
    .mdx, quindi stesso lettore; cambiano solo i nomi e i contenuti."""

    RESOURCE = True

    def _norm(self, word):
        s = word.strip().replace("/", "\\").casefold()
        while s.startswith(".\\"):
            s = s[2:]
        return s if s.startswith("\\") else "\\" + s

    def get(self, name, limit=8 * 1024 * 1024):
        """EN/IT: the bytes filed under *name*, or None."""
        if not self.indexed:
            # EN/IT: indexing is the worker thread's job, never the reader's
            # / indicizzare e' compito del thread di lavoro, mai di chi legge
            return None
        norm = self._norm(name)
        with self._lock:
            row = self._db.execute(
                "SELECT a, b FROM entries WHERE norm = ? ORDER BY id LIMIT 1",
                (norm,)).fetchone()
        if row is None:
            return None
        try:
            return self._record_bytes(row[0], row[1], limit)
        except MdxError:
            return None


def _data_uri(uri, limit):
    """EN/IT: the bytes of a data: URI, base64 or plain, within *limit*."""
    import base64
    head, _, body = uri.partition(",")
    if len(body) > limit * 2:
        return None
    try:
        if head.lower().endswith(";base64"):
            data = base64.b64decode(body, validate=False)
        else:
            from urllib.parse import unquote_to_bytes
            data = unquote_to_bytes(body)
    except ValueError:
        return None
    return data if len(data) <= limit else None


# ---------------------------------------------------------------------------
# EN/IT: from the HTML of an entry to something readable on screen
# ---------------------------------------------------------------------------
# EN: dictionary entries are HTML with a stylesheet. RuscaWriter has no web
#     view, and adding one for this would be a heavy dependency for a small
#     job. Pango markup is what a GTK label already understands, and it is
#     enough for what a definition needs: bold, italic, small caps of a sort,
#     superscripts, line breaks, bullets. Everything else is dropped rather
#     than approximated.
# IT: le voci dei dizionari sono HTML con un foglio di stile. RuscaWriter non
#     ha un motore web, e aggiungerne uno per questo sarebbe una dipendenza
#     pesante per un lavoro piccolo. Il markup di Pango è quello che
#     un'etichetta GTK già capisce, e basta a quello che serve a una
#     definizione: grassetto, corsivo, apici, a capo, elenchi puntati. Il
#     resto si scarta invece di approssimarlo.

# EN/IT: HTML tag -> Pango tag. Pango knows only a handful of them.
_INLINE_TAGS = {
    "b": "b", "strong": "b", "em": "i", "i": "i", "cite": "i", "var": "i",
    "u": "u", "ins": "u", "s": "s", "del": "s", "strike": "s",
    "sub": "sub", "sup": "sup", "tt": "tt", "code": "tt", "kbd": "tt",
    "small": "small", "big": "big",
}
# EN/IT: tags that start a new line, and those whose content is thrown away.
_BLOCK_TAGS = {
    "p", "div", "br", "tr", "li", "dt", "dd", "table", "ul", "ol", "dl",
    "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "section",
    "article", "hr", "td", "th",
}
_DROP_TAGS = {"script", "style", "head", "title", "meta", "link", "object"}
_VOID_TAGS = {"br", "hr", "img", "meta", "link", "input", "col"}


def _esc(text):
    """EN: escape for Pango markup. IT: protegge per il markup di Pango."""
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


class _EntryParser(html.parser.HTMLParser):
    """EN: turns the HTML of an entry into balanced Pango markup. It closes
    its own tags, so a sloppy dictionary cannot produce markup that GTK then
    refuses to render.
    IT: trasforma l'HTML di una voce in markup Pango bilanciato. Chiude i
    propri tag, così un dizionario scritto male non può produrre markup che
    GTK poi si rifiuta di disegnare."""

    def __init__(self, plain=False):
        super().__init__(convert_charrefs=True)
        self.plain = plain
        self.out = []
        self.stack = []
        self.drop = 0
        self.images = []        # EN/IT: src of every <img>, in order

    # -- EN/IT: helpers
    def _open(self, tag):
        if not self.plain:
            self.out.append(f"<{tag}>")
        self.stack.append(tag)

    def _close(self, tag):
        if tag not in self.stack:
            return
        # EN/IT: close everything opened after it, then reopen those.
        reopen = []
        while self.stack:
            top = self.stack.pop()
            if not self.plain:
                self.out.append(f"</{top}>")
            if top == tag:
                break
            reopen.append(top)
        for t in reversed(reopen):
            self._open(t)

    def _newline(self):
        if self.out and not self.out[-1].endswith("\n"):
            self.out.append("\n")

    # -- EN/IT: HTMLParser interface
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "img" and not self.drop:
            src = dict(attrs).get("src") or ""
            if src and src not in self.images and len(self.images) < 12:
                self.images.append(src)
            return
        if tag in _VOID_TAGS and tag in _DROP_TAGS:
            # EN/IT: <link> and <meta> never close. Counting them as an open
            # region threw away the whole entry that followed: almost every
            # MDict entry starts with <link rel="stylesheet" ...>.
            # / <link> e <meta> non si chiudono mai. Contarli come una zona
            # aperta buttava via tutta la voce che seguiva: quasi ogni voce
            # MDict comincia con <link rel="stylesheet" ...>.
            return
        if tag in _DROP_TAGS:
            self.drop += 1
            return
        if self.drop:
            return
        if tag == "li":
            self._newline()
            self.out.append("• ")
            return
        if tag in ("br", "hr"):
            self.out.append("\n")
            return
        if tag in _BLOCK_TAGS:
            self._newline()
            if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                self._open("b")
            return
        if tag in _INLINE_TAGS:
            self._open(_INLINE_TAGS[tag])

    def handle_startendtag(self, tag, attrs):
        if tag.lower() in ("br", "hr") and not self.drop:
            self.out.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _VOID_TAGS and tag in _DROP_TAGS:
            return
        if tag in _DROP_TAGS:
            self.drop = max(0, self.drop - 1)
            return
        if self.drop:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._close("b")
            self._newline()
            return
        if tag in _INLINE_TAGS:
            self._close(_INLINE_TAGS[tag])
            return
        if tag in _BLOCK_TAGS and tag not in _VOID_TAGS:
            self._newline()

    def handle_data(self, data):
        if self.drop:
            return
        # EN/IT: HTML collapses runs of spaces; so do we, newlines included.
        text = re.sub(r"[ \t\r\n\f\v]+", " ", data)
        if not text:
            return
        if text == " " and (not self.out or self.out[-1].endswith((" ", "\n"))):
            return
        self.out.append(text if self.plain else _esc(text))

    def result(self):
        while self.stack:
            top = self.stack.pop()
            if not self.plain:
                self.out.append(f"</{top}>")
        text = "".join(self.out)
        text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def entry_images(entry):
    """EN/IT: the src of the pictures in an entry, in order (at most 12).
    / le src delle immagini di una voce, in ordine (al massimo 12)."""
    parser = _EntryParser(plain=True)
    try:
        parser.feed(entry or "")
        parser.close()
    except Exception:
        return []
    return list(parser.images)


def to_pango_markup(entry):
    """EN: Pango markup for a dictionary entry, ready for a GTK label.
    IT: markup Pango di una voce, pronto per un'etichetta GTK."""
    parser = _EntryParser(plain=False)
    try:
        parser.feed(entry or "")
        parser.close()
    except Exception:
        # EN/IT: never let a broken entry break the lookup: fall back to text.
        return _esc(to_plain_text(entry))
    out = parser.result()
    if not out and entry and entry.strip():
        # EN/IT: a definition is never shown empty if it had any text.
        # / una definizione non si mostra mai vuota se aveva del testo.
        out = _esc(_strip_tags(entry))
    return out


def to_plain_text(entry):
    """EN: the same entry without any formatting, for tests and exports.
    IT: la stessa voce senza formattazione, per i test e gli export."""
    parser = _EntryParser(plain=True)
    try:
        parser.feed(entry or "")
        parser.close()
    except Exception:
        return _strip_tags(entry)
    out = parser.result()
    if not out and entry and entry.strip():
        out = _strip_tags(entry)
    return out


def _strip_tags(entry):
    """EN/IT: last resort: tags out, entities decoded, spaces tidied.
    / ultima risorsa: via i tag, entita' decodificate, spazi in ordine."""
    text = re.sub(r"(?is)<(script|style)\b.*?</\1\s*>", " ", entry or "")
    text = re.sub(r"<[^>]*>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def shorten(markup, max_lines=4, max_chars=320):
    """EN: the opening of an entry, cut at a line or character count without
    leaving a Pango tag open. Returns (text, was_cut).
    IT: l'inizio di una voce, tagliato a un numero di righe o di caratteri
    senza lasciare aperto un tag di Pango. Restituisce (testo, tagliato)."""
    lines = markup.split("\n")
    cut = False
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        cut = True
    text = "\n".join(lines)
    if len(text) > max_chars:
        # EN/IT: cut on a space, never inside a tag, an entity or a word.
        head = text[:max_chars]
        space = head.rfind(" ")
        gt, lt = head.rfind(">"), head.rfind("<")
        if lt > gt:
            head = head[:lt]
        elif space > max_chars * 0.6:
            head = head[:space]
        amp, semi = head.rfind("&"), head.rfind(";")
        if amp > semi:
            head = head[:amp]
        text = head
        cut = True
    if cut:
        # EN/IT: ';' is not stripped: it may be closing an entity.
        text = text.rstrip(" .,:") + "…"
        # EN/IT: rebalance: close what the cut left open.
        opened = []
        for kind, tag in re.findall(r"<(/?)(\w+)[^>]*>", text):
            if kind:
                if opened and opened[-1] == tag:
                    opened.pop()
            else:
                opened.append(tag)
        for tag in reversed(opened):
            text += f"</{tag}>"
    return text, cut


# ---------------------------------------------------------------------------
# EN/IT: gender and number
# ---------------------------------------------------------------------------
# EN: a dictionary files the masculine singular; a page says whatever it says.
#     Between "case" and "casa" there is no similarity to weigh: there is a
#     rule, and it gives one answer. So before falling back on how alike two
#     words look, the endings are undone by rule and the results are looked up
#     in the ordinary way. A rule that produces a word the dictionary does not
#     have costs one lookup and disappears — which is why rules for the wrong
#     language do no harm, and the language of a dictionary, which the format
#     never states reliably, does not have to be known.
# IT: un dizionario registra il maschile singolare; una pagina dice quello che
#     dice. Fra "case" e "casa" non c'è una somiglianza da pesare: c'è una
#     regola, e dà una risposta sola. Perciò, prima di ripiegare su quanto due
#     parole si assomigliano, le desinenze si disfano per regola e i risultati
#     si cercano nel modo consueto. Una regola che produce una parola che il
#     dizionario non ha costa una ricerca e sparisce: per questo le regole
#     della lingua sbagliata non fanno danno, e la lingua del dizionario, che
#     il formato non dichiara mai in modo affidabile, non serve saperla.
#
# EN/IT: each list is (ending, replacement), most specific first. The first
# form the dictionary actually has wins, so the order inside a language is
# what decides between "casa" and "caso" for "case".
INFLECTIONS = {
    "it": [
        # plurale -> singolare
        ("trici", "trice"), ("trici", "tore"), ("trice", "tore"),
        ("esse", "essa"), ("esse", "e"), ("essa", "e"), ("chi", "co"), ("ghi", "go"), ("che", "ca"),
        ("ghe", "ga"), ("ci", "co"), ("gi", "go"),
        ("i", "o"), ("i", "e"), ("i", "a"), ("i", "io"),
        ("e", "a"), ("e", "o"),
        # femminile -> maschile
        ("a", "o"), ("a", "e"),
    ],
    "en": [
        ("ies", "y"), ("ves", "f"), ("ves", "fe"), ("ches", "ch"),
        ("shes", "sh"), ("sses", "ss"), ("xes", "x"), ("zes", "z"),
        ("oes", "o"), ("es", "e"), ("es", ""), ("s", ""),
        ("men", "man"), ("'s", ""), ("\u2019s", ""),
    ],
    "es": [
        ("ces", "z"), ("ores", "or"), ("ora", "or"), ("esa", "\u00e9s"),
        ("es", ""), ("s", ""), ("as", "o"), ("as", "a"), ("os", "o"),
        ("a", "o"),
    ],
    "fr": [
        ("eaux", "eau"), ("aux", "al"), ("euses", "eur"), ("euse", "eur"),
        ("trices", "teur"), ("trice", "teur"), ("\u00e8res", "er"),
        ("\u00e8re", "er"), ("elles", "el"), ("elle", "el"),
        ("ives", "if"), ("ive", "if"), ("s", ""), ("x", ""), ("e", ""),
    ],
    "pt": [
        ("\u00f5es", "\u00e3o"), ("\u00e3es", "\u00e3o"), ("\u00e3os", "\u00e3o"),
        ("ais", "al"), ("eis", "el"), ("\u00f3is", "ol"), ("uis", "ul"),
        ("is", "il"), ("ens", "em"), ("ores", "or"), ("ora", "or"),
        ("es", ""), ("s", ""), ("a", "o"),
    ],
    "de": [
        ("innen", ""), ("in", ""), ("nen", ""), ("en", ""), ("ern", ""),
        ("er", ""), ("es", ""), ("e", ""), ("n", ""), ("s", ""),
    ],
    "ru": [
        ("\u044f\u043c\u0438", "\u044f"), ("\u0430\u043c\u0438", "\u0430"),
        ("\u044f\u0445", "\u044f"), ("\u0430\u0445", "\u0430"),
        ("\u043e\u0432", ""), ("\u0435\u0432", "\u044c"),
        ("\u0435\u0439", "\u044c"), ("\u044f\u043c", "\u044f"),
        ("\u0430\u043c", "\u0430"), ("\u044b", "\u0430"), ("\u044b", ""),
        ("\u0438", "\u0430"), ("\u0438", "\u044c"), ("\u0438", ""),
        ("\u044f", ""), ("\u0430", ""), ("\u0443", ""), ("\u044e", ""),
        ("\u0435", ""), ("\u043e\u043c", ""), ("\u0435\u043c", "\u044c"),
        ("\u043e\u0439", "\u0430"),
    ],
}

# EN/IT: plurals that follow no rule at all. Short lists on purpose: only the
# ones a reader meets constantly. / plurali che non seguono nessuna regola.
# Elenchi corti di proposito: solo quelli che un lettore incontra di continuo.
IRREGULARS = {
    "en": {
        "children": "child", "men": "man", "women": "woman", "feet": "foot",
        "teeth": "tooth", "geese": "goose", "mice": "mouse", "lice": "louse",
        "people": "person", "oxen": "ox",
    },
    "it": {
        "uomini": "uomo", "uova": "uovo", "dei": "dio", "buoi": "bue",
        "mani": "mano", "armi": "arma", "dita": "dito", "ali": "ala",
    },
    "de": {
        "kinder": "kind", "m\u00e4nner": "mann", "frauen": "frau",
        "b\u00fccher": "buch", "h\u00e4user": "haus", "st\u00e4dte": "stadt",
    },
    "fr": {
        "yeux": "\u0153il", "chevaux": "cheval", "messieurs": "monsieur",
        "mesdames": "madame",
    },
    "es": {"l\u00e1pices": "l\u00e1piz"},
    "pt": {"p\u00e3es": "p\u00e3o"},
    "ru": {"\u0434\u0435\u0442\u0438": "\u0440\u0435\u0431\u0451\u043d\u043e\u043a",
           "\u043b\u044e\u0434\u0438": "\u0447\u0435\u043b\u043e\u0432\u0435\u043a"},
}

# EN/IT: German marks many plurals with an umlaut and nothing else.
_UMLAUT = str.maketrans("\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc", "aouAOU")

_CYRILLIC = re.compile(r"[\u0400-\u04FF]")


def _rule_languages(word, prefer=()):
    """EN: which rule sets can apply to this word. The alphabet decides what
    is possible, the writer's own language decides what is tried first.
    IT: quali gruppi di regole possono valere per questa parola. L'alfabeto
    decide cosa e' possibile, la lingua di chi scrive decide cosa si prova
    per primo."""
    cyrillic = bool(_CYRILLIC.search(word))
    usable = [code for code in INFLECTIONS if (code == "ru") == cyrillic]
    ordered = [c for c in prefer if c in usable]
    ordered += [c for c in usable if c not in ordered]
    return ordered


def inflections(word, prefer=(), limit=28):
    """EN - the dictionary forms an inflected word could come from, best
    first. Nothing here knows whether a form is real: these are guesses to be
    checked against a dictionary, and the ones that are not in it cost a
    lookup each and vanish.

    IT - le forme da dizionario da cui una parola flessa puo' venire, la
    migliore per prima. Niente qui sa se una forma esista: sono ipotesi da
    verificare su un dizionario, e quelle che non ci sono costano una
    ricerca ciascuna e spariscono."""
    word = (word or "").strip()
    if len(word) < 3:
        return []
    low = word.casefold()
    out = []

    def add(form):
        form = (form or "").strip()
        if len(form) >= 2 and form.casefold() != low and form not in out:
            out.append(form)

    langs = _rule_languages(word, prefer)
    # EN/IT: the irregulars first: where they apply, there is nothing to guess.
    for code in langs:
        add(IRREGULARS.get(code, {}).get(low, ""))
    for code in langs:
        for ending, replacement in INFLECTIONS[code]:
            if low.endswith(ending) and len(low) - len(ending) >= 2:
                add(word[:len(word) - len(ending)] + replacement)
        if code == "de":
            # Buecher -> Buch: la dieresi e' l'unico segno del plurale
            plain = word.translate(_UMLAUT)
            if plain != word:
                add(plain)
                for ending, replacement in INFLECTIONS["de"]:
                    if plain.casefold().endswith(ending) \
                            and len(plain) - len(ending) >= 2:
                        add(plain[:len(plain) - len(ending)] + replacement)
        if len(out) >= limit:
            break
    return out[:limit]


# ---------------------------------------------------------------------------
# EN/IT: several dictionaries, consulted in order
# ---------------------------------------------------------------------------

class DictionarySet:
    """EN — the dictionaries the user has installed, searched in order.

    Opening is separated from indexing on purpose: open() is instant and
    tells you what still needs building, so the interface can index in a
    worker thread with a progress bar instead of freezing while you write.

    IT — i dizionari che l'utente ha installato, consultati in ordine.

    Aprire è separato da indicizzare di proposito: open() è immediato e dice
    cosa resta da costruire, così l'interfaccia può indicizzare in un thread
    con una barra di avanzamento invece di bloccarsi mentre scrivi.
    """

    def __init__(self, paths=(), cache_folder=None):
        self.cache_folder = cache_folder
        self._items = []            # lista di (percorso, dizionario o None)
        self.errors = {}            # percorso -> messaggio dell'errore
        for p in paths:
            self.add(p)

    # -- EN/IT: composition
    def add(self, path):
        """EN: open a dictionary and put it last. Raises MdxError if the file
        is not usable, and does not add it.
        IT: apre un dizionario e lo mette in fondo. Solleva MdxError se il
        file non è utilizzabile, e non lo aggiunge."""
        path = os.path.abspath(path)
        self.remove(path)
        d = MdxDictionary(path, cache_folder=self.cache_folder)
        self._items.append([path, d])
        self.errors.pop(path, None)
        return d

    def add_quiet(self, path):
        """EN: same, but a broken dictionary is remembered as an error
        instead of stopping the program at startup.
        IT: uguale, ma un dizionario rotto viene ricordato come errore invece
        di fermare il programma all'avvio."""
        try:
            return self.add(path)
        except MdxError as exc:
            path = os.path.abspath(path)
            self.errors[path] = str(exc)
            self._items.append([path, None])
            return None

    def remove(self, path):
        path = os.path.abspath(path)
        for item in list(self._items):
            if item[0] == path:
                if item[1] is not None:
                    item[1].close()
                self._items.remove(item)
        self.errors.pop(path, None)

    def move(self, path, delta):
        """EN: change the search order. IT: cambia l'ordine di consultazione."""
        path = os.path.abspath(path)
        for i, item in enumerate(self._items):
            if item[0] == path:
                j = max(0, min(len(self._items) - 1, i + delta))
                self._items.insert(j, self._items.pop(i))
                return j
        return -1

    @property
    def paths(self):
        return [p for p, _ in self._items]

    def dictionaries(self):
        """EN: (path, dictionary or None) in search order.
        IT: (percorso, dizionario o None) nell'ordine di consultazione."""
        return [(p, d) for p, d in self._items]

    def pending(self):
        """EN: the dictionaries whose index still has to be built. One that
        already failed is not retried at every lookup: it waits until it is
        added again. IT: i dizionari il cui indice è ancora da costruire.
        Uno che ha già fallito non si ritenta a ogni ricerca: aspetta di
        essere aggiunto di nuovo."""
        return [d for p, d in self._items
                if d is not None and not d.indexed and p not in self.errors]

    def needs_work(self):
        """EN/IT: anything still to index, words or resources / qualcosa
        ancora da indicizzare, parole o risorse."""
        for p, d in self._items:
            if d is None or p in self.errors:
                continue
            if not d.indexed or any(not r.indexed for r in d.resources()):
                return True
        return False

    def build_pending(self, progress=None):
        """EN: build the missing indexes. Meant for a worker thread; the
        callback gets (dictionary, fraction). A broken dictionary does not
        stop the others: its message goes in *errors* and the first one is
        returned, so the interface can say it.
        IT: costruisce gli indici mancanti. Pensata per un thread di lavoro;
        la callback riceve (dizionario, frazione). Un dizionario rotto non
        ferma gli altri: il suo messaggio va in *errors* e il primo viene
        restituito, così l'interfaccia può dirlo."""
        first = None
        for p, d in list(self._items):
            if d is None or p in self.errors:
                continue
            if d.indexed:
                d.build_resources()
                continue
            try:
                d.build_index(lambda f, d=d: progress(d, f) if progress else None)
            except MdxError as exc:
                self.errors[p] = str(exc)
                first = first or f"{d.title}: {exc}"
                continue
            # EN/IT: pictures after words: the words are what you wait for.
            d.build_resources()
        return first

    # -- EN/IT: lookup
    def lookup(self, word):
        """EN: every dictionary that has *word*, in order, as a list of
        (dictionary, list of entries). Dictionaries without the word, and
        those still unindexed, are skipped.
        IT: ogni dizionario che ha *word*, in ordine, come lista di
        (dizionario, elenco di voci). I dizionari senza la parola, e quelli
        non ancora indicizzati, vengono saltati."""
        out = []
        for _, d in self._items:
            if d is None or not d.indexed:
                continue
            try:
                found = d.lookup_all(word)
            except MdxError:
                continue
            if found:
                out.append((d, found))
        return out

    def first(self, word):
        """EN: the first entry found, as (dictionary, text), or None.
        IT: la prima voce trovata, come (dizionario, testo), o None."""
        for d, entries in self.lookup(word):
            return d, entries[0]
        return None

    def first_form(self, word, prefer=()):
        """EN: undo gender and number by rule and return the first form the
        dictionaries actually have, as (dictionary, headword, text). A rule
        that invents a word simply finds nothing.
        IT: disfa genere e numero per regola e restituisce la prima forma che
        i dizionari hanno davvero, come (dizionario, lemma, testo). Una
        regola che inventa una parola semplicemente non trova niente."""
        for form in inflections(word, prefer):
            found = self.first(form)
            if found is not None:
                source, text = found
                return source, source.headword(form) or form, text
        return None

    def near(self, word, limit=4, min_ratio=NEAR_RATIO):
        """EN: the closest headwords across every dictionary, best first, as
        (dictionary, headword, score). Ties go to the dictionary higher up
        the list, the same order an exact match follows.
        IT: i lemmi più vicini in tutti i dizionari, il migliore per primo,
        come (dizionario, lemma, punteggio). A pari punteggio vince il
        dizionario più in alto nell'elenco, lo stesso ordine che segue una
        corrispondenza esatta."""
        rows = []
        for rank, (_, d) in enumerate(self._items):
            if d is None or not d.indexed:
                continue
            try:
                for w, score in d.near(word, limit, min_ratio):
                    rows.append((-score, rank, w, d))
            except MdxError:
                continue
        rows.sort(key=lambda r: (r[0], r[1], len(r[2]), r[2]))
        out, seen = [], set()
        for neg, _rank, w, d in rows:
            key = w.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append((d, w, -neg))
            if len(out) >= limit:
                break
        return out

    def first_near(self, word, min_ratio=NEAR_RATIO):
        """EN: the entry of the closest headword, as (dictionary, headword,
        text, score), or None.
        IT: la voce del lemma più vicino, come (dizionario, lemma, testo,
        punteggio), o None."""
        for d, headword, score in self.near(word, 4, min_ratio):
            entries = d.lookup_all(headword)
            if entries:
                return d, headword, entries[0], score
        return None

    def prefix(self, start, limit=12):
        """EN: headword suggestions from every dictionary.
        IT: suggerimenti di lemmi da tutti i dizionari."""
        seen, out = set(), []
        for _, d in self._items:
            if d is None or not d.indexed:
                continue
            try:
                words = d.prefix(start, limit)
            except MdxError:
                continue
            for w in words:
                key = w.casefold()
                if key not in seen:
                    seen.add(key)
                    out.append(w)
                    if len(out) >= limit:
                        return out
        return out

    def close(self):
        for _, d in self._items:
            if d is not None:
                d.close()
        self._items = []

    def __len__(self):
        return len(self._items)
