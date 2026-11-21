#!/usr/bin/env python3
"""RuscaLinux OS Apps — generatore delle icone (GPL-3.0).

Ogni icona è l'emblema di RuscaLinux: l'anello prugna con l'apertura in basso.
Al posto dell'aeroplanino di carta, dentro l'anello c'è il simbolo del tool.
Così l'icona dice insieme "che cosa fa" e "da dove viene".

Uso: python3 gen_icons.py <cartella-di-uscita>
Scrive <tool>.svg (128 px) per ogni tool. Le icone simboliche (16 px) restano
quelle disegnate a mano: a 16 px l'anello coprirebbe il simbolo, e GNOME vuole
icone simboliche semplici e leggibili.
"""
import os, sys

# Anello dell'emblema (branding/logos/emblem-ruscalinux.svg), coordinate originali.
RING = ("M213.2,385.4c-81.2-13.6-137.1-89.8-125-171.8c10.7-72.2,71.2-127.3,144-131.2"
        "c84.2-4.5,156.4,60.8,161.1,145c3.2,57.1-23.7,110.1-66.7,141.4c-15.3,11.1-34.8,19.3-51.2,12.5"
        "c-15.6-6.5-19.1-26.6-11.4-39.8c15.1-25.9,50.7-27.1,73.5-47.8c34.3-31.1,48.2-82.7,33-126.7"
        "c-18.7-54-78.5-87.1-133.1-73.8c-55.7,13.6-94,68-85.1,124.9c7,44.7,42.2,81.1,87,88.2"
        "c16.1,2.5,23.3,23.1,13.4,36.2C241.6,411.3,222.8,387,213.2,385.4z")
# Geometria misurata sul tracciato: ingombro 87–393 × 82–390,
# foro interno: cerchio inscritto di centro (262, 199) e raggio 109.
HOLE_C, HOLE_R = (262.0, 199.0), 109.0
BOX_C = (240.0, 236.0)

# Palette RuscaLinux (specifiche, sezione 4.1)
P900, P800, P600, P500 = "#2d0a1d", "#3a1028", "#7a2357", "#8a2b5f"
P_MID = "#5c1a40"            # già usato nelle icone precedenti
R300, R200, R50, CREAM = "#f2a7c8", "#f8d7e6", "#fbf4f7", "#fff7f0"

