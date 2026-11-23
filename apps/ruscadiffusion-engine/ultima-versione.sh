#!/bin/bash
# ---------------------------------------------------------------------------
# RuscaLinux — quale versione di stable-diffusion.cpp costruire.
#
#   ./ultima-versione.sh     stampa  "master-1106-532d2c1 2026-11-15T10:40:12Z"
#
# Stampa il tag dell'ultima release di stable-diffusion.cpp e, se la conosce,
# la data di pubblicazione (puo' mancare). La usano make-deb.sh, per sapere
# cosa scaricare, e build.sh, per accorgersi che e' uscita una release nuova.
#
# stable-diffusion.cpp non ha numeri di versione X.Y.Z: ogni release e' un
# tag "master-<numero>-<commit>", dove il numero cresce a ogni release. La
# release giusta e' quella che GitHub indica come "Latest" (non una
# pre-release, non una bozza), con un tag in quella forma.
#
# RUSCADIFFUSION_SD_VERSION fissa una versione: il tag intero
# (master-1106-532d2c1) viene stampato e basta; il solo numero (1106) viene
# cercato fra i tag su GitHub.
#
# Tre modi di sapere qual e' l'ultima, nell'ordine; si passa al successivo
# se uno fallisce:
#   1. API di GitHub (da' anche la data). Senza autenticazione ammette 60
#      richieste l'ora per indirizzo IP: con GITHUB_TOKEN il limite sale.
#   2. Il rinvio di github.com/<repo>/releases/latest, che punta al tag.
#   3. git ls-remote: il tag master-<numero>-<commit> con il numero piu' alto.
#
# Esce con 1 se non riesce a saperlo (niente rete), con 2 se la versione
# fissata non e' valida o non esiste.
# ---------------------------------------------------------------------------
set -euo pipefail

REPO="leejet/stable-diffusion.cpp"

valido() { [[ "$1" =~ ^master-[0-9]+-[0-9a-f]{7,40}$ ]]; }

# Tutti i tag di release, dal piu' recente.
tag_remoti() {
    command -v git >/dev/null || return 1
    timeout 60 git ls-remote --tags --refs "https://github.com/$REPO.git" 'master-*' \
        2>/dev/null | sed -n 's|.*refs/tags/||p' \
        | grep -E '^master-[0-9]+-[0-9a-f]{7,40}$' | sort -t- -k2,2nr
}

# ── Versione fissata ─────────────────────────────────────────────────────────
# Dalla master-1116 (commit 6cd0ef1, "Diffusion Graph Language", #2396)
# sd-cli non ha piu' --high-noise-cfg-scale, --high-noise-sampling-method e
# --image-preprocess, che rusca_diffusion.py usa: sono passate ai grafi .dgl.
# Finche' RuscaLLama non e' adattata, si costruisce l'ultima release con le
# vecchie opzioni. Per provare comunque l'ultima:
#   RUSCADIFFUSION_SD_VERSION=latest ./make-deb.sh
# Quando RuscaLLama sara' adattata, rimetti FISSATA="latest".
FISSATA="master-1111-6874e49"
RICHIESTA="${RUSCADIFFUSION_SD_VERSION:-$FISSATA}"
if [ "$RICHIESTA" != latest ]; then
    if valido "$RICHIESTA"; then
        echo "$RICHIESTA"
        exit 0
    fi
    if [[ "$RICHIESTA" =~ ^[0-9]+$ ]]; then
        if ! ELENCO=$(tag_remoti); then
            echo "Non riesco a leggere i tag di stable-diffusion.cpp (rete?)." >&2
            exit 1
        fi
        TAG=$(printf '%s\n' "$ELENCO" | grep -E "^master-$RICHIESTA-" | head -1 || true)
        if [ -n "$TAG" ]; then
            echo "$TAG"
            exit 0
        fi
        [ -n "$ELENCO" ] || exit 1
    fi
    echo "RUSCADIFFUSION_SD_VERSION non valida: \"$RICHIESTA\" (es. master-1106-532d2c1 o 1106)" >&2
    exit 2
fi

# ── 1. API di GitHub ─────────────────────────────────────────────────────────
api() {
    local url="https://api.github.com/repos/$REPO/releases/latest"
    local auth=()
    [ -n "${GITHUB_TOKEN:-}" ] && auth=(-H "Authorization: Bearer $GITHUB_TOKEN")
    if command -v curl >/dev/null; then
        curl -sfL --connect-timeout 15 --max-time 30 \
             -H "Accept: application/vnd.github+json" "${auth[@]}" "$url"
    elif command -v wget >/dev/null; then
        local h=()
        [ -n "${GITHUB_TOKEN:-}" ] && h=(--header="Authorization: Bearer $GITHUB_TOKEN")
        wget -q -T 30 -O - --header="Accept: application/vnd.github+json" "${h[@]}" "$url"
    else
        return 1
    fi
}

if JSON=$(api 2>/dev/null) && [ -n "$JSON" ]; then
    RIGA=$(printf '%s' "$JSON" | python3 -c '
import json, sys
d = json.load(sys.stdin)
if not d.get("draft") and not d.get("prerelease"):
    print(d.get("tag_name", ""), d.get("published_at") or "")
' 2>/dev/null || true)
    TAG="${RIGA%% *}"
    if [ -n "$TAG" ] && valido "$TAG"; then
        echo "$RIGA"
        exit 0
    fi
fi

# ── 2. Rinvio di releases/latest ─────────────────────────────────────────────
rinvio() {
    local url="https://github.com/$REPO/releases/latest"
    if command -v curl >/dev/null; then
        curl -sI --connect-timeout 15 --max-time 30 "$url"
    elif command -v wget >/dev/null; then
        wget -S --spider --max-redirect=0 -T 30 "$url" 2>&1
    fi | tr -d '\r' | sed -n 's|^ *[Ll]ocation: .*/releases/tag/||p' | head -1
}
TAG=$(rinvio 2>/dev/null || true)
if [ -n "$TAG" ] && valido "$TAG"; then
    echo "$TAG"
    exit 0
fi

# ── 3. git ls-remote ─────────────────────────────────────────────────────────
TAG=$(tag_remoti 2>/dev/null | head -1 || true)
if [ -n "$TAG" ] && valido "$TAG"; then
    echo "$TAG"
    exit 0
fi

echo "Non riesco a sapere quale sia l'ultima release di stable-diffusion.cpp (rete?)." >&2
exit 1
