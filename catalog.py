"""Curated knowledge about dotfiles: what to offer, what is junk, what is secret.

Everything here is data, so it is easy to extend without touching logic.
Paths are home-relative and use forward slashes.
"""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogEntry:
    path: str
    label: str
    category: str
    note: str = ""
    os_only: str | None = None  # "linux" / "macos": meaningless on the other OS
    default_on: bool = True


CATALOG: tuple[CatalogEntry, ...] = (
    # --- shell -------------------------------------------------------------
    CatalogEntry(".zshrc", "Zsh config", "shell"),
    CatalogEntry(".zshenv", "Zsh env", "shell"),
    CatalogEntry(".zprofile", "Zsh login profile", "shell"),
    CatalogEntry(".zsh_plugins.txt", "Antidote plugin list", "shell", "Install antidote on the new machine: brew install antidote"),
    CatalogEntry(".p10k.zsh", "Powerlevel10k prompt", "shell"),
    CatalogEntry(".oh-my-zsh/custom", "Oh My Zsh custom plugins/themes", "shell", "Install Oh My Zsh first; only your custom/ dir is transferred"),
    CatalogEntry(".bashrc", "Bash config", "shell"),
    CatalogEntry(".bash_profile", "Bash login profile", "shell"),
    CatalogEntry(".bash_aliases", "Bash aliases", "shell"),
    CatalogEntry(".profile", "POSIX profile", "shell"),
    CatalogEntry(".aliases", "Aliases", "shell"),
    CatalogEntry(".inputrc", "Readline", "shell"),
    CatalogEntry(".config/fish", "Fish shell", "shell"),
    CatalogEntry(".config/starship.toml", "Starship prompt", "shell"),
    CatalogEntry(".config/atuin/config.toml", "Atuin", "shell"),
    # --- editors -----------------------------------------------------------
    CatalogEntry(".config/nvim", "Neovim", "editor", "Plugins reinstall automatically on first launch (lazy-lock.json is kept)"),
    CatalogEntry(".vimrc", "Vim", "editor"),
    CatalogEntry(".ideavimrc", "IdeaVim", "editor"),
    CatalogEntry(".config/helix", "Helix", "editor"),
    CatalogEntry(".config/zed", "Zed", "editor"),
    CatalogEntry(".config/Code/User/settings.json", "VS Code settings", "editor"),
    CatalogEntry(".config/Code/User/keybindings.json", "VS Code keybindings", "editor"),
    CatalogEntry(".config/Code/User/snippets", "VS Code snippets", "editor"),
    CatalogEntry(".config/Cursor/User/settings.json", "Cursor settings", "editor"),
    CatalogEntry(".config/Cursor/User/keybindings.json", "Cursor keybindings", "editor"),
    CatalogEntry(".editorconfig", "EditorConfig", "editor"),
    # --- terminal ----------------------------------------------------------
    CatalogEntry(".tmux.conf", "tmux", "terminal"),
    CatalogEntry(".config/tmux", "tmux (XDG)", "terminal"),
    CatalogEntry(".config/alacritty", "Alacritty", "terminal"),
    CatalogEntry(".config/kitty", "Kitty", "terminal"),
    CatalogEntry(".config/wezterm", "WezTerm", "terminal"),
    CatalogEntry(".wezterm.lua", "WezTerm", "terminal"),
    CatalogEntry(".config/ghostty", "Ghostty", "terminal"),
    # --- git & dev tools ---------------------------------------------------
    CatalogEntry(".gitconfig", "Git config", "git"),
    CatalogEntry(".gitignore_global", "Global gitignore", "git"),
    CatalogEntry(".config/git", "Git (XDG)", "git"),
    CatalogEntry(".config/gh/config.yml", "GitHub CLI config", "git"),
    CatalogEntry(".config/lazygit", "lazygit", "git"),
    CatalogEntry(".config/bat", "bat", "tools"),
    CatalogEntry(".config/btop", "btop", "tools"),
    CatalogEntry(".config/htop", "htop", "tools"),
    CatalogEntry(".ripgreprc", "ripgrep", "tools"),
    CatalogEntry(".curlrc", "curl", "tools"),
    CatalogEntry(".npmrc", "npm", "tools"),
    CatalogEntry(".config/mise", "mise", "tools"),
    CatalogEntry(".tool-versions", "asdf/mise versions", "tools"),
    # --- ssh / secrets (opt-in) -------------------------------------------
    CatalogEntry(".ssh/config", "SSH client config", "ssh"),
    CatalogEntry(".ssh/known_hosts", "SSH known hosts", "ssh"),
    CatalogEntry(".ssh", "SSH keys", "ssh", "Private keys are opt-in; consider generating new keys per machine", default_on=False),
    CatalogEntry(".aws/config", "AWS CLI config", "cloud"),
    CatalogEntry(".kube/config", "kubeconfig", "cloud", default_on=False),
    # --- desktop-specific --------------------------------------------------
    CatalogEntry(".config/i3", "i3", "desktop", os_only="linux"),
    CatalogEntry(".config/sway", "Sway", "desktop", os_only="linux"),
    CatalogEntry(".config/hypr", "Hyprland", "desktop", os_only="linux"),
    CatalogEntry(".config/waybar", "Waybar", "desktop", os_only="linux"),
    CatalogEntry(".config/rofi", "Rofi", "desktop", os_only="linux"),
    CatalogEntry(".Xresources", "X resources", "desktop", os_only="linux"),
    CatalogEntry(".xinitrc", "xinit", "desktop", os_only="linux"),
    CatalogEntry(".config/aerospace", "AeroSpace", "desktop", os_only="macos"),
    CatalogEntry(".config/karabiner", "Karabiner", "desktop", os_only="macos"),
    CatalogEntry(".hammerspoon", "Hammerspoon", "desktop", os_only="macos"),
    CatalogEntry(".yabairc", "yabai", "desktop", os_only="macos"),
    CatalogEntry(".skhdrc", "skhd", "desktop", os_only="macos"),
)

