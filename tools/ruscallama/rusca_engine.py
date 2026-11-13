# -*- coding: utf-8 -*-
# rusca_engine.py — RuscaLinux OS Tools 1.99.3 — GPL-3.0-or-later
#
# Avvio, sorveglianza e interrogazione di ruscallama-engine (llama-server,
# cioe' llama.cpp: software esterno, licenza MIT). Il file e' IDENTICO in
# RuscaLLama e RuscaTranslator: si modifica una volta e si copia.
#
# Privacy e sicurezza (specifiche, sezione 11):
#   * il server ascolta solo su 127.0.0.1, su una porta libera scelta ogni
#     volta, quindi due programmi non si pestano i piedi;
#   * ogni avvio genera una chiave casuale, scritta in XDG_RUNTIME_DIR con
#     permessi 0600 e passata con --api-key-file: gli altri utenti della
#     macchina non possono usare il modello ne' leggere le conversazioni;
#   * le connessioni HTTP vanno solo a 127.0.0.1; il motore e' compilato
#     senza libcurl e non scarica nulla;
#   * un server rimasto orfano viene fermato solo se il processo e' davvero
#     llama-server ed e' dell'utente (controllo su /proc).
import http.client
import json
import os
import re
import secrets
import signal
import socket
import subprocess
import threading
import time

from gi.repository import GLib

# RUSCALLAMA_ENGINE_DIR: per provare un motore compilato a mano.
ENGINE_DIRS = tuple(filter(None, (os.environ.get("RUSCALLAMA_ENGINE_DIR"),
                                  "/usr/lib/ruscallama-engine", "/opt/ruscallama/bin")))
MODEL_DIRS = ("/usr/share/ruscallama/models",
              os.path.join(GLib.get_user_data_dir(), "ruscallama", "models"))
HOST = "127.0.0.1"
READY_TIMEOUT = 900                # s: un modello grande su CPU lenta


class EngineError(Exception):
    """Errore con un messaggio pensato per l'utente (il chiamante lo traduce
    tramite la chiave `key`)."""

    def __init__(self, key, detail=""):
        super().__init__(f"{key}: {detail}" if detail else key)
        self.key = key
        self.detail = detail


def find_binary():
    for d in ENGINE_DIRS:
        p = os.path.join(d, "llama-server")
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def physical_cores():
    """Core fisici: la regola pratica per i thread di llama.cpp."""
    base = "/sys/devices/system/cpu"
    primi = set()
    try:
        for nome in os.listdir(base):
            if nome.startswith("cpu") and nome[3:].isdigit():
                try:
                    with open(os.path.join(base, nome, "topology",
                                           "thread_siblings_list")) as f:
                        primi.add(f.read().strip().split(",")[0].split("-")[0])
                except OSError:
                    continue
    except OSError:
        pass
    return len(primi) or os.cpu_count() or 4


def find_models(extra_dirs=()):
    """Tutti i GGUF utilizzabili come modello principale (niente mmproj,
    niente draft piccoli), dal piu' grande. Restituisce percorsi."""
    trovati = []
    for d in tuple(MODEL_DIRS) + tuple(extra_dirs):
        if not d or not os.path.isdir(d):
            continue
        for root, _dirs, files in os.walk(d):
            for nome in files:
                low = nome.lower()
                if low.endswith(".gguf") and not low.startswith("mmproj"):
                    p = os.path.join(root, nome)
                    if p not in trovati:
                        trovati.append(p)
    trovati.sort(key=lambda p: os.path.getsize(p), reverse=True)
    return trovati


def companions(model):
    """mmproj (visione) e draft MTP accanto al modello. Il draft si riconosce
    dalla dimensione, non solo dal nome: un modello con MTP incorporato ha
    '-mtp' nel nome ma e' grande quanto il principale."""
    mmproj = draft = None
    d = os.path.dirname(model)
    try:
        size_main = os.path.getsize(model)
        for nome in sorted(os.listdir(d)):
            low = nome.lower()
            p = os.path.join(d, nome)
            if not low.endswith(".gguf") or p == model:
                continue
            if low.startswith("mmproj"):
                mmproj = mmproj or p
            elif "mtp" in low and os.path.getsize(p) < size_main * 0.25:
                draft = draft or p
    except OSError:
        pass
    return mmproj, draft


# ── schede grafiche ────────────────────────────────────────────────────────
# Una riga di `llama-server --list-devices`, per esempio:
#   "  Vulkan1: NVIDIA GeForce RTX 3060 Laptop GPU (6144 MiB, 5794 MiB free)"
_DEVICE_RE = re.compile(r"^\s+(\S+):\s+(.*\S)\s+\((\d+) MiB, \d+ MiB free\)\s*$")


