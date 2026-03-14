"""
Flask + Socket.IO web server for the Gmail Manage UI.

Thin interface over the same actions/parse logic used by the old TUI.
All state is server-side; the browser is a dumb display + input box.
"""
from __future__ import annotations

import os
import socket
import threading
import time
import webbrowser

from flask import Flask, send_from_directory
from flask_socketio import SocketIO

from pysrc.tui.gmail_manage import actions
from pysrc.tui.gmail_manage.app import (
    _find_conflicts,
    _parse,
    _resolve_category,
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


# ---------------------------------------------------------------------------
# Port helper
# ---------------------------------------------------------------------------

def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------------------
# Server factory
# ---------------------------------------------------------------------------

def run_server(force_label_case: bool = False) -> None:
    port = _find_free_port()
    app = Flask(__name__)
    sio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

    # ── Single-user in-process state ─────────────────────────────────────────
    state: dict = {
        "labels": [],
        "categories": [],
        "email_queue": [],
        "page_token": None,
        "processed": 0,
        "total_inbox": 0,
        "current_email": None,
        "typo_guard": None,
        "fatal": False,
    }

    # ── Static file serving (no-cache headers on everything) ─────────────────

    def _no_cache(resp):
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    @app.route("/")
    def index():
        return _no_cache(send_from_directory(STATIC_DIR, "index.html"))

    @app.route("/<path:filename>")
    def static_file(filename):
        return _no_cache(send_from_directory(STATIC_DIR, filename))

    # ── Emit helpers (always safe to call from any thread) ───────────────────

    def _emit(event: str, data: dict | None = None) -> None:
        sio.emit(event, data or {})

    def _emit_sidebar() -> None:
        _emit("sidebar", {"labels": state["labels"], "categories": state["categories"]})

    def _emit_email() -> None:
        e = state["current_email"]
        if e is None:
            return
        _emit("email", {**e, "processed": state["processed"], "total": state["total_inbox"]})

    def _emit_status(msg: str, level: str = "info") -> None:
        _emit("status", {"msg": msg, "level": level})

    # ── Advance to next email ─────────────────────────────────────────────────

    def _advance() -> None:
        if not state["email_queue"]:
            if state["page_token"]:
                _emit_status("Loading more emails…", "dim")
                threading.Thread(target=_bg_load_page, daemon=True).start()
            else:
                _emit("done", {"processed": state["processed"]})
            return
        state["current_email"] = state["email_queue"].pop(0)
        if len(state["email_queue"]) < 3 and state["page_token"]:
            threading.Thread(target=_bg_load_page, daemon=True).start()
        _emit_email()
        _emit_status("")

    # ── Background workers ────────────────────────────────────────────────────

    def _bg_load_page() -> None:
        try:
            data = actions.fetch_inbox(state["page_token"])
        except Exception as e:
            _emit_status(f"Failed to load inbox: {e}", "error")
            return
        state["email_queue"].extend(data.get("emails", []))
        state["page_token"] = data.get("nextPageToken")
        state["total_inbox"] = data.get("total", state["total_inbox"])
        if state["current_email"] is None:
            _advance()

    def _bg_load_initial() -> None:
        try:
            labels = actions.fetch_labels()
        except Exception as e:
            state["fatal"] = True
            _emit("fatal", {"msg": f"Failed to load labels:\n{e}"})
            return

        conflicts = _find_conflicts(labels)
        if conflicts and not force_label_case:
            lines = ["ERROR: Gmail label case conflicts detected:\n"]
            for a, b in conflicts:
                lines.append(f'  "{a}"  vs  "{b}"')
            lines += [
                "",
                "Case-insensitive label matching is ambiguous. Options:",
                "  1. Fix label names on gmail.com › Settings › Labels",
                "  2. Re-run with --force-label-case to require exact casing",
            ]
            state["fatal"] = True
            _emit("fatal", {"msg": "\n".join(lines)})
            return

        state["labels"] = labels
        _emit_sidebar()

        if force_label_case and conflicts:
            _emit_status("⚠  --force-label-case: type label names with exact casing", "warning")

        try:
            state["categories"] = actions.fetch_categories()
            _emit_sidebar()
        except Exception as e:
            _emit_status(f"Warning: could not load categories: {e}", "warning")

        _bg_load_page()

    def _bg_run_action(parsed: dict) -> None:
        email = state["current_email"]
        if not email:
            return
        msg_id = email["id"]
        action = parsed["action"]
        secondary = parsed.get("secondary")
        label_obj = parsed.get("label_obj")
        cat = parsed.get("category")

        try:
            if action == "cat" and cat:
                actions.assign_category(
                    msg_id, cat["id"],
                    subject=email.get("subject"),
                    body_preview=email.get("snippet"),
                )
            if action == "hard-delete" or secondary == "hard-delete":
                actions.hard_delete(msg_id)
            elif action == "soft-delete" or secondary == "soft-delete":
                actions.soft_delete(msg_id)
            elif (action == "move" or secondary == "move") and label_obj:
                actions.move_to_label(msg_id, label_obj["id"])
        except Exception as e:
            _emit_status(f"Action failed: {e}", "error")
            return

        state["processed"] += 1
        state["current_email"] = None
        _advance()

    def _bg_create_and_run(guard: dict) -> None:
        try:
            cat = actions.create_category(guard["original"])
        except Exception as e:
            _emit_status(f"Failed to create category: {e}", "error")
            return
        try:
            state["categories"] = actions.fetch_categories()
            _emit_sidebar()
        except Exception:
            pass
        _bg_run_action({
            "action": "cat",
            "category": cat,
            "secondary": guard.get("secondary"),
            "label_obj": guard.get("label_obj"),
        })

    # ── Command processing (always runs in background thread) ─────────────────

    def _process_command(text: str) -> None:
        """Called from a background thread; safe to call sio.emit."""
        if state["fatal"] or state["current_email"] is None:
            return

        if state["typo_guard"] is not None:
            _handle_typo(text)
            return

        parsed = _parse(text, state["labels"], state["categories"], force_label_case)
        _dispatch(parsed)

    def _dispatch(parsed: dict) -> None:
        if "error" in parsed:
            _emit_status(parsed["error"], "error")
            return

        if parsed["action"] == "skip":
            state["processed"] += 1
            _advance()
            return

        if parsed["action"] == "typo_guard":
            state["typo_guard"] = parsed
            orig = parsed["original"]
            sugg = parsed.get("suggestion")
            if sugg:
                msg = (
                    f"'{orig}' not found — did you mean '{sugg}'?  "
                    f"y = use it   n = cancel   c = create '{orig}'"
                )
            else:
                msg = (
                    f"Category '{orig}' not found (no close match).  "
                    f"n = cancel   c = create '{orig}'"
                )
            _emit_status(msg, "typo")
            return

        _bg_run_action(parsed)

    def _handle_typo(text: str) -> None:
        guard = state["typo_guard"]
        state["typo_guard"] = None
        r = text.strip().lower()

        if r == "y" and guard.get("suggestion"):
            cat = _resolve_category(guard["suggestion"], state["categories"])
            if not cat:
                _emit_status("Suggestion disappeared — re-enter command.", "error")
                return
            _bg_run_action({
                "action": "cat",
                "category": cat,
                "secondary": guard.get("secondary"),
                "label_obj": guard.get("label_obj"),
            })
        elif r == "c":
            _bg_create_and_run(guard)
        elif r == "n":
            _emit_status("Cancelled — re-enter your command.", "dim")
        else:
            state["typo_guard"] = guard
            _emit_status("Enter y, n, or c.", "error")

    # ── Socket.IO events ──────────────────────────────────────────────────────

    @sio.on("connect")
    def on_connect():
        # Reset state on each (re)connect so a browser refresh starts fresh
        state.update({
            "labels": [], "categories": [], "email_queue": [],
            "page_token": None, "processed": 0, "total_inbox": 0,
            "current_email": None, "typo_guard": None, "fatal": False,
        })
        _emit_status("Connecting…", "dim")
        threading.Thread(target=_bg_load_initial, daemon=True).start()

    @sio.on("command")
    def on_command(data):
        text = (data or {}).get("text", "").strip()
        # Offload to background thread so we never block the event loop
        threading.Thread(target=_process_command, args=(text,), daemon=True).start()

    # ── Start server ──────────────────────────────────────────────────────────

    url = f"http://localhost:{port}"
    print(f"\n  Gmail Manage UI  →  {url}\n")

    def _open_browser():
        time.sleep(1.0)
        webbrowser.open(url)

    threading.Thread(target=_open_browser, daemon=True).start()
    sio.run(app, host="localhost", port=port, debug=False, use_reloader=False)
