#!/bin/bash
# ---------------------------------------------------------------------------
# RuscaLinux — quale versione di llama.cpp costruire.
#
#   ./ultima-versione.sh            stampa  "v0.8.0 2026-10-28T12:47:51Z"
#
# Stampa il tag dell'ultima release STABILE di llama.cpp e, se la conosce,
# la data di pubblicazione (puo' mancare). La usano make-deb.sh, per sapere
# cosa scaricare, e build.sh, per accorgersi che e' uscita una release nuova.
#
# Stabile vuol dire: la release che GitHub indica come "Latest" (non una
# pre-release, non una bozza) e con un tag nella forma vX.Y.Z. I tag bNNNN
# di llama.cpp sono build automatiche di ogni commit e non contano.
#
# RUSCALLAMA_LLAMA_VERSION=0.7.0 fissa una versione: viene stampata e basta.
#
# Tre modi di saperlo, nell'ordine; si passa al successivo se uno fallisce:
#   1. API di GitHub (da' anche la data). Senza autenticazione ammette 60
#      richieste l'ora per indirizzo IP: su reti condivise finiscono presto.
#      Con GITHUB_TOKEN nell'ambiente il limite sale.
#   2. Il rinvio di github.com/<repo>/releases/latest, che punta al tag.
#   3. git ls-remote: il tag vX.Y.Z piu' alto.
#
# Esce con 1 se non riesce a saperlo (niente rete), con 2 se la versione
# fissata non e' valida.
# ---------------------------------------------------------------------------
set -euo pipefail

REPO="ggml-org/llama.cpp"

valido() { [[ "$1" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; }

# ── Versione fissata a mano ──────────────────────────────────────────────────
RICHIESTA="${RUSCALLAMA_LLAMA_VERSION:-latest}"
if [ "$RICHIESTA" != latest ]; then
    TAG="v${RICHIESTA#v}"
    if ! valido "$TAG"; then
        echo "RUSCALLAMA_LLAMA_VERSION non valida: \"$RICHIESTA\" (es. 0.8.0)" >&2
        exit 2
    fi
    echo "$TAG"
    exit 0
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
if command -v git >/dev/null; then
    TAG=$(timeout 60 git ls-remote --tags --refs "https://github.com/$REPO.git" 'v*' \
              2>/dev/null | sed -n 's|.*refs/tags/||p' \
              | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1 || true)
    if [ -n "$TAG" ] && valido "$TAG"; then
        echo "$TAG"
        exit 0
    fi
fi

echo "Non riesco a sapere quale sia l'ultima release di llama.cpp (rete?)." >&2
exit 1
