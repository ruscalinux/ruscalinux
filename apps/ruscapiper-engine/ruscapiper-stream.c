/*
 * ruscapiper-stream — RuscaLinux OS Apps 1.99.3 — GPL-3.0-or-later
 * Copyright (C) 2026 Nunzio Curcuruto — https://www.ruscalinux.org
 *
 * Voce sempre caricata per RuscaLLisse. Apre una voce Piper una volta sola
 * (con libpiper, l'API in C di Piper: piper1-gpl, GPL-3.0) e poi legge una
 * frase per riga dallo standard input e scrive l'audio sullo standard
 * output, frase dopo frase, finché lo standard input non si chiude.
 * Nessuna rete, nessun file scritto: solo i propri flussi standard.
 *
 * Uso:
 *   ruscapiper-stream --voice VOCE.onnx [--config VOCE.onnx.json]
 *                     [--espeak-data CARTELLA]
 *   ruscapiper-stream --version
 *
 * Protocollo (interi a 32 bit little-endian):
 *
 *   all'avvio, quando la voce è caricata:
 *     "RPS1"  u32 versione del protocollo (1)
 *
 *   in ingresso, una riga UTF-8 per frase:
 *     ID <TAB> LENGTH_SCALE <TAB> TESTO <LF>
 *     (LENGTH_SCALE 0 = quello della voce; il testo senza TAB né LF)
 *
 *   in uscita, per ogni pezzo d'audio della frase:
 *     "RPSC"  u32 id  u32 flags  u32 frequenza  u32 n_campioni
 *             u32 n_fonemi  u32 n_allineamenti
 *     i16 campioni[n_campioni]
 *     u32 fonemi[n_fonemi]           codepoint IPA, gruppi separati da 0
 *     i32 allineamenti[n_allineamenti]  campioni per ogni id di fonema
 *     flags: 1 = ultimo pezzo della frase, 2 = errore (frase non detta)
 *
 * Fonemi e allineamenti (dalla struttura piper_audio_chunk) dicono quale
 * suono si sente in ogni istante: RuscaLLisse li usa per muovere la bocca.
 * Il volume si normalizza a ogni pezzo come fa Piper in Python
 * (normalize_audio): picco a fondo scala.
 */
#include <errno.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "piper.h"

#ifndef RUSCAPIPER_ESPEAK_DATA
#define RUSCAPIPER_ESPEAK_DATA "/usr/lib/ruscapiper-engine/espeak-ng-data"
#endif
#ifndef RUSCAPIPER_VERSION
#define RUSCAPIPER_VERSION "1.99.3"
#endif

#define FLAG_LAST 1u
#define FLAG_ERROR 2u
#define MAX_LINE (64 * 1024)

static void put_u32(uint32_t v, unsigned char *p) {
  p[0] = (unsigned char)(v & 0xff);
  p[1] = (unsigned char)((v >> 8) & 0xff);
  p[2] = (unsigned char)((v >> 16) & 0xff);
  p[3] = (unsigned char)((v >> 24) & 0xff);
}

static int write_all(const void *data, size_t size) {
  return size == 0 || fwrite(data, 1, size, stdout) == size;
}

static int write_header(uint32_t id, uint32_t flags, uint32_t rate,
                        uint32_t n_samples, uint32_t n_phonemes,
                        uint32_t n_alignments) {
  unsigned char h[28];
  memcpy(h, "RPSC", 4);
  put_u32(id, h + 4);
  put_u32(flags, h + 8);
  put_u32(rate, h + 12);
  put_u32(n_samples, h + 16);
  put_u32(n_phonemes, h + 20);
  put_u32(n_alignments, h + 24);
  return write_all(h, sizeof h);
}

/* Campioni float della voce -> 16 bit, con il picco a fondo scala. */
static int write_samples(const float *s, size_t n, int16_t **buf, size_t *cap) {
  if (n == 0)
    return 1;
  if (*cap < n) {
    int16_t *nb = realloc(*buf, n * sizeof **buf);
    if (!nb)
      return 0;
    *buf = nb;
    *cap = n;
  }
  float peak = 0.0f;
  for (size_t i = 0; i < n; i++) {
    float a = fabsf(s[i]);
    if (a > peak)
      peak = a;
  }
  float gain = peak < 1e-8f ? 0.0f : 32767.0f / peak;
  for (size_t i = 0; i < n; i++) {
    float v = s[i] * gain;
    if (v > 32767.0f)
      v = 32767.0f;
    if (v < -32768.0f)
      v = -32768.0f;
    (*buf)[i] = (int16_t)lrintf(v);
  }
  /* il formato è little-endian come la macchina (amd64) */
  return write_all(*buf, n * sizeof **buf);
}

static int write_u32_array(const uint32_t *a, size_t n) {
  unsigned char b[4];
  for (size_t i = 0; i < n; i++) {
    put_u32(a[i], b);
    if (!write_all(b, 4))
      return 0;
  }
  return 1;
}

static int write_i32_array(const int *a, size_t n) {
  unsigned char b[4];
  for (size_t i = 0; i < n; i++) {
    put_u32((uint32_t)a[i], b);
    if (!write_all(b, 4))
      return 0;
  }
  return 1;
}

