"""Encrypted, PIN-authenticated channel between host and client.

Handshake (raw TCP):
    host  -> client : MAGIC || host_pub(32)
    client-> host   : MAGIC || client_pub(32)
    both derive     : HKDF-SHA256(ikm=X25519(shared), salt=SHA256(host_pub||client_pub),
                                  info=MAGIC||"|pin|"||PIN) -> k_host_to_client || k_client_to_host
    client-> host   : E{"type":"confirm"}      (wrong PIN => AES-GCM tag failure => host drops)
    host  -> client : E{"type":"confirm-ok"}

After that every frame is: len(4, BE) || AES-GCM(key_dir, nonce=counter, aad=MAGIC||dir).
Counter nonces give replay/reorder protection; separate keys per direction stop reflection.

The PIN alone is brute-forceable by an *active* MITM (6 digits), so both sides also
display a short authentication string (SAS) derived from the transcript. If the codes
shown on both screens match, nobody is in the middle.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import socket
import struct
from typing import BinaryIO

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC = b"SKELKEY1"
MAX_FRAME = 4 * 1024 * 1024 + 64
CHUNK = 1024 * 1024
_JSON, _BYTES = b"J", b"B"


class ProtocolError(Exception):
    pass


class AuthError(ProtocolError):
    """Wrong PIN (or tampering)."""


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("peer closed the connection")
        buf.extend(chunk)
    return bytes(buf)


def _pub_bytes(key: x25519.X25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def _derive(shared: bytes, host_pub: bytes, client_pub: bytes, pin: str) -> tuple[bytes, bytes, str]:
    transcript = host_pub + client_pub
    okm = HKDF(
        algorithm=hashes.SHA256(),
        length=64,
        salt=hashlib.sha256(transcript).digest(),
        info=MAGIC + b"|pin|" + pin.strip().encode(),
    ).derive(shared)
    digest = hashlib.sha256(b"sas" + transcript).hexdigest().upper()
    sas = f"{digest[:3]}-{digest[3:6]}"
    return okm[:32], okm[32:], sas


class SecureChannel:
    def __init__(self, sock: socket.socket, send_key: bytes, recv_key: bytes,
                 send_dir: bytes, recv_dir: bytes, sas: str):
        self.sock = sock
        self.sas = sas
        self._send = AESGCM(send_key)
        self._recv = AESGCM(recv_key)
        self._send_aad = MAGIC + send_dir
        self._recv_aad = MAGIC + recv_dir
        self._send_ctr = 0
        self._recv_ctr = 0

    # -- framing ------------------------------------------------------------
    def _write(self, plaintext: bytes) -> None:
        nonce = self._send_ctr.to_bytes(12, "big")
        self._send_ctr += 1
        ct = self._send.encrypt(nonce, plaintext, self._send_aad)
        self.sock.sendall(struct.pack(">I", len(ct)) + ct)

    def _read(self) -> bytes:
        (length,) = struct.unpack(">I", _recv_exact(self.sock, 4))
        if length > MAX_FRAME:
            raise ProtocolError(f"frame too large ({length} bytes)")
        ct = _recv_exact(self.sock, length)
        nonce = self._recv_ctr.to_bytes(12, "big")
        self._recv_ctr += 1
        try:
            return self._recv.decrypt(nonce, ct, self._recv_aad)
        except InvalidTag as exc:
            raise AuthError("decryption failed (wrong PIN or tampered stream)") from exc

    # -- typed messages -----------------------------------------------------
    def send(self, obj: dict) -> None:
        self._write(_JSON + json.dumps(obj, separators=(",", ":")).encode())

    def recv(self) -> dict:
        data = self._read()
        if data[:1] != _JSON:
            raise ProtocolError("expected a JSON frame")
        return json.loads(data[1:])

    def send_bytes(self, data: bytes) -> None:
        self._write(_BYTES + data)

    def recv_bytes(self) -> bytes:
        data = self._read()
        if data[:1] != _BYTES:
            raise ProtocolError("expected a bytes frame")
        return data[1:]

    # -- streaming ----------------------------------------------------------
    def send_stream(self, fh: BinaryIO, size: int, meta: dict | None = None) -> None:
        self.send({"ok": True, "size": size, **(meta or {})})
        remaining = size
        while remaining > 0:
            chunk = fh.read(min(CHUNK, remaining))
            if not chunk:
                raise ProtocolError("file shrank during transfer")
            remaining -= len(chunk)
            self.send_bytes(chunk)
        self.send_bytes(b"")  # terminator

    def recv_stream(self, out: BinaryIO, max_size: int | None = None) -> dict:
        header = self.recv()
        if not header.get("ok"):
            raise ProtocolError(header.get("error", "transfer refused"))
        total = 0
        while True:
            chunk = self.recv_bytes()
            if not chunk:
                break
            total += len(chunk)
            if max_size is not None and total > max_size:
                raise ProtocolError("stream exceeded announced size")
            out.write(chunk)
        if total != header.get("size", total):
            raise ProtocolError(f"short transfer: got {total} of {header.get('size')} bytes")
        return header

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


def host_handshake(sock: socket.socket, pin: str, timeout: float = 60) -> SecureChannel:
    sock.settimeout(timeout)
    priv = x25519.X25519PrivateKey.generate()
    host_pub = _pub_bytes(priv)
    sock.sendall(MAGIC + host_pub)
    hello = _recv_exact(sock, len(MAGIC) + 32)
    if hello[: len(MAGIC)] != MAGIC:
        raise ProtocolError("not a skeleton-key client")
    client_pub = hello[len(MAGIC):]
    shared = priv.exchange(x25519.X25519PublicKey.from_public_bytes(client_pub))
    k_h2c, k_c2h, sas = _derive(shared, host_pub, client_pub, pin)
    ch = SecureChannel(sock, k_h2c, k_c2h, b"H", b"C", sas)
    if ch.recv().get("type") != "confirm":
        raise ProtocolError("bad confirmation")
    ch.send({"type": "confirm-ok"})
    sock.settimeout(300)
    return ch


def client_handshake(sock: socket.socket, pin: str, timeout: float = 30) -> SecureChannel:
    sock.settimeout(timeout)
    hello = _recv_exact(sock, len(MAGIC) + 32)
    if hello[: len(MAGIC)] != MAGIC:
        raise ProtocolError("not a skeleton-key host")
    host_pub = hello[len(MAGIC):]
    priv = x25519.X25519PrivateKey.generate()
    client_pub = _pub_bytes(priv)
    sock.sendall(MAGIC + client_pub)
    shared = priv.exchange(x25519.X25519PublicKey.from_public_bytes(host_pub))
    k_h2c, k_c2h, sas = _derive(shared, host_pub, client_pub, pin)
    ch = SecureChannel(sock, k_c2h, k_h2c, b"C", b"H", sas)
    ch.send({"type": "confirm"})
    try:
        reply = ch.recv()
    except ConnectionError as exc:
        raise AuthError("host rejected the PIN") from exc
    if reply.get("type") != "confirm-ok":
        raise AuthError("host rejected the PIN")
    sock.settimeout(300)
    return ch


def new_pin() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"
