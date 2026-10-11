"""Command line interface for skeleton-key.
Supports host mode, client mode, and web UI launcher.
"""
from __future__ import annotations

import argparse
import os
import sys
import webbrowser

from .config import HostConfig
from .discovery import discover
from .host import HostServer
from .platforms import Profile, current_os, detect
from .restore import RestorePlan, Restorer
from .ui.app import create_app


def run_ui(host: str = "127.0.0.1", port: int = 5055, open_browser: bool = True):
    """Launch local UI on localhost (not exposed as public server)."""
    app = create_app()
    url = f"http://{host}:{port}"
    print(f"🔑 Skeleton Key UI starting on {url}")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    app.run(host=host, port=port, debug=False)


def run_host_cli(port: int = 0, no_advertise: bool = False):
    """Headless host CLI mode."""
    prof = detect()
    cfg = HostConfig.load()
    server = HostServer(prof, cfg, port=port, advertise=not no_advertise)
    server.start()

    print("\n" + "=" * 60)
    print("🗝️  SKELETON KEY — HOST MODE")
    print("=" * 60)
    print(f"Hostname : {prof.hostname} ({prof.os}/{prof.arch})")
    print(f"Address  : {server.address}:{server.port}")
    print(f"Pair PIN : {server.pin}  (enter this on client)")
    print("=" * 60)
    print("Waiting for client connection... (Press Ctrl+C to stop)\n")

    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping host server...")
        server.stop()


def run_client_cli(address: str | None = None, port: int | None = None, pin: str | None = None, dry_run: bool = False):
    """Headless client CLI mode."""
    from .client import HostConnection

    prof = detect()
    print("\n" + "=" * 60)
    print("🗝️  SKELETON KEY — CLIENT MODE (NEW LAPTOP)")
    print("=" * 60)
    print(f"Target   : {prof.user}@{prof.hostname} ({prof.os}/{prof.arch})")
    print(f"Home     : {prof.home}")
    print("=" * 60)

    # 1. Discover or use specified address
    if not address or not port:
        print("🔍 Searching for Skeleton Key hosts on LAN via mDNS...")
        hosts = discover(timeout=3.0)
        if not hosts:
            print("No hosts found automatically. Please provide --address and --port.")
            sys.exit(1)
        print(f"Found {len(hosts)} host(s):")
        for idx, h in enumerate(hosts, 1):
            print(f"  [{idx}] {h.name} at {h.address}:{h.port} ({h.os})")
        choice = 0
        if len(hosts) == 1:
            choice = 1
        else:
            val = input(f"Select host [1-{len(hosts)}]: ").strip()
            choice = int(val) if val.isdigit() else 1
        selected = hosts[choice - 1]
        address, port = selected.address, selected.port

    if not pin:
        pin = input(f"Enter 6-digit PIN from host ({address}:{port}): ").strip()

    print(f"Connecting to {address}:{port} with PIN {pin}...")
    try:
        conn = HostConnection(address, port, pin)
    except Exception as exc:
        print(f"❌ Connection or pairing failed: {exc}")
        sys.exit(1)

    print(f"\n🔒 Session established!")
    print(f"👉 Security Verification Code (SAS): {conn.sas}")
    print("Verify this code matches on the host machine before proceeding!\n")

    manifest = conn.hello(prof)
    print(f"Received manifest from host {manifest.get('host', {}).get('hostname')}:")
    items = manifest.get("items", [])
    projects = manifest.get("projects", [])
    print(f"  • {len(items)} dotfile items")
    for pr in projects:
        print(f"  • Project root: {pr['rel']} ({len(pr.get('repos', []))} repos, {len(pr.get('dirs', []))} dirs)")

    if dry_run:
        print("\n[DRY RUN MODE ENABLED - No changes will be written]")

    confirm = input("\nProceed with environment replication? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        conn.close()
        sys.exit(0)

    def on_progress(msg: str, frac: float):
        pct = int(frac * 100)
        print(f"[{pct:3d}%] {msg}")

    restorer = Restorer(conn, manifest, prof, plan=RestorePlan(dry_run=dry_run), on_progress=on_progress)
    rep = restorer.run()
    conn.close()

    print("\n" + "=" * 60)
    print("🎉 ENVIRONMENT REPLICATION COMPLETE!")
    print("=" * 60)
    print(f"Directories created : {len(rep.dirs_created)}")
    print(f"Repositories cloned : {len(rep.repos)}")
    print(f"Dotfiles copied     : {rep.copied_count}")
    print(f"Dotfiles adapted    : {rep.adapted_count}")
    print(f"Files skipped       : {rep.skipped_count}")

    if rep.warnings:
        print("\n⚠️  ADVISORY WARNINGS & ACTIONABLE NEXT STEPS:")
        for w in rep.warnings:
            print(f"  • {w}")

    if rep.errors:
        print("\n❌ ERRORS ENCOUNTERED:")
        for e in rep.errors:
            print(f"  • {e}")


def main():
    parser = argparse.ArgumentParser(description="Skeleton Key — Cross-platform environment replicator")
    subparsers = parser.add_subparsers(dest="command")

    # ui command (default)
    ui_parser = subparsers.add_parser("ui", help="Launch interactive local web UI")
    ui_parser.add_argument("--port", type=int, default=5055, help="Port for local web UI (default 5055)")
    ui_parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")

    # host command
    host_parser = subparsers.add_parser("host", help="Run in Host mode (expose configurations)")
    host_parser.add_argument("--port", type=int, default=0, help="Listen port (default random)")
    host_parser.add_argument("--no-advertise", action="store_true", help="Disable mDNS advertisement")

    # client command
    client_parser = subparsers.add_parser("client", help="Run in Client mode (import to new machine)")
    client_parser.add_argument("--address", help="Host IP address")
    client_parser.add_argument("--port", type=int, help="Host port")
    client_parser.add_argument("--pin", help="Pairing PIN")
    client_parser.add_argument("--dry-run", action="store_true", help="Simulate import without writing to disk")

    args = parser.parse_args()

    # Default to UI mode if no command specified
    if not args.command or args.command == "ui":
        port = getattr(args, "port", 5055)
        no_browser = getattr(args, "no_browser", False)
        run_ui(port=port, open_browser=not no_browser)
    elif args.command == "host":
        run_host_cli(port=args.port, no_advertise=args.no_advertise)
    elif args.command == "client":
        run_client_cli(address=args.address, port=args.port, pin=args.pin, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
