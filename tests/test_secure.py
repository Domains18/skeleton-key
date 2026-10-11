import socket
import threading
import pytest
from skeleton_key.secure import (
    AuthError,
    ProtocolError,
    client_handshake,
    host_handshake,
    new_pin,
)


def test_pin_generation():
    pin = new_pin()
    assert len(pin) == 6
    assert pin.isdigit()


def test_handshake_and_secure_channel():
    pin = "123456"
    s_srv, s_cli = socket.socketpair()

    ch_srv = None
    ch_cli = None
    err = None

    def run_host():
        nonlocal ch_srv, err
        try:
            ch_srv = host_handshake(s_srv, pin)
        except Exception as e:
            err = e

    t = threading.Thread(target=run_host)
    t.start()

    try:
        ch_cli = client_handshake(s_cli, pin)
    finally:
        t.join()

    assert err is None
    assert ch_srv is not None
    assert ch_cli is not None
    # Verify Short Authentication String (SAS) match on both sides
    assert ch_srv.sas == ch_cli.sas
    assert len(ch_srv.sas) == 7  # e.g. "ABC-DEF"

    # Test typed messages
    ch_cli.send({"msg": "hello from client", "num": 42})
    received = ch_srv.recv()
    assert received["msg"] == "hello from client"
    assert received["num"] == 42

    ch_srv.send({"resp": "ok"})
    assert ch_cli.recv()["resp"] == "ok"

    # Test raw bytes
    ch_srv.send_bytes(b"some raw payload")
    assert ch_cli.recv_bytes() == b"some raw payload"

    ch_srv.close()
    ch_cli.close()


def test_handshake_wrong_pin_rejected():
    s_srv, s_cli = socket.socketpair()

    def run_host():
        try:
            host_handshake(s_srv, "111111")
        except Exception:
            pass
        finally:
            try:
                s_srv.close()
            except OSError:
                pass

    t = threading.Thread(target=run_host)
    t.start()

    with pytest.raises((AuthError, ProtocolError, ConnectionError, OSError)):
        client_handshake(s_cli, "999999", timeout=2)

    t.join()
    try:
        s_cli.close()
    except OSError:
        pass
