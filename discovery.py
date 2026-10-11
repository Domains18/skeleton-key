"""LAN discovery over mDNS/Bonjour (works out of the box on macOS; Linux needs avahi or nothing at all,
since python-zeroconf speaks mDNS itself)."""
from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass

SERVICE_TYPE = "_skeletonkey._tcp.local."


@dataclass
class HostAd:
    name: str
    address: str
    port: int
    os: str = ""
    user: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def lan_ip() -> str:
    """Best-effort primary LAN address (gethostbyname(hostname) is often 127.0.1.1 on Debian/Pop!_OS)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no packet is sent
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class Advertiser:
    def __init__(self, port: int, hostname: str, os_name: str, user: str):
        from zeroconf import ServiceInfo, Zeroconf

        self._zc = Zeroconf()
        self.address = lan_ip()
        self._info = ServiceInfo(
            SERVICE_TYPE,
            f"{hostname}-{port}.{SERVICE_TYPE}",
            addresses=[socket.inet_aton(self.address)],
            port=port,
            properties={"os": os_name, "user": user, "v": "1"},
            server=f"{hostname}.local.",
        )
        self._zc.register_service(self._info)

    def close(self) -> None:
        try:
            self._zc.unregister_service(self._info)
        finally:
            self._zc.close()


def discover(timeout: float = 4.0) -> list[HostAd]:
    from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

    found: dict[str, HostAd] = {}
    lock = threading.Lock()

    class _Listener(ServiceListener):
        def add_service(self, zc, type_, name):
            info = zc.get_service_info(type_, name, timeout=2000)
            if not info or not info.addresses:
                return
            props = {k.decode(): (v or b"").decode() for k, v in (info.properties or {}).items()}
            ad = HostAd(name=name.replace("." + SERVICE_TYPE, ""), address=socket.inet_ntoa(info.addresses[0]),
                        port=info.port, os=props.get("os", ""), user=props.get("user", ""))
            with lock:
                found[name] = ad

        def update_service(self, zc, type_, name):
            self.add_service(zc, type_, name)

        def remove_service(self, zc, type_, name):
            with lock:
                found.pop(name, None)

    zc = Zeroconf()
    try:
        ServiceBrowser(zc, SERVICE_TYPE, _Listener())
        time.sleep(timeout)
    finally:
        zc.close()
    with lock:
        return list(found.values())