def list_devices():
    """Schede grafiche viste dal motore: [(nome, descrizione, MiB)], per
    esempio ("Vulkan1", "NVIDIA GeForce RTX 3060 Laptop GPU", 6144). Lista
    vuota se il motore manca o non vede schede. Il motore inizializza Vulkan,
    quindi puo' servire un secondo: va chiamata fuori dal thread
    dell'interfaccia."""
    binary = find_binary()
    if not binary:
        return []
    try:
        r = subprocess.run([binary, "--list-devices"], stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return []
    devices = []
    for line in (r.stdout + "\n" + r.stderr).splitlines():
        m = _DEVICE_RE.match(line)
        if m:
            devices.append((m.group(1), m.group(2), int(m.group(3))))
    return devices


def device_name(description, devices):
    """Nome attuale (Vulkan0, Vulkan1, ...) della scheda scelta. Si salva la
    descrizione e non il nome, perche' la numerazione puo' cambiare se
    cambiano driver o schede. None: scelta automatica, oppure la scheda non
    c'e' piu'."""
    for name, desc, _mib in devices:
        if description and desc == description:
            return name
    return None


def _runtime_dir():
    base = os.environ.get("XDG_RUNTIME_DIR") or GLib.get_user_runtime_dir()
    d = os.path.join(base, "ruscallama")
    os.makedirs(d, mode=0o700, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def _is_our_llama_server(pid):
    try:
        st = os.stat(f"/proc/{pid}")
        if st.st_uid != os.getuid():
            return False
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            argv0 = f.read().split(b"\0")[0].decode("utf-8", "replace")
        return os.path.basename(argv0) == "llama-server"
    except OSError:
        return False


class Engine:
    """Un llama-server per programma. Le callback arrivano sempre nel thread
    dell'interfaccia (GLib.idle_add)."""

    def __init__(self, app_id, on_log=None, on_state=None):
        self.app_id = app_id
        self.on_log = on_log or (lambda line: None)
        self.on_state = on_state or (lambda state, detail="": None)
        self.proc = None
        self.port = None
        self.key = None
        self.state = "stopped"          # stopped | starting | ready | error
        self.model = None
        self._conn = None
        self._lock = threading.Lock()
        rd = _runtime_dir()
        self._pid_file = os.path.join(rd, f"{app_id}.pid")
        self._key_file = os.path.join(rd, f"{app_id}.key")

    # ── stato ─────────────────────────────────────────────────────────────
    def _set_state(self, state, detail=""):
        self.state = state
        GLib.idle_add(self.on_state, state, detail)

    def _log(self, line):
        GLib.idle_add(self.on_log, line)

    @property
    def running(self):
        return self.proc is not None and self.proc.poll() is None

    # ── avvio ─────────────────────────────────────────────────────────────
    def kill_orphan(self):
        """Ferma un llama-server lasciato acceso da una sessione precedente
        dello stesso programma (crash, logout)."""
        try:
            with open(self._pid_file) as f:
                pid = int(f.read().strip())
        except (OSError, ValueError):
            return
        if _is_our_llama_server(pid):
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                time.sleep(1.0)
                if _is_our_llama_server(pid):
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
            except OSError:
                pass
        for p in (self._pid_file, self._key_file):
            try:
                os.unlink(p)
            except OSError:
                pass

    def start(self, model, args, gpu=True):
        """Avvia il server in background e ritorna subito. `args` sono le
        opzioni specifiche del programma (contesto, thread, cache, ...)."""
        if self.running:
            return
        binary = find_binary()
        if not binary:
            raise EngineError("err_no_engine")
        if not model or not os.path.isfile(model):
            raise EngineError("err_no_model")
        self.kill_orphan()
        self.port = _free_port()
        self.key = secrets.token_urlsafe(24)
        fd = os.open(self._key_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(self.key)
        cmd = [binary, "-m", model, "--host", HOST, "--port", str(self.port),
               "--api-key-file", self._key_file, "--no-webui", "--jinja",
               "-ngl", "99" if gpu else "0"] + [str(a) for a in args]
        env = os.environ.copy()
        if not gpu:
            # Senza scheda grafica i driver Vulkan vengono nascosti: alcuni
            # driver si bloccano anche con -ngl 0.
            env["VK_DRIVER_FILES"] = "/dev/null"
            env["VK_ICD_FILENAMES"] = "/dev/null"
        self._log("$ " + " ".join(cmd))
        try:
            self.proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, text=True, bufsize=1, env=env,
                start_new_session=True)
        except OSError as e:
            raise EngineError("err_start", str(e)) from e
        try:
            with open(self._pid_file, "w") as f:
                f.write(str(self.proc.pid))
        except OSError:
            pass
        self.model = model
        self._set_state("starting")
        proc = self.proc
        threading.Thread(target=self._read_log, args=(proc,), daemon=True).start()
        threading.Thread(target=self._wait_ready, args=(proc,), daemon=True).start()
        threading.Thread(target=self._watch, args=(proc,), daemon=True).start()

    def _read_log(self, proc):
        try:
            for line in iter(proc.stdout.readline, ""):
                self._log(line.rstrip("\n"))
        except (OSError, ValueError):
            pass

    def _watch(self, proc):
        code = proc.wait()
        if self.proc is proc:
            self.proc = None
            self._cleanup_files()
            self._set_state("error", str(code))

    def _wait_ready(self, proc):
        t0 = time.monotonic()
        while self.proc is proc and proc.poll() is None:
            if time.monotonic() - t0 > READY_TIMEOUT:
                self._set_state("error", "timeout")
                return
            try:
                c = http.client.HTTPConnection(HOST, self.port, timeout=2)
                c.request("GET", "/health")
                r = c.getresponse()
                r.read()
                c.close()
                if r.status == 200:
                    self._set_state("ready")
                    return
            except OSError:
                pass
            time.sleep(0.5)

    def wait_ready(self, stop_event=None):
        """Per i thread di lavoro: attende che il server sia pronto."""
        while self.state == "starting":
            if stop_event is not None and stop_event.is_set():
                return False
            time.sleep(0.2)
        return self.state == "ready"

    # ── arresto ───────────────────────────────────────────────────────────
    def stop(self, wait=False):
        self.cancel()
        proc, self.proc = self.proc, None
        if proc is None:
            return
        t = threading.Thread(target=self._terminate, args=(proc,), daemon=True)
        t.start()
        if wait:
            t.join(6)

    def _terminate(self, proc):
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGTERM)
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(pgid, signal.SIGKILL)
                proc.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass
        self._cleanup_files()
        self._set_state("stopped")

    def _cleanup_files(self):
        for p in (self._pid_file, self._key_file):
            try:
                os.unlink(p)
            except OSError:
                pass

    # ── richieste ─────────────────────────────────────────────────────────
    def _headers(self):
        return {"Content-Type": "application/json",
                "Authorization": f"Bearer {self.key}"}

    def chat(self, body, timeout=600):
        """Richiesta senza streaming: restituisce il testo della risposta."""
        body = dict(body, stream=False)
        conn = http.client.HTTPConnection(HOST, self.port, timeout=timeout)
        try:
            conn.request("POST", "/v1/chat/completions", json.dumps(body),
                         self._headers())
            r = conn.getresponse()
            data = r.read().decode("utf-8", "replace")
            if r.status != 200:
                raise EngineError("err_http", f"{r.status} {data[:200]}")
            return json.loads(data)["choices"][0]["message"].get("content") or ""
        finally:
            conn.close()

    def chat_stream(self, body, stop_event, timeout=3600):
        """Streaming SSE: genera coppie (testo, ragionamento). Si interrompe
        quando stop_event e' impostato o quando si chiama cancel()."""
        body = dict(body, stream=True)
        conn = http.client.HTTPConnection(HOST, self.port, timeout=timeout)
        with self._lock:
            self._conn = conn
        try:
            conn.request("POST", "/v1/chat/completions", json.dumps(body),
                         self._headers())
            r = conn.getresponse()
            if r.status != 200:
                raise EngineError("err_http", f"{r.status} {r.read()[:200]!r}")
            for raw in iter(r.readline, b""):
                if stop_event.is_set():
                    break
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    delta = json.loads(payload)["choices"][0]["delta"]
                except (ValueError, KeyError, IndexError):
                    continue
                text = delta.get("content") or ""
                reasoning = delta.get("reasoning_content") or ""
                if text or reasoning:
                    yield text, reasoning
        except OSError:
            if not stop_event.is_set():
                raise
        finally:
            with self._lock:
                self._conn = None
            conn.close()

    def cancel(self):
        """Interrompe la richiesta in corso chiudendo la connessione."""
        with self._lock:
            conn = self._conn
        if conn is not None and conn.sock is not None:
            try:
                conn.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