# ── Simboli dei tool, disegnati in un riquadro 100 × 100 (centro 50, 50) ──
# Colori sul disco crema: prugna per il segno, rosa per i dettagli.
GLYPHS = {
"ruscacleaner": f'''
  <g transform="rotate(-35 50 50)">
    <rect x="44" y="-6" width="12" height="52" rx="6" fill="{P_MID}"/>
    <rect x="34" y="43" width="32" height="11" rx="3.5" fill="{P600}"/>
    <path d="M35 55H65L75 96Q76.5 103 69 103H31Q23.5 103 25 96Z" fill="{R300}"/>
    <g stroke="{P600}" stroke-width="3.2" stroke-linecap="round" fill="none" opacity="0.8">
      <path d="M42 62 37 97M50 62V97M58 62 63 97"/>
    </g>
  </g>
  <path d="M84 4c1.5 5.8 4.2 8.5 10 10-5.8 1.5-8.5 4.2-10 10-1.5-5.8-4.2-8.5-10-10 5.8-1.5 8.5-4.2 10-10z" fill="{P500}"/>''',

"ruscahub": f'''
  <g stroke="{P_MID}" stroke-width="9" stroke-linecap="round">
    <path d="M38 38 22 22M62 38 78 22M38 62 22 78M62 62 78 78"/>
  </g>
  <g fill="{P600}">
    <circle cx="16" cy="16" r="10"/><circle cx="84" cy="16" r="10"/>
    <circle cx="16" cy="84" r="10"/><circle cx="84" cy="84" r="10"/>
  </g>
  <circle cx="50" cy="50" r="19" fill="{P_MID}"/>
  <circle cx="50" cy="50" r="7" fill="{R300}"/>''',

"ruscamark": f'''
  <g stroke="{P_MID}" stroke-width="13" stroke-linecap="round" fill="none">
    <path d="M40 8 32 92M72 8 64 92M12 32H90M10 68H88"/>
  </g>''',

"ruscawriter": f'''
  <path d="M26 4h48v28c0 22-14 40-24 60-10-20-24-38-24-60z" fill="{P_MID}"/>
  <rect x="26" y="4" width="48" height="11" fill="{P600}"/>
  <path d="M50 44v44" stroke="{CREAM}" stroke-width="4" stroke-linecap="round"/>
  <circle cx="50" cy="42" r="6.5" fill="{CREAM}"/>''',

"ruscallama": f'''
  <path d="M12 10h76a10 10 0 0 1 10 10v46a10 10 0 0 1-10 10H44L22 96V76H12A10 10 0 0 1 2 66V20a10 10 0 0 1 10-10z" fill="{P_MID}"/>
  <path d="M50 20c2.8 11 7.6 15.8 18.6 18.6C57.6 41.4 52.8 46.2 50 57.2 47.2 46.2 42.4 41.4 31.4 38.6 42.4 35.8 47.2 31 50 20z" fill="{CREAM}"/>
  <circle cx="74" cy="22" r="4" fill="{R300}"/>
  <circle cx="27" cy="56" r="3" fill="{R300}"/>''',

"ruscatranslator": f'''
  <path d="M8 2h50a9 9 0 0 1 9 9v30a9 9 0 0 1-9 9H32L16 64V50H8a9 9 0 0 1-9-9V11a9 9 0 0 1 9-9z" fill="{R300}"/>
  <g stroke="{P_MID}" stroke-width="6" stroke-linecap="round"><path d="M12 18h34M12 32h22"/></g>
  <path d="M92 34H42a9 9 0 0 0-9 9v30a9 9 0 0 0 9 9h26l16 14V82h8a9 9 0 0 0 9-9V43a9 9 0 0 0-9-9z" fill="{P_MID}"/>
  <g stroke="{CREAM}" stroke-width="6" stroke-linecap="round"><path d="M46 50h36M46 64h22"/></g>''',

"ruscallisse": f'''
  <!-- Ellittica: caschetto, frangia di lato, occhiali ovali, matita, orbita -->
  <defs>
    <linearGradient id="ell-hair" x1="0.2" y1="0" x2="0.8" y2="1">
      <stop offset="0" stop-color="{P500}"/><stop offset="1" stop-color="{P_MID}"/>
    </linearGradient>
    <radialGradient id="ell-skin" cx="0.42" cy="0.38" r="0.7">
      <stop offset="0" stop-color="{R50}"/><stop offset="1" stop-color="#f3d3e1"/>
    </radialGradient>
  </defs>
  <ellipse cx="50" cy="27" rx="47" ry="11" transform="rotate(-14 50 27)" fill="none" stroke="{R300}" stroke-width="3" stroke-dasharray="74 300" stroke-dashoffset="-148" opacity="0.8"/>
  <path d="M20 100C22 89 34 84 50 84C66 84 78 89 80 100Z" fill="{P600}"/>
  <path d="M41 84 50 95 59 84Z" fill="{CREAM}"/>
  <path d="M12 58C9 28 26 8 50 8C74 8 91 28 88 58C87 72 81 80 70 82H30C19 80 13 72 12 58Z" fill="url(#ell-hair)"/>
  <ellipse cx="50" cy="52" rx="27" ry="31" fill="url(#ell-skin)"/>
  <g transform="translate(80 37) rotate(-54)">
    <rect x="-3" y="-15" width="6" height="26" fill="#e8b04a"/>
    <rect x="-3" y="-19" width="6" height="4.5" fill="{R300}"/>
    <path d="M-3 11H3L0 17Z" fill="{P900}"/>
  </g>
  <path d="M21 52C19 28 33 15 52 15C70 15 82 27 80 44C76 37 70 34 63 34C57 38 50 38 43 36C35 38 27 43 21 52Z" fill="url(#ell-hair)"/>
  <path d="M30 31C38 22 52 19 66 22" fill="none" stroke="{R300}" stroke-width="2.4" stroke-linecap="round" opacity="0.7"/>
  <ellipse cx="33" cy="66" rx="6" ry="3.6" fill="{R300}" opacity="0.75"/>
  <ellipse cx="67" cy="66" rx="6" ry="3.6" fill="{R300}" opacity="0.75"/>
  <circle cx="39" cy="55" r="3.6" fill="{P900}"/>
  <circle cx="61" cy="55" r="3.6" fill="{P900}"/>
  <circle cx="40.3" cy="53.6" r="1.3" fill="{CREAM}"/>
  <circle cx="62.3" cy="53.6" r="1.3" fill="{CREAM}"/>
  <g fill="{CREAM}" fill-opacity="0.25" stroke="{P900}" stroke-width="2.4">
    <ellipse cx="39" cy="55" rx="10.5" ry="8.5"/>
    <ellipse cx="61" cy="55" rx="10.5" ry="8.5"/>
  </g>
  <path d="M48 54Q50 51.5 52 54" fill="none" stroke="{P900}" stroke-width="2.2" stroke-linecap="round"/>
  <path d="M42 70Q50 77 58 70" fill="none" stroke="{P600}" stroke-width="3.2" stroke-linecap="round"/>
  <ellipse cx="50" cy="27" rx="47" ry="11" transform="rotate(-14 50 27)" fill="none" stroke="{R300}" stroke-width="3" stroke-dasharray="148 300"/>
  <circle cx="95" cy="16" r="4.2" fill="{P600}" stroke="{CREAM}" stroke-width="1.6"/>''',
}

