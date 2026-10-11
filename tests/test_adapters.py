import pytest
from skeleton_key.adapters import AdaptContext, adapt, compute_diff, is_text
from skeleton_key.platforms import Profile


def test_is_text():
    assert is_text(b"Hello world\nexport PATH=/usr/bin")
    assert not is_text(b"\x00\x01\x02\x03\x04")


def test_adapt_home_and_brew_path():
    src = Profile("linux", "x86_64", "/home/john", "john", "devbox")
    dst = Profile("macos", "arm64", "/Users/john", "john", "macbook")
    ctx = AdaptContext(src=src, dst=dst)

    zshrc_content = (
        'export PATH="/home/john/.local/bin:$PATH"\n'
        'export BREW="/home/linuxbrew/.linuxbrew/bin"\n'
        'alias copy="xclip -selection clipboard"\n'
        'alias paste="xclip -selection clipboard -o"\n'
        'alias browser="xdg-open"\n'
    ).encode("utf-8")

    res = adapt(".zshrc", zshrc_content, ctx)
    assert res.text is True
    assert res.target_rel == ".zshrc"
    assert len(res.changes) > 0

    text = res.data.decode("utf-8")
    assert "/Users/john/.local/bin" in text
    assert "/opt/homebrew/bin" in text
    assert "alias copy=pbcopy" in text or "pbcopy" in text
    assert "alias paste=pbpaste" in text or "pbpaste" in text
    assert "alias browser=open" in text or "open" in text


def test_adapt_project_root_remap():
    src = Profile("linux", "x86_64", "/home/john", "john", "devbox")
    dst = Profile("macos", "arm64", "/Users/john", "john", "macbook")
    ctx = AdaptContext(src=src, dst=dst, root_map={"Documents/github": "Developer"})

    content = b'alias myrepo="cd /home/john/Documents/github/myrepo"\n'
    res = adapt(".zshrc", content, ctx)
    text = res.data.decode("utf-8")
    assert "/Users/john/Developer/myrepo" in text


def test_adapt_advisory_warnings():
    src = Profile("linux", "x86_64", "/home/john", "john", "devbox")
    dst = Profile("macos", "arm64", "/Users/john", "john", "macbook")
    ctx = AdaptContext(src=src, dst=dst)

    content = (
        'sudo apt update && sudo apt install ripgrep\n'
        'systemctl --user restart mydaemon\n'
        'export NVM_DIR="$HOME/.nvm"\n'
        'export PATH="/home/john/.nvm/versions/node/v20.0.0/bin:$PATH"\n'
    ).encode("utf-8")

    res = adapt(".bashrc", content, ctx)
    assert any("apt" in w for w in res.warnings)
    assert any("systemd" in w or "systemctl" in w for w in res.warnings)
    assert any("v20.0.0" in w for w in res.warnings)


def test_compute_diff():
    diff = compute_diff("old line\ncommon\n", "new line\ncommon\n")
    assert "-old line" in diff
    assert "+new line" in diff