# Directories never descended into (inside dotfile dirs and project trees).
JUNK_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".cache", "plugged", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".next", ".turbo",
    ".gradle", ".dart_tool", "target", "dist", "build", ".parcel-cache",
})

# Basenames (globs) that are machine state, not configuration.
JUNK_FILES = (
    ".DS_Store", "*.swp", "*.swo", "*~", "*.zwc", ".zcompdump*", "*.log", "*.pyc",
    "*history", "*.sock", "*.pid", ".lesshst", ".viminfo", "*.tmp", "*.tmp.*",
)

# Home-relative globs whose *whole file* is secret material: offered, but off by default.
SECRET_FILES = (
    ".ssh/id_*", ".ssh/*.pem", ".ssh/*_rsa", ".ssh/*_ed25519", ".aws/credentials",
    ".netrc", ".git-credentials", ".pypirc", ".docker/config.json",
    ".config/gh/hosts.yml", ".gnupg/*", ".kube/config", "*.pem", "*.key", "*.p12",
    ".env", ".env.*",
)
NOT_SECRET = (".ssh/*.pub",)

# Content patterns that look like inline credentials (warn, line-level).
SECRET_PATTERNS = (
    ("GitHub token", re.compile(r"\b(ghp|gho|ghu|ghs)_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("API key (sk-…)", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("npm auth token", re.compile(r"_authToken\s*=")),
    ("credential assignment", re.compile(
        r"""(?i:\b\w*(api[_-]?key|secret|token|password|passwd)\w*\s*[=:]\s*['"]?[A-Za-z0-9_\-+]{16,})""")),
)

# Size limits.
MAX_DOTFILE_BYTES = 10 * 1024 * 1024
MAX_LOOSE_PROJECT_FILE_BYTES = 25 * 1024 * 1024
MAX_FILES_PER_ITEM = 3000


def _match(rel: str, patterns) -> bool:
    base = rel.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(base, p) for p in patterns)


def is_junk_file(rel: str) -> bool:
    return _match(rel, JUNK_FILES)


def is_secret_file(rel: str) -> bool:
    return _match(rel, SECRET_FILES) and not _match(rel, NOT_SECRET)


_SECRET_ANY = re.compile("|".join(f"(?:{rx.pattern})" for _, rx in SECRET_PATTERNS))


def find_secret_lines(text: str, limit: int = 5) -> list[str]:
    if not _SECRET_ANY.search(text):
        return []
    hits: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for label, rx in SECRET_PATTERNS:
            if rx.search(line):
                hits.append(f"L{lineno}: looks like a {label}")
                break
        if len(hits) >= limit:
            break
    return hits
