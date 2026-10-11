"""Content/location adaptation for moving a config file between machines.

`adapt()` is a pure function: (home-relative path, bytes, context) -> AdaptResult.
A file "needs adaptation" exactly when adapt() changes its bytes or location,
so classification and the real transform can never disagree.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .platforms import LINUX_TO_MAC_LOCATIONS, MAC_TO_LINUX_LOCATIONS, Profile, relocate

_TEXT_SNIFF = 8192


def is_text(data: bytes) -> bool:
    if b"\0" in data[:_TEXT_SNIFF]:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


@dataclass
class AdaptContext:
    src: Profile
    dst: Profile
    # home-relative source project root -> home-relative target root
    root_map: dict[str, str] = field(default_factory=dict)

    @property
    def cross_os(self) -> bool:
        return self.src.os != self.dst.os

    def path_pairs(self) -> list[tuple[str, str, str]]:
        """(old, new, label) prefixes to rewrite, longest first."""
        pairs: list[tuple[str, str, str]] = []
        sh, dh = self.src.home, self.dst.home

        def add_rel(s: str, d: str, label: str) -> None:
            pairs.append((f"{sh}/{s}", f"{dh}/{d}", label))
            if s != d:  # home-relative spellings only matter when the tail changes
                for pre in ("~/", "$HOME/", "${HOME}/"):
                    pairs.append((pre + s, pre + d, label))

        for s, d in self.root_map.items():
            add_rel(s.strip("/"), d.strip("/"), "project root")
        if self.cross_os:
            table = LINUX_TO_MAC_LOCATIONS if self.src.os == "linux" else MAC_TO_LINUX_LOCATIONS
            for s, d in table.items():
                if s != d:
                    add_rel(s, d, "OS config location")
        if self.src.brew_prefix != self.dst.brew_prefix:
            pairs.append((self.src.brew_prefix, self.dst.brew_prefix, "Homebrew prefix"))
        if sh != dh:
            pairs.append((sh, dh, "home directory"))
        # de-dup, longest first so specific prefixes win in the alternation
        seen: dict[str, tuple[str, str, str]] = {}
        for p in pairs:
            seen.setdefault(p[0], p)
        return sorted(seen.values(), key=lambda p: -len(p[0]))


@dataclass
class AdaptResult:
    source_rel: str
    target_rel: str
    data: bytes
    text: bool
    changes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def relocated(self) -> bool:
        return self.source_rel != self.target_rel


# ---------------------------------------------------------------------------
# path rewriting
# ---------------------------------------------------------------------------
_BOUNDARY_AFTER = r"(?=[/\"'\s:;)}\]`,=]|$)"
_BOUNDARY_BEFORE = r"(?<![\w.\-/~$])"


def rewrite_paths(text: str, ctx: AdaptContext) -> tuple[str, list[str]]:
    pairs = ctx.path_pairs()
    if not pairs:
        return text, []
    lookup = {old: (new, label) for old, new, label in pairs}
    rx = re.compile(
        _BOUNDARY_BEFORE + "(" + "|".join(re.escape(o) for o, _, _ in pairs) + ")" + _BOUNDARY_AFTER,
        re.M,
    )
    counts: dict[tuple[str, str, str], int] = {}

    def sub(m: re.Match) -> str:
        new, label = lookup[m.group(1)]
        key = (label, m.group(1), new)
        counts[key] = counts.get(key, 0) + 1
        return new

    out = rx.sub(sub, text)
    changes = [f"{label}: {old} → {new} (×{n})" for (label, old, new), n in counts.items()]
    return out, changes


# ---------------------------------------------------------------------------
# command/tool rewriting (cross-OS only)
# ---------------------------------------------------------------------------
_XCLIP = re.compile(
    r"\bxclip((?:\s+-(?:selection|sel)\s+(?:clipboard|clip|c|primary|p|secondary|s)\b|\s+-(?:o|out|i|in)\b)+)"
)
_XSEL = re.compile(r"\bxsel((?:\s+(?:--clipboard|--output|--input|-[bio]{1,2})\b)+)")
_ZSH_PLUGINS = re.compile(
    r"/usr/share/(zsh-autosuggestions|zsh-syntax-highlighting|zsh-history-substring-search|"
    r"zsh-theme-powerlevel10k|powerlevel10k)(?=/)"
)
_FZF_SHELL = re.compile(r"/usr/share/(?:doc/fzf/examples|fzf(?:/shell)?)/(key-bindings|completion)\.(zsh|bash|fish)")
_GIT_LIBSECRET = re.compile(r"(helper\s*=\s*)\S*libsecret\S*")


def _l2m_commands(text: str, ctx: AdaptContext) -> tuple[str, list[str]]:
    changes: list[str] = []
    brew = ctx.dst.brew_prefix

    def count_sub(rx, repl, s, label):
        new, n = rx.subn(repl, s)
        if n:
            changes.append(f"{label} (×{n})")
        return new

    def xclip_repl(m: re.Match) -> str:
        return "pbpaste" if re.search(r"-(?:o|out)\b", m.group(1)) else "pbcopy"

    def xsel_repl(m: re.Match) -> str:
        flags = m.group(1)
        return "pbpaste" if ("--output" in flags or re.search(r"-[bi]*o", flags)) else "pbcopy"

    text = count_sub(_XCLIP, xclip_repl, text, "clipboard: xclip → pbcopy/pbpaste")
    text = count_sub(_XSEL, xsel_repl, text, "clipboard: xsel → pbcopy/pbpaste")
    text = count_sub(re.compile(r"\bwl-copy\b"), "pbcopy", text, "clipboard: wl-copy → pbcopy")
    text = count_sub(re.compile(r"\bwl-paste\b"), "pbpaste", text, "clipboard: wl-paste → pbpaste")
    text = count_sub(re.compile(r"\bxdg-open\b"), "open", text, "xdg-open → open")

    def plugin_repl(m: re.Match) -> str:
        name = "powerlevel10k" if "powerlevel10k" in m.group(1) else m.group(1)
        return f"{brew}/share/{name}"

    text = count_sub(_ZSH_PLUGINS, plugin_repl, text, f"zsh plugin path: /usr/share → {brew}/share (brew install the plugin)")
    text = count_sub(_FZF_SHELL, lambda m: f"{brew}/opt/fzf/shell/{m.group(1)}.{m.group(2)}", text,
                     "fzf shell integration → Homebrew path")
    text = count_sub(_GIT_LIBSECRET, r"\1osxkeychain", text, "git credential helper: libsecret → osxkeychain")
    return text, changes


def _m2l_commands(text: str, ctx: AdaptContext) -> tuple[str, list[str]]:
    changes: list[str] = []
    for rx, repl, label in (
        (re.compile(r"\bpbcopy\b"), "xclip -selection clipboard", "clipboard: pbcopy → xclip"),
        (re.compile(r"\bpbpaste\b"), "xclip -selection clipboard -o", "clipboard: pbpaste → xclip -o"),
    ):
        text, n = rx.subn(repl, text)
        if n:
            changes.append(f"{label} (×{n})")
    return text, changes


# ---------------------------------------------------------------------------
# advisory warnings (no rewrite possible / safe)
# ---------------------------------------------------------------------------
_ANY_WARN = (
    (re.compile(r"\.nvm/versions/node/(v[\d.]+)"), "pins Node {0} via nvm — run `nvm install {0}` on the new machine"),
)
_L2M_WARN = (
    (re.compile(r"\b(apt|apt-get|dnf|yum|pacman|zypper|snap|flatpak)\s"), "uses Linux package manager `{0}` — use Homebrew on macOS"),
    (re.compile(r"\b(systemctl|journalctl)\b"), "`{0}` (systemd) doesn't exist on macOS — use launchctl / `brew services`"),
    (re.compile(r"\bsed\s+-i(?!\s*(?:''|\"\"))\s"), "GNU `sed -i`; BSD sed needs `sed -i ''` (or `brew install gnu-sed`)"),
    (re.compile(r"(linux[-_](?:x86_64|amd64|x64|arm64|aarch64)|x86_64[-_](?:unknown[-_])?linux)"),
     "Linux-specific binary path (`{0}`) — install the macOS build (e.g. via brew) and fix this line"),
    (re.compile(r"\b(notify-send|gsettings|dconf|nautilus|gnome-[\w-]+)\b"), "`{0}` is Linux-desktop specific"),
    (re.compile(r"(/usr/(?:share|lib)/[\w.+-]+)"), "references Linux system path `{0}` — verify it exists on macOS"),
)
_M2L_WARN = (
    (re.compile(r"\b(defaults write|osascript|launchctl|mdfind|caffeinate)\b"), "`{0}` is macOS-only"),
    (re.compile(r"(/Applications/[^\s\"']+)"), "macOS app path `{0}`"),
    (re.compile(r"\b(osxkeychain|UseKeychain)\b"), "`{0}` is macOS keychain specific"),
)


_COMBINED: dict[tuple, re.Pattern] = {}


def _any_match(rules, text: str) -> bool:
    key = tuple(id(rx) for rx, _ in rules)
    rx = _COMBINED.get(key)
    if rx is None:
        rx = _COMBINED[key] = re.compile("|".join(f"(?:{r.pattern})" for r, _ in rules))
    return rx.search(text) is not None


def _warnings(text: str, ctx: AdaptContext) -> list[str]:
    rules = list(_ANY_WARN)
    if ctx.cross_os:
        rules += list(_L2M_WARN if ctx.src.os == "linux" else _M2L_WARN)
    if not _any_match(rules, text):
        return []
    out: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.lstrip()
        if not stripped:
            continue
        for rx, msg in rules:
            m = rx.search(line)
            if m:
                out.append(f"L{lineno}: " + msg.format(*(m.groups() or (m.group(0),))))
                break
    return out


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------
def adapt(rel: str, data: bytes, ctx: AdaptContext) -> AdaptResult:
    target_rel = relocate(rel, ctx.src, ctx.dst)
    for s, d in ctx.root_map.items():
        s, d = s.strip("/"), d.strip("/")
        if rel == s or rel.startswith(s + "/"):
            target_rel = d + rel[len(s):]
            break
    result = AdaptResult(source_rel=rel, target_rel=target_rel, data=data, text=is_text(data))
    if result.relocated:
        result.changes.append(f"location: ~/{rel} → ~/{target_rel}")
    if not result.text:
        return result

    text = data.decode("utf-8")
    new, changes = rewrite_paths(text, ctx)
    result.changes += changes
    if ctx.cross_os:
        fn = _l2m_commands if ctx.src.os == "linux" else _m2l_commands
        new, changes = fn(new, ctx)
        result.changes += changes
    result.warnings = _warnings(new, ctx)
    if new != text:
        result.data = new.encode("utf-8")
    return result
