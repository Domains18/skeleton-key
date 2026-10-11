"""Host side: advertise on the LAN, pair with a PIN, and serve *only* manifest entries.

This is deliberately not a file server: the client can ask for a manifest, for a
file *id* from that manifest, or for a git bundle of a repo *id* from that manifest.
Nothing else. Paths never cross the wire as requests.
"""
from __future__ import annotations

import os
import socket
import subprocess
import tempfile
import threading
import time
from collections import deque
from typing import Callable

from .config import HostConfig
from .discovery import Advertiser, lan_ip
from .platforms import Profile, default_home_for
from .scanner import Manifest, build_manifest
from .secure import AuthError, ProtocolError, SecureChannel, host_handshake, new_pin

MAX_PIN_FAILURES = 5


class HostServer:
    def __init__(self, profile: Profile, cfg: HostConfig, *, port: int = 0, advertise: bool = True,
                 bind: str = "0.0.0.0", on_event: Callable[[str], None] | None = None):
        self.profile = profile
        self.cfg = cfg
        self.pin = new_pin()
        self.events: deque[dict] = deque(maxlen=300)
        self.session: dict | None = None
        self._on_event = on_event
        self._advertise = advertise
        self._failures = 0
        self._session_lock = threading.Lock()
        self._cache: dict[tuple, Manifest] = {}
        self._cache_lock = threading.Lock()
        self._stop = threading.Event()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((bind, port))
        self._sock.listen(4)
        self.port = self._sock.getsockname()[1]
        self.address = lan_ip() if bind == "0.0.0.0" else bind
        self._adv: Advertiser | None = None
        self._thread: threading.Thread | None = None

    # -- lifecycle ----------------------------------------------------------
    def start(self) -> "HostServer":
        if self._advertise:
            try:
                self._adv = Advertiser(self.port, self.profile.hostname, self.profile.os, self.profile.user)
            except Exception as exc:  # mDNS is a convenience; manual address still works
                self._log(f"mDNS advertisement failed ({exc}); clients can connect to {self.address}:{self.port}")
        self._thread = threading.Thread(target=self._accept_loop, name="sk-host", daemon=True)
        self._thread.start()
        self._log(f"Listening on {self.address}:{self.port} — PIN {self.pin}")
        return self

    def stop(self) -> None:
        self._stop.set()
        try:
            self._sock.close()
        except OSError:
            pass
        if self._adv:
            self._adv.close()

    def rotate_pin(self) -> str:
        self.pin = new_pin()
        self._failures = 0
        self._log("PIN rotated")
        return self.pin

    def invalidate(self) -> None:
        with self._cache_lock:
            self._cache.clear()

    # -- manifests ----------------------------------------------------------
    def manifest_for(self, target: Profile) -> Manifest:
        key = tuple(sorted(target.to_dict().items()))
        with self._cache_lock:
            cached = self._cache.get(key)
            if cached and time.time() - cached.generated_at < 120:
                return cached
        m = build_manifest(self.profile.home, self.cfg, self.profile, target)
        with self._cache_lock:
            self._cache[key] = m
        return m

    def preview_target(self) -> Profile:
        """What the host UI previews against: a Mac (or Linux, if we *are* a Mac) for the same user."""
        other = "macos" if self.profile.os == "linux" else "linux"
        return Profile(os=other, arch="arm64" if other == "macos" else "x86_64",
                       home=default_home_for(other, self.profile.user), user=self.profile.user, hostname="new-machine")

    # -- networking ---------------------------------------------------------
    def _log(self, msg: str) -> None:
        self.events.append({"t": time.time(), "msg": msg})
        if self._on_event:
            self._on_event(msg)

    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            try:
                conn, addr = self._sock.accept()
            except OSError:
                break
            threading.Thread(target=self._handle, args=(conn, addr), daemon=True).start()

    def _handle(self, conn: socket.socket, addr) -> None:
        peer = f"{addr[0]}:{addr[1]}"
        if not self._session_lock.acquire(blocking=False):
            conn.close()
            self._log(f"Rejected {peer}: another client is already connected")
            return
        ch: SecureChannel | None = None
        try:
            try:
                ch = host_handshake(conn, self.pin)
            except (AuthError, ProtocolError, ConnectionError, OSError) as exc:
                self._failures += 1
                self._log(f"Pairing failed from {peer}: {exc}")
                if self._failures >= MAX_PIN_FAILURES:
                    self.rotate_pin()
                    self._log(f"Too many failed attempts — new PIN {self.pin}")
                return
            self._failures = 0
            self.session = {"peer": peer, "sas": ch.sas, "since": time.time(), "target": None}
            self._log(f"Paired with {peer}. Verify code on both screens: {ch.sas}")
            self._serve(ch)
        except (ConnectionError, OSError):
            self._log(f"{peer} disconnected")
        except ProtocolError as exc:
            self._log(f"Protocol error from {peer}: {exc}")
        finally:
            if ch:
                ch.close()
            else:
                conn.close()
            self.session = None
            self._session_lock.release()

    def _serve(self, ch: SecureChannel) -> None:
        manifest: Manifest | None = None
        while True:
            req = ch.recv()
            kind = req.get("type")
            if kind == "hello":
                target = Profile.from_dict(req["profile"])
                self.session["target"] = target.to_dict()
                self._log(f"Client is {target.user}@{target.hostname} ({target.os}/{target.arch}); building manifest…")
                manifest = self.manifest_for(target)
                ch.send({"type": "manifest", "manifest": manifest.to_dict()})
                self._log(f"Manifest sent: {len(manifest.files)} files, {len(manifest.repo_paths)} repos")
            elif kind == "file" and manifest:
                self._send_file(ch, manifest.files.get(str(req.get("id"))))
            elif kind == "bundle" and manifest:
                self._send_bundle(ch, manifest.repo_paths.get(str(req.get("id"))))
            elif kind == "bye":
                self._log("Client finished")
                return
            else:
                ch.send({"ok": False, "error": "unknown or out-of-order request"})

    def _send_file(self, ch: SecureChannel, path: str | None) -> None:
        if not path:
            ch.send({"ok": False, "error": "not in manifest"})
            return
        try:
            fh = open(path, "rb")
        except OSError as exc:
            ch.send({"ok": False, "error": exc.strerror or "unreadable"})
            return
        with fh:
            st = os.fstat(fh.fileno())
            ch.send_stream(fh, st.st_size, {"mode": st.st_mode & 0o7777})

    def _send_bundle(self, ch: SecureChannel, repo: str | None) -> None:
        if not repo:
            ch.send({"ok": False, "error": "not in manifest"})
            return
        with tempfile.TemporaryDirectory(prefix="skeleton-key-") as tmp:
            out = os.path.join(tmp, "repo.bundle")
            r = subprocess.run(["git", "-C", repo, "bundle", "create", out, "--all"],
                               capture_output=True, text=True)
            if r.returncode != 0 or not os.path.exists(out):
                ch.send({"ok": False, "error": (r.stderr.strip() or "git bundle failed")[:300]})
                return
            with open(out, "rb") as fh:
                ch.send_stream(fh, os.fstat(fh.fileno()).st_size)
        self._log(f"Sent git bundle of {os.path.relpath(repo, self.profile.home)}")
