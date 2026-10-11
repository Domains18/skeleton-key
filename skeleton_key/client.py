"""Client side: connect to a host and pull files / bundles by manifest id."""
from __future__ import annotations

import io
import socket
import threading

from .platforms import Profile
from .secure import ProtocolError, client_handshake


class HostConnection:
    def __init__(self, address: str, port: int, pin: str, connect_timeout: float = 10):
        sock = socket.create_connection((address, int(port)), timeout=connect_timeout)
        try:
            self.ch = client_handshake(sock, pin)
        except Exception:
            sock.close()
            raise
        self.address, self.port = address, int(port)
        self.sas = self.ch.sas
        self._lock = threading.Lock()

    def hello(self, profile: Profile) -> dict:
        with self._lock:
            self.ch.send({"type": "hello", "profile": profile.to_dict()})
            resp = self.ch.recv()
        if resp.get("type") != "manifest":
            raise ProtocolError(resp.get("error", "host did not return a manifest"))
        return resp["manifest"]

    def fetch(self, file_id: str) -> tuple[bytes, int | None]:
        buf = io.BytesIO()
        with self._lock:
            self.ch.send({"type": "file", "id": file_id})
            header = self.ch.recv_stream(buf)
        return buf.getvalue(), header.get("mode")

    def fetch_bundle(self, repo_id: str, dest_path: str) -> None:
        with self._lock, open(dest_path, "wb") as fh:
            self.ch.send({"type": "bundle", "id": repo_id})
            self.ch.recv_stream(fh)

    def close(self) -> None:
        try:
            with self._lock:
                self.ch.send({"type": "bye"})
        except Exception:
            pass
        self.ch.close()
