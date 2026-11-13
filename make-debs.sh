#!/bin/bash
#
# Costruisce i pacchetti .deb che finiscono nella ISO.
#
# Vengono messi in local/extra_debs/, che NON sta in git: sono il risultato
# di branding/ e tools/, non sorgenti. build.sh li ricostruisce da solo se
# la cartella non c'e' o se qualcosa in branding/ o tools/ e' cambiato.
# Puoi comunque lanciarlo a mano quando vuoi.
#
# Dalla 1.99.2 tutto si costruisce qui, senza rete: RuscaWriter e la
# cartella vendor/ non esistono piu'.
set -e

cd "$(dirname "$0")"
. ./release.conf

QUI="$(pwd)"
FUORI="$QUI/local/extra_debs"

# Si lavora in una cartella temporanea e la si sposta al posto giusto solo
# alla fine. Se qualcosa si rompe a meta', local/extra_debs/ non resta mezza
# piena: o c'e' tutta, o non c'e' (e build.sh la ricostruira').
LAVORO="$QUI/local/extra_debs.tmp"
LOG="$QUI/local/make-debs.log"

rm -rf "$LAVORO"
mkdir -p "$LAVORO"
: > "$LOG"
trap 'rm -rf "$LAVORO"' EXIT

for comando in dpkg-deb python3; do
    if ! command -v "$comando" > /dev/null; then
        echo "ERRORE: manca $comando."
        exit 1
    fi
done

# Lancia uno script mandando tutto quello che scrive nel log. Se fallisce,
# mostra le ultime righe: molti script scrivono i loro ERRORE su stdout,
# e con un semplice "> /dev/null" sparirebbero.
esegui() {                        # esegui  DESCRIZIONE  COMANDO...
    local descr="$1"; shift
    local inizio
    echo "==> $descr"
    echo "===== $descr =====" >> "$LOG"
    inizio=$(wc -l < "$LOG")
    if ! "$@" >> "$LOG" 2>&1; then
        echo
        echo "ERRORE: $descr non e' andato a buon fine. Ultime righe:"
        tail -n 20 "$LOG" | sed 's/^/    /'
        echo
        echo "Log completo: local/make-debs.log"
        exit 1
    fi
    # Gli avvisi (righe "ATTENZIONE:" e quelle rientrate che seguono) si
    # mostrano anche a schermo: nel log nessuno li leggerebbe.
    tail -n +"$((inizio + 1))" "$LOG" | awk '
        /^ATTENZIONE:/ { a = 1; print "    " $0; next }
        a && /^[ \t]/  { print "    " $0; next }
        { a = 0 }'
}


# --- Icone, sfondi, caratteri, tema ------------------------------------------
#
# Ognuno di questi script sta accanto ai file che impacchetta e scrive il
# .deb nella cartella corrente: per questo prima ci si sposta in $LAVORO.

cd "$LAVORO"

esegui "Icone" bash "$QUI/branding/icons/make-icons-deb.sh" \
       "$QUI/branding/icons/Adwaita-Prugna.tar.xz" "$BRANDING_VERSION"

esegui "Sfondi" bash "$QUI/branding/backgrounds/make-backgrounds-deb.sh" \
       "$QUI/branding/backgrounds/ruscalinux-backgrounds.tar.xz" "$BRANDING_VERSION"

esegui "Caratteri" bash "$QUI/branding/fonts/make-fonts-deb.sh" \
       "$QUI/branding/fonts/DM_Sans,Syne.zip" "$BRANDING_VERSION"

esegui "Tema" bash "$QUI/branding/theme/make-theme-deb.sh" "$BRANDING_VERSION"

esegui "Tema della Shell" bash "$QUI/branding/shell-theme/make-shell-theme-deb.sh" \
       "$BRANDING_VERSION"

cd "$QUI"


# --- Utility di RuscaLinux -------------------------------------------------
#
# Ogni cartella dentro tools/ e' un'applicazione, con il suo script di
# pacchettizzazione (make-deb.sh). Lo script:
#   - si lancia dalla sua cartella, senza argomenti;
#   - ha la versione scritta dentro di se';
#   - scrive il .deb in build-deb/, con nome <nome>-ruscalinux_<ver>_all.deb;
#   - produce un pacchetto Debian che si chiama come la cartella.
# Questo ciclo le trova da solo: aggiungerne una non richiede modifiche qui.

ATTENZIONE=""

for CARTELLA in "$QUI"/tools/*/; do
    CARTELLA="${CARTELLA%/}"
    NOME=$(basename "$CARTELLA")

    SCRIPT="make-deb.sh"
    if [ ! -f "$CARTELLA/$SCRIPT" ]; then
        echo "ERRORE: in tools/$NOME/ non c'e' lo script make-deb.sh."
        exit 1
    fi

    # Toglie i .deb di build precedenti: alcuni script cancellano solo il
    # file della versione corrente, e un vecchio .deb finirebbe nella ISO.
    rm -f "$CARTELLA"/build-deb/*.deb

    esegui "$NOME" bash -c 'cd "$1" && bash "./$2"' _ "$CARTELLA" "$SCRIPT"

    PRODOTTI=( "$CARTELLA"/build-deb/*.deb )
    if [ ! -f "${PRODOTTI[0]}" ]; then
        echo "ERRORE: $SCRIPT di $NOME non ha prodotto nessun .deb in build-deb/."
        exit 1
    fi
    if [ "${#PRODOTTI[@]}" -ne 1 ]; then
        echo "ERRORE: $SCRIPT di $NOME ha prodotto piu' di un .deb:"
        printf '    %s\n' "${PRODOTTI[@]##*/}"
        exit 1
    fi
    DEB="${PRODOTTI[0]}"

    # build.sh cerca un pacchetto con il nome della cartella.
    PACCHETTO=$(dpkg-deb -f "$DEB" Package)
    if [ "$PACCHETTO" != "$NOME" ]; then
        echo "ERRORE: tools/$NOME/ produce il pacchetto \"$PACCHETTO\"."
        echo "        Il pacchetto Debian deve chiamarsi come la cartella."
        exit 1
    fi

    # Le utility devono avere la stessa versione di RuscaLinux. Non si
    # blocca la build, ma lo si dice chiaramente alla fine.
    VERS=$(dpkg-deb -f "$DEB" Version)
    if [ "$VERS" != "$VERSION" ]; then
        ATTENZIONE="$ATTENZIONE    $NOME e' alla $VERS, RuscaLinux alla $VERSION\n"
    fi

    cp "$DEB" "$LAVORO/"
done


# --- Fine ------------------------------------------------------------------

rm -rf "$FUORI"
mv "$LAVORO" "$FUORI"
trap - EXIT

echo
echo "Pacchetti pronti in local/extra_debs/:"
ls -1sh "$FUORI"/*.deb | sed 's|/.*/|  |'

if [ -n "$ATTENZIONE" ]; then
    echo
    echo "ATTENZIONE: versioni non allineate (cambia VER nel make-deb.sh"
    echo "e APP_VERSION nel programma):"
    printf "$ATTENZIONE"
fi
