"""Persistent host-side settings: which roots/paths are exposed."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field


def config_dir() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "skeleton-key")


@dataclass
class HostConfig:
    project_roots: list[str] = field(default_factory=lambda: ["Documents/github"])
    extra_paths: list[str] = field(default_factory=list)
    # home-relative item path -> exposed?  Overrides the catalog default.
    exposure: dict[str, bool] = field(default_factory=dict)
    path: str = field(default="", repr=False, compare=False)

    @classmethod
    def load(cls, path: str | None = None) -> "HostConfig":
        path = path or os.path.join(config_dir(), "host.json")
        cfg = cls(path=path)
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    raw = json.load(fh)
                cfg.project_roots = [str(p) for p in raw.get("project_roots", cfg.project_roots)]
                cfg.extra_paths = [str(p) for p in raw.get("extra_paths", [])]
                cfg.exposure = {str(k): bool(v) for k, v in raw.get("exposure", {}).items()}
            except (OSError, ValueError):
                pass  # corrupt config -> defaults
        return cfg

    def save(self) -> None:
        if not self.path:
            return
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        data = asdict(self)
        data.pop("path")
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, self.path)


def to_home_rel(home: str, path: str) -> str:
    """Normalise user input (~/x, /abs/x, x) to a home-relative path, refusing escapes."""
    path = path.strip()
    if not path:
        raise ValueError("empty path")
    expanded = os.path.expanduser(path)
    absolute = os.path.normpath(expanded if os.path.isabs(expanded) else os.path.join(home, expanded))
    home_real = os.path.normpath(home)
    if absolute != home_real and not absolute.startswith(home_real + os.sep):
        raise ValueError("only paths inside your home directory can be shared")
    rel = os.path.relpath(absolute, home_real)
    if rel == ".":
        raise ValueError("refusing to share your entire home directory")
    return rel.replace(os.sep, "/")
