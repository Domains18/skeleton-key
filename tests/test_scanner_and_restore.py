import os
import tempfile
import pytest
from skeleton_key.config import HostConfig
from skeleton_key.platforms import Profile
from skeleton_key.restore import RestorePlan, Restorer
from skeleton_key.scanner import build_manifest


class DummyConnection:
    """Mock connection to serve dummy files for unit testing the restorer."""
    def __init__(self, file_map: dict[str, bytes]):
        self.file_map = file_map

    def fetch(self, file_id: str):
        data = self.file_map.get(file_id, b"dummy content")
        return data, 0o644

    def fetch_bundle(self, repo_id: str, dest_path: str):
        pass


def test_scanner_distinguishes_copy_vs_adapt_vs_skip():
    with tempfile.TemporaryDirectory() as fake_home:
        # Create a portable config (copy)
        tmux_conf = os.path.join(fake_home, ".tmux.conf")
        with open(tmux_conf, "w") as f:
            f.write("set -g mouse on\n")

        # Create a config that needs adaptation (adapt)
        zshrc = os.path.join(fake_home, ".zshrc")
        with open(zshrc, "w") as f:
            f.write(f'export PATH="{fake_home}/bin:$PATH"\nalias c="xclip -selection clipboard"\n')

        # Create a junk file (skip)
        ds_store = os.path.join(fake_home, ".DS_Store")
        with open(ds_store, "w") as f:
            f.write("junk")

        src = Profile("linux", "x86_64", fake_home, "testuser", "linuxbox")
        dst = Profile("macos", "arm64", "/Users/testuser", "testuser", "macbook")
        cfg = HostConfig(project_roots=[])

        manifest = build_manifest(fake_home, cfg, src, dst)

        tmux_item = next((i for i in manifest.items if i.path == ".tmux.conf"), None)
        assert tmux_item is not None
        assert tmux_item.files[0].strategy == "copy"

        zshrc_item = next((i for i in manifest.items if i.path == ".zshrc"), None)
        assert zshrc_item is not None
        assert zshrc_item.files[0].strategy == "adapt"
        assert len(zshrc_item.files[0].reasons) > 0


def test_restore_dry_run_and_execution():
    with tempfile.TemporaryDirectory() as host_home, tempfile.TemporaryDirectory() as target_home:
        # Host side setup
        tmux_path = os.path.join(host_home, ".tmux.conf")
        with open(tmux_path, "w") as f:
            f.write("set -g prefix C-a\n")

        zshrc_path = os.path.join(host_home, ".zshrc")
        with open(zshrc_path, "w") as f:
            f.write(f'export MYHOME="{host_home}"\nalias cb="xclip -selection clipboard"\n')

        src = Profile("linux", "x86_64", host_home, "testuser", "linuxbox")
        dst = Profile("macos", "arm64", target_home, "testuser", "macbook")
        cfg = HostConfig(project_roots=[])
        manifest = build_manifest(host_home, cfg, src, dst)

        file_map = {}
        for fid, path in manifest.files.items():
            with open(path, "rb") as fh:
                file_map[fid] = fh.read()

        conn = DummyConnection(file_map)

        # 1. Test Dry Run
        plan_dry = RestorePlan(dry_run=True)
        restorer_dry = Restorer(conn, manifest.to_dict(), dst, plan=plan_dry)
        rep_dry = restorer_dry.run()

        assert rep_dry.copied_count >= 1
        assert rep_dry.adapted_count >= 1
        # No files actually created in target_home during dry-run
        assert not os.path.exists(os.path.join(target_home, ".tmux.conf"))
        assert not os.path.exists(os.path.join(target_home, ".zshrc"))

        # 2. Test Real Execution
        plan_real = RestorePlan(dry_run=False)
        restorer_real = Restorer(conn, manifest.to_dict(), dst, plan=plan_real)
        rep_real = restorer_real.run()

        assert rep_real.copied_count >= 1
        assert rep_real.adapted_count >= 1

        # Check restored files
        target_tmux = os.path.join(target_home, ".tmux.conf")
        target_zshrc = os.path.join(target_home, ".zshrc")
        assert os.path.exists(target_tmux)
        assert os.path.exists(target_zshrc)

        with open(target_zshrc, "r") as f:
            content = f.read()
        # Verify adaptation occurred on target side
        assert target_home in content
        assert "pbcopy" in content
        assert "xclip" not in content

        # 3. Test backup creation when running again
        rep_second = restorer_real.run()
        backed_up = [f for f in rep_second.files if f.backup_path is not None]
        assert len(backed_up) >= 2
        for b in backed_up:
            assert os.path.exists(b.backup_path)
