"""Flask UI backend for skeleton-key.
Provides local desktop control for both Host (exposing/previewing)
and Client (discovering, customizing, diff-inspecting, and restoring).
Bound strictly to localhost by default (not a generic public HTTP server).
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any

from flask import Flask, jsonify, render_template, request

from ..adapters import AdaptContext, adapt, compute_diff, is_text
from ..client import HostConnection
from ..config import HostConfig, to_home_rel
from ..discovery import discover
from ..host import HostServer
from ..platforms import Profile, default_home_for, detect
from ..restore import RestorePlan, Restorer


class AppState:
    def __init__(self):
        self.profile = detect()
        self.config = HostConfig.load()
        self.host_server: HostServer | None = None
        self.client_conn: HostConnection | None = None
        self.client_manifest: dict | None = None
        self.client_target_profile: Profile | None = None
        self.restore_progress: dict[str, Any] = {"running": False, "msg": "", "pct": 0.0, "report": None}
        self.restore_lock = threading.Lock()


def create_app(initial_mode: str = "host", host_server: HostServer | None = None, config: HostConfig | None = None) -> Flask:
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    app = Flask(__name__, template_folder=template_dir)
    state = AppState()
    if config:
        state.config = config
    if host_server:
        state.host_server = host_server

    @app.route("/")
    def index():
        return render_template("index.html")

    # -----------------------------------------------------------------------
    # System & Profile APIs
    # -----------------------------------------------------------------------
    @app.route("/api/profile")
    def get_profile():
        return jsonify(state.profile.to_dict())

    @app.route("/api/state")
    def get_state():
        host_active = state.host_server is not None
        host_info = None
        if host_active and state.host_server:
            host_info = {
                "address": state.host_server.address,
                "port": state.host_server.port,
                "pin": state.host_server.pin,
                "sas": state.host_server.session.get("sas") if state.host_server.session else None,
                "paired": state.host_server.session is not None,
                "peer": state.host_server.session.get("peer") if state.host_server.session else None,
                "events": list(state.host_server.events)[-20:],
            }

        client_active = state.client_conn is not None
        client_info = None
        if client_active and state.client_conn:
            client_info = {
                "address": state.client_conn.address,
                "port": state.client_conn.port,
                "sas": state.client_conn.sas,
                "host_summary": state.client_manifest.get("host") if state.client_manifest else None,
            }

        return jsonify({
            "local_profile": state.profile.to_dict(),
            "host": host_info,
            "client": client_info,
            "restore": state.restore_progress,
        })

    # -----------------------------------------------------------------------
    # Host Mode APIs
    # -----------------------------------------------------------------------
    @app.route("/api/host/start", methods=["POST"])
    def host_start():
        if state.host_server is None:
            state.host_server = HostServer(state.profile, state.config).start()
        return jsonify({
            "ok": True,
            "address": state.host_server.address,
            "port": state.host_server.port,
            "pin": state.host_server.pin,
        })

    @app.route("/api/host/stop", methods=["POST"])
    def host_stop():
        if state.host_server:
            state.host_server.stop()
            state.host_server = None
        return jsonify({"ok": True})

    @app.route("/api/host/rotate_pin", methods=["POST"])
    def host_rotate_pin():
        if not state.host_server:
            return jsonify({"ok": False, "error": "Host not running"}), 400
        pin = state.host_server.rotate_pin()
        return jsonify({"ok": True, "pin": pin})

    @app.route("/api/host/manifest")
    def host_manifest():
        if not state.host_server:
            state.host_server = HostServer(state.profile, state.config).start()
        preview_target = state.host_server.preview_target()
        manifest = state.host_server.manifest_for(preview_target)
        # Include all items (not only exposed) so user can customize
        return jsonify(manifest.to_dict(exposed_only=False))

    @app.route("/api/host/toggle_item", methods=["POST"])
    def host_toggle_item():
        data = request.json or {}
        path = data.get("path")
        exposed = bool(data.get("exposed"))
        if not path:
            return jsonify({"ok": False, "error": "path required"}), 400

        state.config.exposure[path] = exposed
        state.config.save()
        if state.host_server:
            state.host_server.invalidate()
        return jsonify({"ok": True})

    @app.route("/api/host/add_path", methods=["POST"])
    def host_add_path():
        data = request.json or {}
        raw = data.get("path", "").strip()
        try:
            rel = to_home_rel(state.profile.home, raw)
        except ValueError as err:
            return jsonify({"ok": False, "error": str(err)}), 400

        if rel not in state.config.extra_paths:
            state.config.extra_paths.append(rel)
            state.config.exposure[rel] = True
            state.config.save()
            if state.host_server:
                state.host_server.invalidate()
        return jsonify({"ok": True, "rel": rel})

    @app.route("/api/host/remove_path", methods=["POST"])
    def host_remove_path():
        data = request.json or {}
        rel = data.get("path", "").strip()
        if rel in state.config.extra_paths:
            state.config.extra_paths.remove(rel)
        state.config.exposure.pop(rel, None)
        state.config.save()
        if state.host_server:
            state.host_server.invalidate()
        return jsonify({"ok": True})

    @app.route("/api/host/add_root", methods=["POST"])
    def host_add_root():
        data = request.json or {}
        raw = data.get("root", "").strip()
        try:
            rel = to_home_rel(state.profile.home, raw)
        except ValueError as err:
            return jsonify({"ok": False, "error": str(err)}), 400

        if rel not in state.config.project_roots:
            state.config.project_roots.append(rel)
            state.config.save()
            if state.host_server:
                state.host_server.invalidate()
        return jsonify({"ok": True, "rel": rel})

    @app.route("/api/host/remove_root", methods=["POST"])
    def host_remove_root():
        data = request.json or {}
        rel = data.get("root", "").strip()
        if rel in state.config.project_roots:
            state.config.project_roots.remove(rel)
            state.config.save()
            if state.host_server:
                state.host_server.invalidate()
        return jsonify({"ok": True})

    @app.route("/api/host/diff/<file_id>")
    def host_diff(file_id: str):
        if not state.host_server:
            return jsonify({"ok": False, "error": "Host not running"}), 400
        preview_target = state.host_server.preview_target()
        manifest = state.host_server.manifest_for(preview_target)
        file_path = manifest.files.get(file_id)
        if not file_path or not os.path.exists(file_path):
            return jsonify({"ok": False, "error": "File not found"}), 404

        rel = os.path.relpath(file_path, state.profile.home).replace(os.sep, "/")
        try:
            with open(file_path, "rb") as fh:
                data = fh.read()
        except OSError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

        if not is_text(data):
            return jsonify({
                "ok": True,
                "is_binary": True,
                "rel": rel,
                "size": len(data),
            })

        original_text = data.decode("utf-8")
        ctx = AdaptContext(src=state.profile, dst=preview_target)
        res = adapt(rel, data, ctx)
        adapted_text = res.data.decode("utf-8")
        diff_text = compute_diff(original_text, adapted_text, fromfile=f"Host: ~/{rel}", tofile=f"Target: ~/{res.target_rel}")

        return jsonify({
            "ok": True,
            "is_binary": False,
            "rel": rel,
            "target_rel": res.target_rel,
            "changes": res.changes,
            "warnings": res.warnings,
            "diff": diff_text,
            "original": original_text,
            "adapted": adapted_text,
        })

    # -----------------------------------------------------------------------
    # Client Mode APIs
    # -----------------------------------------------------------------------
    @app.route("/api/client/discover")
    def client_discover():
        hosts = discover(timeout=2.0)
        return jsonify([h.to_dict() for h in hosts])

    @app.route("/api/client/connect", methods=["POST"])
    def client_connect():
        data = request.json or {}
        address = data.get("address", "").strip()
        port = int(data.get("port", 0))
        pin = data.get("pin", "").strip()
        if not address or not port or not pin:
            return jsonify({"ok": False, "error": "Address, port, and PIN required"}), 400

        try:
            conn = HostConnection(address, port, pin)
            target = state.profile
            manifest = conn.hello(target)
            state.client_conn = conn
            state.client_manifest = manifest
            state.client_target_profile = target
            return jsonify({
                "ok": True,
                "sas": conn.sas,
                "manifest": manifest,
                "host_info": manifest.get("host"),
            })
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/client/disconnect", methods=["POST"])
    def client_disconnect():
        if state.client_conn:
            state.client_conn.close()
            state.client_conn = None
            state.client_manifest = None
        return jsonify({"ok": True})

    @app.route("/api/client/manifest")
    def client_manifest():
        if not state.client_manifest:
            return jsonify({"ok": False, "error": "Not connected"}), 400
        return jsonify(state.client_manifest)

    @app.route("/api/client/diff/<file_id>")
    def client_diff(file_id: str):
        if not state.client_conn or not state.client_manifest:
            return jsonify({"ok": False, "error": "Not connected"}), 400

        # Find file entry in manifest
        found_fe = None
        for item in state.client_manifest.get("items", []):
            for fe in item.get("files", []):
                if fe["id"] == file_id:
                    found_fe = fe
                    break
            if found_fe:
                break

        if not found_fe:
            for pr in state.client_manifest.get("projects", []):
                for fe in pr.get("loose", []):
                    if fe["id"] == file_id:
                        found_fe = fe
                        break
                if found_fe:
                    break

        if not found_fe:
            return jsonify({"ok": False, "error": "File entry not found in manifest"}), 404

        try:
            raw_bytes, _ = state.client_conn.fetch(file_id)
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

        if not is_text(raw_bytes):
            return jsonify({
                "ok": True,
                "is_binary": True,
                "rel": found_fe["rel"],
                "size": len(raw_bytes),
            })

        src_profile = Profile.from_dict(state.client_manifest["host"])
        ctx = AdaptContext(src=src_profile, dst=state.profile)
        res = adapt(found_fe["rel"], raw_bytes, ctx)

        original_text = raw_bytes.decode("utf-8")
        adapted_text = res.data.decode("utf-8")
        diff_text = compute_diff(
            original_text,
            adapted_text,
            fromfile=f"Host: ~/{found_fe['rel']}",
            tofile=f"Target: ~/{res.target_rel}",
        )

        return jsonify({
            "ok": True,
            "is_binary": False,
            "rel": found_fe["rel"],
            "target_rel": res.target_rel,
            "changes": res.changes,
            "warnings": res.warnings,
            "diff": diff_text,
            "original": original_text,
            "adapted": adapted_text,
        })

    @app.route("/api/client/restore", methods=["POST"])
    def client_restore():
        if not state.client_conn or not state.client_manifest:
            return jsonify({"ok": False, "error": "Not connected"}), 400

        data = request.json or {}
        plan = RestorePlan(
            item_ids=set(data.get("item_ids", [])),
            repo_ids=set(data.get("repo_ids", [])),
            include_loose=bool(data.get("include_loose", True)),
            include_overlays=bool(data.get("include_overlays", True)),
            root_map=dict(data.get("root_map", {})),
            recreate_symlinks=bool(data.get("recreate_symlinks", True)),
            dry_run=bool(data.get("dry_run", False)),
        )

        with state.restore_lock:
            if state.restore_progress["running"]:
                return jsonify({"ok": False, "error": "Restore already in progress"}), 400
            state.restore_progress = {
                "running": True,
                "msg": "Starting restore...",
                "pct": 0.0,
                "report": None,
                "dry_run": plan.dry_run,
            }

        def run_thread():
            def progress(msg: str, frac: float):
                with state.restore_lock:
                    state.restore_progress["msg"] = msg
                    state.restore_progress["pct"] = round(frac * 100, 1)

            try:
                restorer = Restorer(
                    conn=state.client_conn,
                    manifest=state.client_manifest,
                    target_profile=state.profile,
                    plan=plan,
                    on_progress=progress,
                )
                rep = restorer.run()
                rep_dict = {
                    "duration": round(rep.duration, 2),
                    "copied_count": rep.copied_count,
                    "adapted_count": rep.adapted_count,
                    "skipped_count": rep.skipped_count,
                    "dirs_created": rep.dirs_created,
                    "warnings": rep.warnings,
                    "errors": rep.errors,
                    "repos": [
                        {
                            "path": r.path,
                            "remote": r.remote,
                            "branch": r.branch,
                            "action": r.action,
                            "overlays": r.overlays_applied,
                            "error": r.error,
                        }
                        for r in rep.repos
                    ],
                    "files": [
                        {
                            "rel": f.rel,
                            "target_rel": f.target_rel,
                            "action": f.action,
                            "changes": f.changes,
                            "warnings": f.warnings,
                            "backup": f.backup_path,
                            "error": f.error,
                        }
                        for f in rep.files
                    ],
                }
                with state.restore_lock:
                    state.restore_progress["running"] = False
                    state.restore_progress["msg"] = "Complete"
                    state.restore_progress["pct"] = 100.0
                    state.restore_progress["report"] = rep_dict
            except Exception as exc:
                with state.restore_lock:
                    state.restore_progress["running"] = False
                    state.restore_progress["msg"] = f"Failed: {exc}"
                    state.restore_progress["report"] = {"errors": [str(exc)]}

        threading.Thread(target=run_thread, daemon=True).start()
        return jsonify({"ok": True})

    @app.route("/api/client/restore_status")
    def client_restore_status():
        with state.restore_lock:
            return jsonify(state.restore_progress)

    return app
