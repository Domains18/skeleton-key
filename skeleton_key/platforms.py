"""Machine profiles and OS-specific path knowledge (Linux <-> macOS only)."""
from __future__ import annotations

import getpass
import os
import platform as _stdlib_platform
import socket
import sys
from dataclasses import asdict, dataclass

SUPPORTED_OS = ("linux", "macos")

# Where Homebrew lives by default on each platform/arch.
BREW_PREFIXES = {
    ("linux", "x86_64"): "/home/linuxbrew/.linuxbrew",
    ("linux", "arm64"): "/home/linuxbrew/.linuxbrew",
    ("macos", "arm64"): "/opt/homebrew",
    ("macos", "x86_64"): "/usr/local",
}

# Home-relative config locations that differ between Linux and macOS.
# Tools not listed here honour ~/.config on both (nvim, kitty, alacritty, wezterm,
# starship, fish, gh, git, tmux, ghostty, ...), so they are copied in place.
LINUX_TO_MAC_LOCATIONS = {
    ".config/Code/User": "Library/Application Support/Code/User",
    ".config/Code - Insiders/User": "Library/Application Support/Code - Insiders/User",
    ".config/VSCodium/User": "Library/Application Support/VSCodium/User",
    ".config/Cursor/User": "Library/Application Support/Cursor/User",
    ".config/Windsurf/User": "Library/Application Support/Windsurf/User",
    ".config/lazygit": "Library/Application Support/lazygit",
    ".config/zed": ".config/zed",
    ".local/share/pnpm": "Library/pnpm",
}
MAC_TO_LINUX_LOCATIONS = {v: k for k, v in LINUX_TO_MAC_LOCATIONS.items()}


@dataclass(frozen=True)
class Profile:
    """Everything an adapter needs to know about one side of the transfer."""

    os: str
    arch: str
    home: str
    user: str
    hostname: str

    @property
    def brew_prefix(self) -> str:
        return BREW_PREFIXES.get((self.os, self.arch), "/usr/local")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        os_name = data.get("os")
        if os_name not in SUPPORTED_OS:
            raise ValueError(f"Unsupported OS {os_name!r}; skeleton-key supports Linux and macOS only")
        return cls(
            os=os_name,
            arch=_norm_arch(str(data.get("arch", "x86_64"))),
            home=str(data["home"]).rstrip("/") or "/",
            user=str(data["user"]),
            hostname=str(data.get("hostname", "unknown")),
        )


def _norm_arch(arch: str) -> str:
    arch = arch.lower()
    if arch in ("aarch64", "arm64", "armv8"):
        return "arm64"
    return "x86_64"


def current_os() -> str:
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    raise RuntimeError(f"skeleton-key supports Linux and macOS only (got {sys.platform})")


def detect(home: str | None = None) -> Profile:
    """Profile of the machine we are running on."""
    return Profile(
        os=current_os(),
        arch=_norm_arch(_stdlib_platform.machine()),
        home=os.path.abspath(home or os.path.expanduser("~")),
        user=getpass.getuser(),
        hostname=socket.gethostname().split(".")[0],
    )


def default_home_for(os_name: str, user: str) -> str:
    return f"/Users/{user}" if os_name == "macos" else f"/home/{user}"


def relocate(rel: str, src: Profile, dst: Profile) -> str:
    """Map a home-relative path to where the same config lives on the target OS."""
    if src.os == dst.os:
        return rel
    table = LINUX_TO_MAC_LOCATIONS if src.os == "linux" else MAC_TO_LINUX_LOCATIONS
    for old, new in sorted(table.items(), key=lambda kv: -len(kv[0])):
        if rel == old or rel.startswith(old + "/"):
            return new + rel[len(old):]
    return rel
