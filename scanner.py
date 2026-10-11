"""Build the manifest a host offers: dotfile items + project directory trees.

Every file the host is willing to serve is registered in an allowlist
(`Manifest.files` / `Manifest.repos`) keyed by an opaque id. The host never
serves a path that isn't in the manifest it generated.
"""
from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field

from .skeleton_key import catalog
from .adapters import AdaptContext, adapt, is_text
from .config import HostConfig
from .platforms import Profile, relocate

MANIFEST_VERSION = 1


def _id(*parts: str) -> str:
    return hashlib.sha1("\0".join(parts).encode()).hexdigest()[:16]


@dataclass
class FileEntry:
    id: str
    rel: str  # home-relative on the host
    size: int
    mode: int
    strategy: str  # "copy" | "adapt" | "skip"
    target_rel: str
    text: bool = False
    secret: bool = False
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    link_to: str | None = None  # home-relative symlink target inside a project root


@dataclass
class Item:
    id: str
    label: str
    category: str
    path: str
    kind: str  # "file" | "dir"
    exposed: bool
    default_on: bool
    note: str = ""
    os_only: str | None = None
    files: list[FileEntry] = field(default_factory=list)
    repo: dict | None = None  # {"remote", "branch"} when the dir is itself a git checkout
    link_to: str | None = None


@dataclass
class Repo:
    id: str
    root: str  # home-relative project root
    path: str  # relative to root
    remote: str | None
    branch: str | None
    dirty: int = 0
    unpushed: int | None = None
    overlay: list[FileEntry] = field(default_factory=list)  # uncommitted/untracked files


@dataclass
class ProjectRoot:
    rel: str
    dirs: list[str] = field(default_factory=list)
    repos: list[Repo] = field(default_factory=list)
    loose: list[FileEntry] = field(default_factory=list)


@dataclass
class Manifest:
    host: dict
    target: dict
    items: list[Item]
    projects: list[ProjectRoot]
    version: int = MANIFEST_VERSION
    generated_at: float = field(default_factory=time.time)
    # allowlists (host-only, never serialised to the client)
    files: dict[str, str] = field(default_factory=dict, repr=False)
    repo_paths: dict[str, str] = field(default_factory=dict, repr=False)

    def to_dict(self, exposed_only: bool = True) -> dict:
        items = [i for i in self.items if i.exposed] if exposed_only else self.items
        return {
            "version": self.version,
            "generated_at": self.generated_at,
            "host": self.host,
            "target": self.target,
            "items": [asdict(i) for i in items],
            "projects": [asdict(p) for p in self.projects],
        }


# ---------------------------------------------------------------------------
# classification
# ---------------------------------------------------------------------------
def classify_file(home: str, rel: str, ctx: AdaptContext, *, os_only: str | None = None,
                  adapt_content: bool = True, max_bytes: int = catalog.MAX_DOTFILE_BYTES,
                  project_roots: tuple[str, ...] = ()) -> FileEntry | None:
    """Decide copy / adapt / skip for one home-relative file."""
    path = os.path.join(home, rel)
    try:
        st = os.stat(path)  # follows symlinks
    except OSError:
        return None
    if not stat.S_ISREG(st.st_mode):
        return None
    entry = FileEntry(id=_id("f", rel), rel=rel, size=st.st_size, mode=stat.S_IMODE(st.st_mode),
                      strategy="copy", target_rel=relocate(rel, ctx.src, ctx.dst),
                      secret=catalog.is_secret_file(rel))
    entry.link_to = _link_into_projects(home, rel, project_roots)

    def skip(reason: str) -> FileEntry:
        entry.strategy, entry.reasons = "skip", [reason]
        return entry

    if catalog.is_junk_file(rel):
        return skip("machine state / cache, not configuration")
    if os_only and os_only != ctx.dst.os:
        return skip(f"{os_only}-only config with no {ctx.dst.os} equivalent")
    if ctx.cross_os and ctx.src.os == "macos" and rel.startswith("Library/") and entry.target_rel == rel:
        return skip("macOS Library file with no Linux equivalent")
    if st.st_size > max_bytes:
        return skip(f"too large ({st.st_size // 1024 // 1024} MB)")
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        return skip(f"unreadable: {exc.strerror}")

    entry.text = is_text(data)
    if adapt_content:
        res = adapt(rel, data, ctx)
        entry.target_rel = res.target_rel
        entry.warnings = res.warnings
        if res.changes:
            entry.strategy, entry.reasons = "adapt", res.changes
        else:
            entry.reasons = ["portable as-is"]
    else:
        entry.reasons = ["copied verbatim"]
    if entry.text and not entry.secret:
        entry.warnings += catalog.find_secret_lines(data.decode("utf-8"))
    if entry.secret:
        entry.warnings.insert(0, "secret material — off by default")
    return entry


