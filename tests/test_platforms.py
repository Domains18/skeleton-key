import pytest
from skeleton_key.platforms import (
    Profile,
    detect,
    relocate,
    default_home_for,
    LINUX_TO_MAC_LOCATIONS,
    MAC_TO_LINUX_LOCATIONS,
)


def test_profile_creation_and_dict():
    p = Profile(os="linux", arch="x86_64", home="/home/testuser", user="testuser", hostname="box")
    assert p.brew_prefix == "/home/linuxbrew/.linuxbrew"
    d = p.to_dict()
    assert d["os"] == "linux"
    assert d["user"] == "testuser"

    p2 = Profile.from_dict(d)
    assert p2 == p


def test_profile_mac_arm():
    p = Profile(os="macos", arch="arm64", home="/Users/testuser", user="testuser", hostname="macbook")
    assert p.brew_prefix == "/opt/homebrew"


def test_unsupported_os():
    with pytest.raises(ValueError, match="Unsupported OS"):
        Profile.from_dict({"os": "windows", "home": "C:\\", "user": "win", "hostname": "winbox"})


def test_relocate_linux_to_mac():
    src = Profile("linux", "x86_64", "/home/alpha", "alpha", "pop")
    dst = Profile("macos", "arm64", "/Users/alpha", "alpha", "mbp")

    # VS Code settings should relocate to Library/Application Support
    assert relocate(".config/Code/User/settings.json", src, dst) == "Library/Application Support/Code/User/settings.json"
    # Neovim should stay ~/.config/nvim on both
    assert relocate(".config/nvim/init.lua", src, dst) == ".config/nvim/init.lua"
    # pnpm store
    assert relocate(".local/share/pnpm/store", src, dst) == "Library/pnpm/store"


def test_relocate_mac_to_linux():
    src = Profile("macos", "arm64", "/Users/alpha", "alpha", "mbp")
    dst = Profile("linux", "x86_64", "/home/alpha", "alpha", "pop")

    assert relocate("Library/Application Support/Code/User/keybindings.json", src, dst) == ".config/Code/User/keybindings.json"
