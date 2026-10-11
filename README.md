# 🗝️ Skeleton Key

> **AirDrop-style environment replicator and cross-platform dotfile adapter for Linux and macOS.**

When moving between machines—especially from a tuned Linux environment to a new MacBook—copying dotfiles verbatim often breaks your setup due to hardcoded home paths, different Homebrew prefixes, Linux-only utilities (`xclip`, `xdg-open`), and diverging application config locations (e.g., `~/.config/Code` vs. `~/Library/Application Support/Code`).

**Skeleton Key** pairs your old and new laptops directly over the local network like AirDrop, categorizes every configuration file into **Direct Copy** vs. **Needs Adaptation**, provides a visual diff preview of all adaptations before import, and clones your project repositories without copying heavy `node_modules` or build artifacts.

---

## ✨ Key Features

- **Direct Copy vs. Adaptation Engine**:
  - **Portable as-is (`DIRECT COPY`)**: Configurations that follow standard specifications across platforms (e.g., Neovim `~/.config/nvim`, tmux `~/.tmux.conf`, WezTerm, Starship, Git, etc.).
  - **Adapted (`NEEDS ADAPTATION`)**: Automatically adapts path prefixes (`/home/user` $\to$ `/Users/user`), Homebrew paths (`/home/linuxbrew/.linuxbrew` $\to$ `/opt/homebrew`), clipboard tools (`xclip`/`xsel`/`wl-copy` $\to$ `pbcopy`/`pbpaste`), desktop openers (`xdg-open` $\to$ `open`), and macOS application paths (e.g., VS Code settings moving to `~/Library/Application Support/Code/User`).
  - **Skipped (`SKIPPED`)**: Filters out machine cache, socket files, history buffers, and platform-exclusive window managers (e.g., i3, sway, hyprland).
- **Project Structure & Git Replication**:
  - Recreates directory hierarchies (e.g., `~/Documents/github`).
  - Clones Git repositories from their remote URLs with branch checkouts rather than transferring bloated `node_modules` or `.venv` directories.
  - Automatically transfers uncommitted/untracked overlay files and local bundles for repos without remotes.
- **AirDrop-Style Discovery & PIN Pairing**:
  - mDNS/Bonjour discovery (`_skeletonkey._tcp.local.`) automatically detects devices on the LAN.
  - 6-digit PIN pairing ensures only intended machines connect.
  - **Short Authentication String (SAS)** visual fingerprint displayed on both screens to verify the connection against MITM attacks.
- **End-to-End Encryption**:
  - Ephemeral X25519 elliptic-curve Diffie-Hellman key exchange.
  - HKDF-SHA256 session key derivation tied to transcript and PIN.
  - AES-256-GCM encryption with direction-specific keys and replay-protected counter nonces.
  - Strict allowlist: the client only requests opaque manifest IDs; arbitrary file paths cannot cross the wire.
- **Interactive Local Web UI**:
  - Lightweight Flask UI running strictly on `127.0.0.1` (not an exposed public HTTP server).
  - Native `<dialog closedby="any">` diff preview modal showing syntax-highlighted diffs for every adapted file.
  - Real-time progress bar, dry-run simulation, and timestamped backups (`.sk_backup_<timestamp>`).

---

## 🚀 Quickstart

### 1. Installation

Clone and install dependencies (Python 3.10+ required):

```bash
git clone https://github.com/yourusername/skeleton-key.git
cd skeleton-key
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### 2. Launching the Interactive Web UI

On either machine, simply run:

```bash
skeleton-key ui
```

This launches the local UI at `http://127.0.0.1:5055` and opens your browser.

- **On your current machine (Linux)**: Select **Host Mode**. You'll see your 6-digit pairing PIN, LAN address, and a curated list of discovered dotfiles and project directories.
- **On your new machine (MacBook)**: Select **Client Mode**. Hit **Scan LAN** to detect the host via mDNS radar, enter the 6-digit PIN, verify the SAS fingerprint, customize your selections, and click **Start Import**.

---

## 🖥️ Command-Line Usage (Headless Mode)

Skeleton Key also includes a headless CLI mode if you prefer running directly in the terminal:

### Host Mode (Old Machine)
```bash
skeleton-key host
```
Output:
```text
============================================================
🗝️  SKELETON KEY — HOST MODE
============================================================
Hostname : pop-os (linux/x86_64)
Address  : 192.168.1.100:43821
Pair PIN : 849201  (enter this on client)
============================================================
Waiting for client connection...
```

### Client Mode (New Machine)
```bash
# Auto-discovers host on the LAN:
skeleton-key client

# Or connect directly with IP and PIN:
skeleton-key client --address 192.168.1.100 --port 43821 --pin 849201

# Run in dry-run mode (simulate without writing):
skeleton-key client --dry-run
```

---

## 🔄 Adaptation Rules Summary

| Linux / Source | macOS / Target | Reason |
| :--- | :--- | :--- |
| `/home/<user>` | `/Users/<user>` | Home directory relocation |
| `/home/linuxbrew/.linuxbrew` | `/opt/homebrew` (Apple Silicon) or `/usr/local` (Intel) | Homebrew prefix update |
| `~/.config/Code/User` | `~/Library/Application Support/Code/User` | macOS Application Support standard |
| `~/.config/Cursor/User` | `~/Library/Application Support/Cursor/User` | macOS Application Support standard |
| `~/.local/share/pnpm` | `~/Library/pnpm` | macOS pnpm store location |
| `xclip -selection clipboard` | `pbcopy` | macOS native clipboard |
| `xclip -selection clipboard -o` | `pbpaste` | macOS native clipboard |
| `xdg-open <url>` | `open <url>` | macOS native URL / file opener |
| `git credential helper libsecret` | `osxkeychain` | macOS Keychain integration |
| `/usr/share/zsh-...` | `/opt/homebrew/share/zsh-...` | Homebrew package path |

---

## 🛡️ Security

1. **No Open HTTP Server**: The file transfer mechanism uses a dedicated TCP socket with custom binary frame encapsulation (`MAGIC || length || AES-GCM ciphertext`). The web UI runs strictly on localhost (`127.0.0.1`).
2. **Brute Force Protection**: 5 consecutive failed PIN attempts automatically triggers PIN rotation and disconnects the client.
3. **Opt-in Secrets**: Private SSH keys (`~/.ssh/id_*`), AWS credentials, and kubeconfig files are classified as sensitive and excluded by default unless explicitly toggled on.
4. **Automatic Safety Backups**: Any file overwritten on the target machine is automatically copied to `<filename>.sk_backup_<timestamp>`.

---

## 🧪 Running Tests

```bash
pytest -v
```
All unit tests verify platform detection, adaptation transformations, secure crypto handshake, scanner classification, and the Flask UI APIs.