def _link_into_projects(home: str, rel: str, roots: tuple[str, ...]) -> str | None:
    """If ~/rel is a symlink (e.g. GNU stow) into a project root, return the home-relative target."""
    path = os.path.join(home, rel)
    if not os.path.islink(path):
        return None
    target = os.path.realpath(path)
    for root in roots:
        base = os.path.realpath(os.path.join(home, root))
        if target.startswith(base + os.sep):
            return root + "/" + os.path.relpath(target, base).replace(os.sep, "/")
    return None


# ---------------------------------------------------------------------------
# dotfiles
# ---------------------------------------------------------------------------
def _walk_files(base: str) -> list[str]:
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in catalog.JUNK_DIRS)
        for f in sorted(filenames):
            out.append(os.path.join(dirpath, f))
            if len(out) >= catalog.MAX_FILES_PER_ITEM:
                return out
    return out


def _git(path: str, *args: str, strip: bool = True) -> str | None:
    try:
        r = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip() if strip else r.stdout


def _remote(path: str) -> str | None:
    url = _git(path, "remote", "get-url", "origin")
    if url:
        return url
    names = (_git(path, "remote") or "").split()
    return _git(path, "remote", "get-url", names[0]) if names else None


def scan_dotfiles(home: str, cfg: HostConfig, ctx: AdaptContext) -> list[Item]:
    entries: list[catalog.CatalogEntry] = list(catalog.CATALOG)
    known = {e.path for e in entries}
    for p in cfg.extra_paths:
        if p not in known:
            entries.append(catalog.CatalogEntry(p, p, "custom"))
            known.add(p)
    entries += _discover_loose_dotfiles(home, known)

    roots = tuple(cfg.project_roots)
    claimed: set[str] = set()
    items: list[Item] = []
    # most specific paths first so ".ssh/config" wins over ".ssh"
    for entry in sorted(entries, key=lambda e: -e.path.count("/")):
        path = os.path.join(home, entry.path)
        if not os.path.exists(path):
            continue
        is_dir = os.path.isdir(path)
        exposed = cfg.exposure.get(entry.path, entry.default_on and entry.category != "discovered")
        item = Item(id=_id("i", entry.path), label=entry.label, category=entry.category, path=entry.path,
                    kind="dir" if is_dir else "file", exposed=exposed, default_on=entry.default_on,
                    note=entry.note, os_only=entry.os_only,
                    link_to=_link_into_projects(home, entry.path, roots))
        abs_files = _walk_files(path) if is_dir else [path]
        for abs_path in abs_files:
            rel = os.path.relpath(abs_path, home).replace(os.sep, "/")
            if rel in claimed:
                continue
            fe = classify_file(home, rel, ctx, os_only=entry.os_only, project_roots=roots)
            if fe:
                claimed.add(rel)
                item.files.append(fe)
        if is_dir and os.path.exists(os.path.join(path, ".git")):
            remote = _remote(path)
            if remote:
                item.repo = {"remote": remote, "branch": _git(path, "symbolic-ref", "--short", "-q", "HEAD")}
        if item.files:
            items.append(item)
    order = {c: i for i, c in enumerate(
        ["shell", "editor", "terminal", "git", "tools", "ssh", "cloud", "desktop", "custom", "discovered"])}
    items.sort(key=lambda i: (order.get(i.category, 99), i.path))
    return items


