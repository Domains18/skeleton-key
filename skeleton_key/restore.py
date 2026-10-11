"""Client-side restore engine: recreates directory structure, clones repos,
applies dotfiles (copy direct or adapt), creates backups, and reports warnings.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Callable

from .adapters import AdaptContext, adapt
from .client import HostConnection
from .platforms import Profile


@dataclass
class RestorePlan:
    item_ids: set[str] = field(default_factory=set)
    repo_ids: set[str] = field(default_factory=set)
    include_loose: bool = True
    include_overlays: bool = True
    root_map: dict[str, str] = field(default_factory=dict)  # host root -> target root
    recreate_symlinks: bool = True
    dry_run: bool = False


@dataclass
class FileResult:
    rel: str
    target_rel: str
    action: str  # "copied", "adapted", "skipped", "backed_up", "error"
    size: int
    changes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    backup_path: str | None = None
    error: str | None = None


@dataclass
class RepoResult:
    path: str
    remote: str | None
    branch: str | None
    action: str  # "cloned", "bundled", "skipped_existing", "error"
    overlays_applied: int = 0
    error: str | None = None


@dataclass
class RestoreReport:
    dirs_created: list[str] = field(default_factory=list)
    files: list[FileResult] = field(default_factory=list)
    repos: list[RepoResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration: float = 0.0

    @property
    def copied_count(self) -> int:
        return sum(1 for f in self.files if f.action == "copied")

    @property
    def adapted_count(self) -> int:
        return sum(1 for f in self.files if f.action == "adapted")

    @property
    def skipped_count(self) -> int:
        return sum(1 for f in self.files if f.action == "skipped")


def _backup_file(path: str) -> str:
    """Create a timestamped backup of an existing file."""
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup = f"{path}.sk_backup_{ts}"
    shutil.copy2(path, backup)
    return backup


class Restorer:
    def __init__(
        self,
        conn: HostConnection,
        manifest: dict,
        target_profile: Profile,
        plan: RestorePlan | None = None,
        on_progress: Callable[[str, float], None] | None = None,
    ):
        self.conn = conn
        self.manifest = manifest
        self.target = target_profile
        self.src = Profile.from_dict(manifest["host"])
        self.plan = plan or RestorePlan()
        self.on_progress = on_progress
        self.ctx = AdaptContext(
            src=self.src,
            dst=self.target,
            root_map=self.plan.root_map,
        )

    def _progress(self, msg: str, frac: float = 0.0) -> None:
        if self.on_progress:
            self.on_progress(msg, frac)

    def run(self) -> RestoreReport:
        start_time = time.time()
        report = RestoreReport()
        home = self.target.home

        # 1. Collect items to restore
        all_items = self.manifest.get("items", [])
        if self.plan.item_ids:
            items_to_restore = [i for i in all_items if i["id"] in self.plan.item_ids]
        else:
            # Default to all exposed items
            items_to_restore = [i for i in all_items if i.get("exposed", False)]

        # Collect total file steps for progress calculation
        total_dotfiles = sum(len(i.get("files", [])) for i in items_to_restore)
        projects = self.manifest.get("projects", [])
        total_steps = max(1, total_dotfiles + len(projects))
        current_step = 0

        # 2. Process Dotfiles
        for item in items_to_restore:
            if item.get("note"):
                report.warnings.append(f"{item['label']}: {item['note']}")

            for fe in item.get("files", []):
                current_step += 1
                self._progress(f"Dotfile: {fe['rel']}", current_step / total_steps)

                if fe.get("strategy") == "skip":
                    report.files.append(
                        FileResult(
                            rel=fe["rel"],
                            target_rel=fe.get("target_rel", fe["rel"]),
                            action="skipped",
                            size=fe.get("size", 0),
                            changes=[],
                            warnings=fe.get("warnings", []),
                        )
                    )
                    continue

                if self.plan.dry_run:
                    action = "adapted" if fe.get("strategy") == "adapt" else "copied"
                    report.files.append(
                        FileResult(
                            rel=fe["rel"],
                            target_rel=fe.get("target_rel", fe["rel"]),
                            action=action,
                            size=fe.get("size", 0),
                            changes=fe.get("reasons", []),
                            warnings=fe.get("warnings", []),
                        )
                    )
                    continue

                # Fetch bytes from host
                try:
                    data, mode = self.conn.fetch(fe["id"])
                except Exception as exc:
                    err_msg = f"Failed to fetch {fe['rel']}: {exc}"
                    report.errors.append(err_msg)
                    report.files.append(
                        FileResult(
                            rel=fe["rel"],
                            target_rel=fe.get("target_rel", fe["rel"]),
                            action="error",
                            size=fe.get("size", 0),
                            error=str(exc),
                        )
                    )
                    continue

                # Determine target destination path on new system
                target_rel = fe.get("target_rel", fe["rel"])
                dest_path = os.path.join(home, target_rel)

                # Adaptation check
                changes = []
                warnings = list(fe.get("warnings", []))
                action = "copied"

                if fe.get("strategy") == "adapt" or fe.get("text", False):
                    res = adapt(fe["rel"], data, self.ctx)
                    data = res.data
                    dest_path = os.path.join(home, res.target_rel)
                    target_rel = res.target_rel
                    changes = res.changes
                    warnings = list(set(warnings + res.warnings))
                    if changes:
                        action = "adapted"

                # Check if file exists -> create backup
                backup_path = None
                if os.path.exists(dest_path):
                    try:
                        backup_path = _backup_file(dest_path)
                    except OSError as exc:
                        report.warnings.append(f"Could not backup {dest_path}: {exc}")

                # Write file
                try:
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    with open(dest_path, "wb") as f:
                        f.write(data)
                    if mode is not None:
                        os.chmod(dest_path, mode)
                except OSError as exc:
                    err_msg = f"Failed to write {dest_path}: {exc}"
                    report.errors.append(err_msg)
                    report.files.append(
                        FileResult(
                            rel=fe["rel"],
                            target_rel=target_rel,
                            action="error",
                            size=len(data),
                            error=str(exc),
                        )
                    )
                    continue

                report.files.append(
                    FileResult(
                        rel=fe["rel"],
                        target_rel=target_rel,
                        action=action,
                        size=len(data),
                        changes=changes,
                        warnings=warnings,
                        backup_path=backup_path,
                    )
                )

        # 3. Process Project Structure & Repositories
        for pr in projects:
            src_root = pr["rel"]
            dst_root = self.plan.root_map.get(src_root, src_root)
            abs_root = os.path.join(home, dst_root)

            # Recreate project directory structure
            for d in pr.get("dirs", []):
                dir_path = os.path.join(abs_root, d)
                if not self.plan.dry_run and not os.path.exists(dir_path):
                    try:
                        os.makedirs(dir_path, exist_ok=True)
                        report.dirs_created.append(os.path.relpath(dir_path, home))
                    except OSError as exc:
                        report.errors.append(f"Could not create directory {dir_path}: {exc}")
                else:
                    report.dirs_created.append(os.path.relpath(dir_path, home))

            # Process Git Repositories
            for repo in pr.get("repos", []):
                if self.plan.repo_ids and repo["id"] not in self.plan.repo_ids:
                    continue

                repo_dst = os.path.join(abs_root, repo["path"])
                current_step += 1
                self._progress(f"Repo: {repo['path']}", current_step / total_steps)

                if self.plan.dry_run:
                    report.repos.append(
                        RepoResult(
                            path=repo["path"],
                            remote=repo.get("remote"),
                            branch=repo.get("branch"),
                            action="cloned" if repo.get("remote") else "bundled",
                        )
                    )
                    continue

                if os.path.exists(repo_dst):
                    report.repos.append(
                        RepoResult(
                            path=repo["path"],
                            remote=repo.get("remote"),
                            branch=repo.get("branch"),
                            action="skipped_existing",
                        )
                    )
                else:
                    # Clone repository
                    os.makedirs(os.path.dirname(repo_dst), exist_ok=True)
                    cloned_ok = False
                    action = "cloned"

                    if repo.get("remote"):
                        try:
                            cmd = ["git", "clone", repo["remote"], repo_dst]
                            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                            if r.returncode == 0:
                                cloned_ok = True
                                if repo.get("branch"):
                                    subprocess.run(
                                        ["git", "-C", repo_dst, "checkout", repo["branch"]],
                                        capture_output=True,
                                        text=True,
                                    )
                            else:
                                report.warnings.append(
                                    f"git clone failed for {repo['path']} ({r.stderr.strip()[:100]}); attempting git bundle..."
                                )
                        except Exception as exc:
                            report.warnings.append(f"git clone exception for {repo['path']}: {exc}")

                    if not cloned_ok:
                        # Fallback to git bundle from host
                        bundle_tmp = f"{repo_dst}.bundle"
                        try:
                            self.conn.fetch_bundle(repo["id"], bundle_tmp)
                            cmd = ["git", "clone", bundle_tmp, repo_dst]
                            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                            if r.returncode == 0:
                                cloned_ok = True
                                action = "bundled"
                                if repo.get("remote"):
                                    # Restore the origin remote URL
                                    subprocess.run(
                                        ["git", "-C", repo_dst, "remote", "set-url", "origin", repo["remote"]],
                                        capture_output=True,
                                    )
                                if repo.get("branch"):
                                    subprocess.run(
                                        ["git", "-C", repo_dst, "checkout", repo["branch"]],
                                        capture_output=True,
                                    )
                            else:
                                report.errors.append(f"Failed to clone bundle for {repo['path']}: {r.stderr.strip()}")
                        except Exception as exc:
                            report.errors.append(f"Bundle transfer failed for {repo['path']}: {exc}")
                        finally:
                            if os.path.exists(bundle_tmp):
                                os.remove(bundle_tmp)

                    overlays_count = 0
                    if cloned_ok and self.plan.include_overlays:
                        # Apply uncommitted / untracked files
                        for ov in repo.get("overlay", []):
                            try:
                                o_data, o_mode = self.conn.fetch(ov["id"])
                                o_target_rel = ov.get("target_rel", ov["rel"])
                                # Map relative to target root if root was remapped
                                if src_root in self.plan.root_map:
                                    s = src_root.strip("/")
                                    d = self.plan.root_map[src_root].strip("/")
                                    if o_target_rel.startswith(s + "/"):
                                        o_target_rel = d + o_target_rel[len(s):]
                                o_path = os.path.join(home, o_target_rel)
                                os.makedirs(os.path.dirname(o_path), exist_ok=True)
                                with open(o_path, "wb") as f:
                                    f.write(o_data)
                                if o_mode is not None:
                                    os.chmod(o_path, o_mode)
                                overlays_count += 1
                            except Exception as exc:
                                report.warnings.append(f"Could not apply overlay {ov['rel']}: {exc}")

                    report.repos.append(
                        RepoResult(
                            path=repo["path"],
                            remote=repo.get("remote"),
                            branch=repo.get("branch"),
                            action=action if cloned_ok else "error",
                            overlays_applied=overlays_count,
                            error=None if cloned_ok else "Clone and bundle both failed",
                        )
                    )

            # Process loose files in project roots
            if self.plan.include_loose:
                for fe in pr.get("loose", []):
                    if fe.get("strategy") == "skip":
                        continue
                    if self.plan.dry_run:
                        report.files.append(
                            FileResult(
                                rel=fe["rel"],
                                target_rel=fe.get("target_rel", fe["rel"]),
                                action="copied",
                                size=fe.get("size", 0),
                            )
                        )
                        continue

                    try:
                        data, mode = self.conn.fetch(fe["id"])
                        target_rel = fe.get("target_rel", fe["rel"])
                        if src_root in self.plan.root_map:
                            s = src_root.strip("/")
                            d = self.plan.root_map[src_root].strip("/")
                            if target_rel.startswith(s + "/"):
                                target_rel = d + target_rel[len(s):]
                        dest_path = os.path.join(home, target_rel)
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                        with open(dest_path, "wb") as f:
                            f.write(data)
                        if mode is not None:
                            os.chmod(dest_path, mode)
                        report.files.append(
                            FileResult(
                                rel=fe["rel"],
                                target_rel=target_rel,
                                action="copied",
                                size=len(data),
                            )
                        )
                    except Exception as exc:
                        report.errors.append(f"Could not transfer loose file {fe['rel']}: {exc}")

        # 4. Optional symlink restoration (e.g. GNU stow setups)
        if self.plan.recreate_symlinks and not self.plan.dry_run:
            for item in items_to_restore:
                link_to = item.get("link_to")
                if link_to:
                    # item was a symlink to link_to inside a project root
                    src_link_target = os.path.join(home, link_to)
                    dest_link = os.path.join(home, item["path"])
                    if os.path.exists(src_link_target) and not os.path.islink(dest_link):
                        try:
                            # If dest_link is a normal file we just wrote, replace with symlink
                            os.remove(dest_link)
                            os.symlink(src_link_target, dest_link)
                            report.warnings.append(f"Restored symlink {item['path']} -> {link_to}")
                        except OSError as exc:
                            report.warnings.append(f"Could not link {dest_link} to {src_link_target}: {exc}")

        report.duration = time.time() - start_time
        self._progress("Restore complete!", 1.0)
        return report
