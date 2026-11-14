#!/bin/bash
#
# Avvia in QEMU la ISO appena costruita, per provarla senza masterizzarla.
#
#   ./test.sh              sessione live, avvio UEFI (come i PC di oggi)
#   ./test.sh --bios       sessione live, avvio BIOS (PC vecchi)
#   ./test.sh --install    aggancia un disco vuoto e prova l'installazione
#   ./test.sh --installed  riavvia il disco gia' installato, senza la ISO
#
# Serve:  sudo apt install qemu-system-x86 qemu-utils ovmf
set -e

cd "$(dirname "$0")"
. ./release.conf

ISO=".work/ruscalinux-$VERSION-$ARCH.iso"
DISCO=".work/disco-di-prova.qcow2"
MEMORIA_UEFI=".work/uefi-vars.fd"

MODO=uefi
DISCO_ACCESO=no
CON_ISO=si

for opzione in "$@"; do
    case "$opzione" in
        --bios)      MODO=bios ;;
        --install)   DISCO_ACCESO=si ;;
        --installed) DISCO_ACCESO=si; CON_ISO=no ;;
        *)           echo "Opzione sconosciuta: $opzione"; exit 1 ;;
    esac
done

if [ "$CON_ISO" = "si" ] && [ ! -f "$ISO" ]; then
    echo "ERRORE: non trovo $ISO — lancia prima ./build.sh"
    exit 1
fi

# Da qui in poi si costruisce la riga di comando di QEMU, pezzo per pezzo,
# dentro la variabile OPZIONI.
OPZIONI="-machine q35 -m 4096 -smp 2"

# KVM rende la macchina virtuale veloce quanto quella vera. Se non c'e'
# funziona lo stesso, ma lentamente.
if [ -r /dev/kvm ]; then
    OPZIONI="$OPZIONI -enable-kvm -cpu host"
else
    echo "Nota: /dev/kvm non disponibile, sara' lento."
fi

# Avvio UEFI. Servono DUE file: il firmware (in sola lettura) e una copia
# scrivibile della sua memoria. Senza la seconda l'installer non riesce a
# registrare la voce di avvio, e al riavvio il PC virtuale dice che non
# trova nessun sistema: sembra un disco non rilevato, ma non lo e'.
if [ "$MODO" = "uefi" ]; then
    FIRMWARE=/usr/share/OVMF/OVMF_CODE_4M.fd
    MODELLO=/usr/share/OVMF/OVMF_VARS_4M.fd

    if [ ! -f "$FIRMWARE" ]; then
        echo "ERRORE: manca OVMF.  Installalo con:  sudo apt install ovmf"
        exit 1
    fi

    mkdir -p .work
    if [ ! -f "$MEMORIA_UEFI" ]; then
        cp "$MODELLO" "$MEMORIA_UEFI"
        chmod u+w "$MEMORIA_UEFI"
    fi

    OPZIONI="$OPZIONI -drive if=pflash,format=raw,readonly=on,file=$FIRMWARE"
    OPZIONI="$OPZIONI -drive if=pflash,format=raw,file=$MEMORIA_UEFI"
fi

# Disco su cui installare. Cancellalo per ricominciare da zero.
if [ "$DISCO_ACCESO" = "si" ]; then
    mkdir -p .work
    if [ ! -f "$DISCO" ]; then
        qemu-img create -f qcow2 "$DISCO" 25G > /dev/null
        echo "Creato un disco vuoto da 25G: $DISCO"
    fi
    OPZIONI="$OPZIONI -drive file=$DISCO,format=qcow2,if=none,id=hd0"
    OPZIONI="$OPZIONI -device virtio-blk-pci,drive=hd0"
fi

# La ISO, e l'ordine di avvio: prima il lettore CD (d), poi il disco (c).
if [ "$CON_ISO" = "si" ]; then
    OPZIONI="$OPZIONI -drive file=$ISO,format=raw,if=none,id=cd0,media=cdrom"
    OPZIONI="$OPZIONI -device ide-cd,drive=cd0,bus=ide.0 -boot order=dc"
else
    OPZIONI="$OPZIONI -boot order=c"
fi

# Schermo, audio, e mouse che segue il cursore invece di essere catturato.
OPZIONI="$OPZIONI -device virtio-vga -display gtk"
OPZIONI="$OPZIONI -device intel-hda -device hda-duplex -usb -device usb-tablet"

echo "Avvio RuscaLinux $VERSION in $MODO..."
qemu-system-x86_64 $OPZIONI