static void usage(FILE *f) {
  fprintf(f,
          "Uso: ruscapiper-stream --voice VOCE.onnx [--config VOCE.onnx.json]\n"
          "                         [--espeak-data CARTELLA]\n"
          "     ruscapiper-stream --version\n"
          "Legge una frase per riga (ID<TAB>LENGTH_SCALE<TAB>TESTO) e scrive\n"
          "l'audio a 16 bit sullo standard output, frase dopo frase.\n");
}

int main(int argc, char **argv) {
  const char *voice = NULL, *config = NULL;
  const char *espeak_data = RUSCAPIPER_ESPEAK_DATA;

  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--voice") && i + 1 < argc) {
      voice = argv[++i];
    } else if (!strcmp(argv[i], "--config") && i + 1 < argc) {
      config = argv[++i];
    } else if (!strcmp(argv[i], "--espeak-data") && i + 1 < argc) {
      espeak_data = argv[++i];
    } else if (!strcmp(argv[i], "--version")) {
      printf("ruscapiper-stream %s (Piper %s)\n", RUSCAPIPER_VERSION,
             piper_version());
      return 0;
    } else if (!strcmp(argv[i], "--help") || !strcmp(argv[i], "-h")) {
      usage(stdout);
      return 0;
    } else {
      usage(stderr);
      return 2;
    }
  }
  if (!voice) {
    usage(stderr);
    return 2;
  }

  piper_synthesizer *synth = piper_create(voice, config, espeak_data);
  if (!synth) {
    fprintf(stderr, "ruscapiper-stream: non riesco ad aprire la voce %s\n",
            voice);
    return 1;
  }
  piper_synthesize_options defaults = piper_default_synthesize_options(synth);

  piper_audio_chunk chunk;
  unsigned char hello[8];
  memcpy(hello, "RPS1", 4);
  put_u32(1, hello + 4);
  if (!write_all(hello, sizeof hello) || fflush(stdout) != 0) {
    piper_free(synth);
    return 1;
  }

  char *line = malloc(MAX_LINE);
  int16_t *pcm = NULL;
  size_t pcm_cap = 0;
  int status = 0;
  if (!line) {
    piper_free(synth);
    return 1;
  }

  while (fgets(line, MAX_LINE, stdin)) {
    size_t len = strlen(line);
    if (len && line[len - 1] == '\n')
      line[--len] = '\0';
    if (len && line[len - 1] == '\r')
      line[--len] = '\0';
    if (!len)
      continue;

    char *tab1 = strchr(line, '\t');
    char *tab2 = tab1 ? strchr(tab1 + 1, '\t') : NULL;
    if (!tab1 || !tab2) {
      fprintf(stderr, "ruscapiper-stream: riga non valida\n");
      continue;
    }
    *tab1 = *tab2 = '\0';
    errno = 0;
    unsigned long id = strtoul(line, NULL, 10);
    float scale = strtof(tab1 + 1, NULL);
    const char *text = tab2 + 1;

    piper_synthesize_options opts = defaults;
    if (scale > 0.1f && scale < 5.0f)
      opts.length_scale = scale;

    int ok = 1;
    if (piper_synthesize_start(synth, text, &opts) != PIPER_OK) {
      fprintf(stderr, "ruscapiper-stream: frase %lu non sintetizzabile\n", id);
      ok = write_header((uint32_t)id, FLAG_LAST | FLAG_ERROR, 0, 0, 0, 0);
    } else {
      /* libpiper 1.8.0 consegna l'ultimo pezzo insieme a PIPER_DONE (non
       * dopo, come lascerebbe intendere piper.h): il pezzo va scritto anche
       * quando rc == PIPER_DONE. */
      int rc, last_sent = 0;
      for (;;) {
        rc = piper_synthesize_next(synth, &chunk);
        if (rc != PIPER_OK && rc != PIPER_DONE) {
          fprintf(stderr, "ruscapiper-stream: errore nella frase %lu\n", id);
          ok = write_header((uint32_t)id, FLAG_LAST | FLAG_ERROR, 0, 0, 0, 0);
          last_sent = 1;
          break;
        }
        int last = rc == PIPER_DONE || chunk.is_last;
        size_t n_samp = chunk.samples ? chunk.num_samples : 0;
        size_t n_ph = chunk.phonemes ? chunk.num_phonemes : 0;
        size_t n_al = chunk.alignments ? chunk.num_alignments : 0;
        if (n_samp || n_ph || last) {
          ok = write_header((uint32_t)id, last ? FLAG_LAST : 0,
                            (uint32_t)chunk.sample_rate, (uint32_t)n_samp,
                            (uint32_t)n_ph, (uint32_t)n_al) &&
               write_samples(chunk.samples, n_samp, &pcm, &pcm_cap) &&
               write_u32_array((const uint32_t *)chunk.phonemes, n_ph) &&
               write_i32_array(chunk.alignments, n_al) && fflush(stdout) == 0;
          if (!ok)
            break;
        }
        if (last) {
          last_sent = 1;
          break;
        }
      }
      if (ok && !last_sent)
        ok = write_header((uint32_t)id, FLAG_LAST, 0, 0, 0, 0);
    }
    if (!ok || fflush(stdout) != 0) {
      status = 1; /* RuscaLLisse ha chiuso la lettura: si esce */
      break;
    }
  }

  free(line);
  free(pcm);
  piper_free(synth);
  return status;
}