def _discover_loose_dotfiles(home: str, known: set[str]) -> list[catalog.CatalogEntry]:
    """Top-level ~/.something text files we don't know about: offered, never exposed by default."""
    found = []
    try:
        names = sorted(os.listdir(home))
    except OSError:
        return found
    for name in names:
        if not name.startswith(".") or name in known or catalog.is_junk_file(name) or catalog.is_secret_file(name):
            continue
        path = os.path.join(home, name)
        try:
            if not os.path.isfile(path) or os.path.getsize(path) > 256 * 1024:
                continue
            with open(path, "rb") as fh:
                if not is_text(fh.read(8192)):
                    continue
        except OSError:
            continue
        found.append(catalog.CatalogEntry(name, name, "discovered", default_on=False))
    return found


# ---------------------------------------------------------------------------
# project trees
# ---------------------------------------------------------------------------
def _repo_info(home: str, root: str, repo_rel: str, ctx: AdaptContext) -> Repo:
    abs_path = os.path.join(home, root, repo_rel)
    repo = Repo(id=_id("r", root, repo_rel), root=root, path=repo_rel, remote=_remote(abs_path),
                branch=_git(abs_path, "symbolic-ref", "--short", "-q", "HEAD"))
    status = _git(abs_path, "status", "--porcelain=v1", "-z", "--untracked-files=all", strip=False) or ""
    parts = status.split("\0")
    i = 0
    while i < len(parts):
        rec = parts[i]
        i += 1
        if len(rec) < 4:
            continue
        code, rel = rec[:2], rec[3:]
        if "R" in code or "C" in code:
            i += 1  # skip rename source
        repo.dirty += 1
        if "D" in code or len(repo.overlay) >= 500 or any(s in catalog.JUNK_DIRS for s in rel.split("/")):
            continue
        home_rel = f"{root}/{repo_rel}/{rel}" if repo_rel != "." else f"{root}/{rel}"
        fe = classify_file(home, home_rel, ctx, adapt_content=False,
                           max_bytes=catalog.MAX_LOOSE_PROJECT_FILE_BYTES)
        if fe:
            repo.overlay.append(fe)
    ahead = _git(abs_path, "rev-list", "--count", "@{upstream}..HEAD")
    repo.unpushed = int(ahead) if ahead and ahead.isdigit() else None
    return repo


def scan_projects(home: str, roots: list[str], ctx: AdaptContext) -> list[ProjectRoot]:
    results: list[ProjectRoot] = []
    for root in roots:
        base = os.path.join(home, root)
        if not os.path.isdir(base):
            continue
        pr = ProjectRoot(rel=root)
        repo_rels: list[str] = []
        for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
            rel_dir = os.path.relpath(dirpath, base).replace(os.sep, "/")
            if ".git" in dirnames or ".git" in filenames:
                repo_rels.append(rel_dir)
                dirnames[:] = []
                continue
            dirnames[:] = sorted(d for d in dirnames if d not in catalog.JUNK_DIRS)
            if rel_dir != ".":
                pr.dirs.append(rel_dir)
            for f in sorted(filenames):
                home_rel = f"{root}/{f}" if rel_dir == "." else f"{root}/{rel_dir}/{f}"
                fe = classify_file(home, home_rel, ctx, max_bytes=catalog.MAX_LOOSE_PROJECT_FILE_BYTES)
                if fe:
                    pr.loose.append(fe)
        with ThreadPoolExecutor(max_workers=8) as pool:
            pr.repos = list(pool.map(lambda r: _repo_info(home, root, r, ctx), repo_rels))
        results.append(pr)
    return results


# ---------------------------------------------------------------------------
def build_manifest(home: str, cfg: HostConfig, src: Profile, dst: Profile) -> Manifest:
    ctx = AdaptContext(src=src, dst=dst)
    items = scan_dotfiles(home, cfg, ctx)
    projects = scan_projects(home, cfg.project_roots, ctx)
    m = Manifest(host=src.to_dict(), target=dst.to_dict(), items=items, projects=projects)
    for item in items:
        if item.exposed:
            for fe in item.files:
                if fe.strategy != "skip":
                    m.files[fe.id] = os.path.join(home, fe.rel)
    for pr in projects:
        for fe in pr.loose:
            if fe.strategy != "skip":
                m.files[fe.id] = os.path.join(home, fe.rel)
        for repo in pr.repos:
            m.repo_paths[repo.id] = os.path.join(home, pr.rel, repo.path)
            for fe in repo.overlay:
                if fe.strategy != "skip":
                    m.files[fe.id] = os.path.join(home, fe.rel)
    return m