TITLES = {"ruscacleaner": "RuscaCleaner", "ruscahub": "RuscaHub", "ruscamark": "RuscaMark",
          "ruscawriter": "RuscaWriter", "ruscallama": "RuscaLLama", "ruscatranslator": "RuscaTranslator",
          "ruscallisse": "RuscaLLisse"}


def full_icon(tool):
    size = 128
    s = 116.0 / 308.0                     # l'anello occupa 116 px su 128
    tx, ty = 64 - BOX_C[0] * s, 64 - BOX_C[1] * s + 1
    hx, hy = HOLE_C[0] * s + tx, HOLE_C[1] * s + ty
    hr = HOLE_R * s
    g = 0.64 * hr * 2 / 100.0            # il simbolo occupa il 64% del foro
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  <title>{TITLES[tool]}</title>
  <desc>Icona di {TITLES[tool]}: l’emblema di RuscaLinux con il simbolo del tool al posto dell’aeroplanino. Generata da gen_icons.py.</desc>
  <defs>
    <linearGradient id="ring" x1="0.15" y1="0" x2="0.75" y2="1">
      <stop offset="0" stop-color="{P500}"/>
      <stop offset="0.5" stop-color="{P600}"/>
      <stop offset="1" stop-color="{P_MID}"/>
    </linearGradient>
    <radialGradient id="disc" cx="0.4" cy="0.35" r="0.75">
      <stop offset="0" stop-color="{CREAM}"/>
      <stop offset="1" stop-color="{R200}"/>
    </radialGradient>
  </defs>
  <!-- disco interno: dà al simbolo un fondo chiaro su qualsiasi sfondo -->
  <circle cx="{hx:.2f}" cy="{hy:.2f}" r="{hr + 1:.2f}" fill="url(#disc)"/>
  <!-- ombra sottile dell'anello (niente sfocature: resta nitida a ogni dimensione) -->
  <path d="{RING}" transform="translate({tx:.3f} {ty + 2:.3f}) scale({s:.5f})" fill="{P900}" opacity="0.22"/>
  <!-- anello dell'emblema RuscaLinux -->
  <path d="{RING}" transform="translate({tx:.3f} {ty:.3f}) scale({s:.5f})" fill="url(#ring)"/>
  <!-- simbolo del tool -->
  <g transform="translate({hx - 50 * g:.3f} {hy - 50 * g:.3f}) scale({g:.4f})">{GLYPHS[tool]}
  </g>
</svg>
'''


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    for tool in GLYPHS:
        with open(os.path.join(out, f"{tool}.svg"), "w", encoding="utf-8") as f:
            f.write(full_icon(tool))
        print("scritto", tool)
