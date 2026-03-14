"""
Gmail Manage TUI — dsed google gmail manage

Layout:
  ┌─ email pane (2/3) ─────┬─ sidebar (1/3) ─┐
  │ FROM / DATE / SUBJECT  │ GMAIL LABELS     │
  │ snippet                │ CATEGORIES       │
  ├────────────────────────┴──────────────────┤
  │ help bar (one line)                       │
  │ status bar (one line)                     │
  │ > [command input]                         │
  └───────────────────────────────────────────┘
"""
from __future__ import annotations

import difflib
from typing import Optional

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, Static

from . import actions

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HELP = (
    "[dim]Commands:[/dim]  "
    "[cyan]cat <category>[/cyan]  "
    "[red]hard-delete[/red]  "
    "[yellow]soft-delete[/yellow]  "
    "[blue]move <label>[/blue]  "
    "[dim]  ·  Combine: cat <category> hard-delete  |  cat <category> soft-delete  |  "
    "cat <category> move <label>  ·  Empty/skip = skip[/dim]"
)

# ---------------------------------------------------------------------------
# Pure helpers (no side-effects)
# ---------------------------------------------------------------------------

def _find_conflicts(labels: list[dict]) -> list[tuple[str, str]]:
    """Return (a, b) pairs that differ only by case."""
    seen: dict[str, str] = {}
    conflicts: list[tuple[str, str]] = []
    for lbl in labels:
        name = lbl["name"]
        key = name.lower()
        if key in seen and seen[key] != name:
            conflicts.append((seen[key], name))
        else:
            seen[key] = name
    return conflicts


def _resolve_label(name: str, labels: list[dict], force_case: bool) -> dict | str:
    """Return matching label dict, or an error string."""
    if force_case:
        matches = [l for l in labels if l["name"] == name]
    else:
        matches = [l for l in labels if l["name"].lower() == name.lower()]

    if not matches:
        sample = ", ".join(l["name"] for l in labels[:8])
        return f"Label '{name}' not found. Available: {sample}"
    if len(matches) > 1:
        opts = ", ".join(m["name"] for m in matches)
        return f"Ambiguous label '{name}' — matches: {opts}. Use --force-label-case."
    return matches[0]


def _resolve_category(name: str, categories: list[dict]) -> dict | None:
    """Case-insensitive lookup in the categories list."""
    lower = name.lower()
    for cat in categories:
        if cat["name"] == lower:
            return cat
    return None


def _parse(text: str, labels: list[dict], categories: list[dict], force_case: bool) -> dict:
    """
    Parse a command string.

    Returns one of:
      {"action": "skip"}
      {"action": "hard-delete"}
      {"action": "soft-delete"}
      {"action": "move",        "label_obj": <dict>}
      {"action": "cat",         "category": <dict>, "secondary": None|"hard-delete"|"soft-delete"|"move", "label_obj": <dict>|None}
      {"action": "typo_guard",  "original": str, "suggestion": str|None, "secondary": ..., "label_obj": ...}
      {"error": str}
    """
    text = text.strip()

    if not text or text == "skip":
        return {"action": "skip"}

    if text == "hard-delete":
        return {"action": "hard-delete"}

    if text == "soft-delete":
        return {"action": "soft-delete"}

    if text.startswith("move "):
        label_name = text[5:].strip()
        if not label_name:
            return {"error": "move requires a label name"}
        result = _resolve_label(label_name, labels, force_case)
        if isinstance(result, str):
            return {"error": result}
        return {"action": "move", "label_obj": result}

    if text.startswith("cat "):
        rest = text[4:].strip()
        if not rest:
            return {"error": "cat requires a category name"}

        # Peel off terminal modifier (checking from the right so category can contain spaces)
        secondary: str | None = None
        label_obj: dict | None = None
        category_text = rest

        if rest.endswith(" hard-delete"):
            category_text = rest[: -len(" hard-delete")].strip()
            secondary = "hard-delete"
        elif rest.endswith(" soft-delete"):
            category_text = rest[: -len(" soft-delete")].strip()
            secondary = "soft-delete"
        elif " move " in rest:
            idx = rest.rfind(" move ")
            category_text = rest[:idx].strip()
            label_name = rest[idx + 6 :].strip()
            resolved = _resolve_label(label_name, labels, force_case)
            if isinstance(resolved, str):
                return {"error": resolved}
            label_obj = resolved
            secondary = "move"

        if not category_text:
            return {"error": "category name cannot be empty"}

        cat = _resolve_category(category_text, categories)
        if cat is None:
            suggestions = difflib.get_close_matches(
                category_text.lower(),
                [c["name"] for c in categories],
                n=1,
                cutoff=0.6,
            )
            return {
                "action": "typo_guard",
                "original": category_text,
                "suggestion": suggestions[0] if suggestions else None,
                "secondary": secondary,
                "label_obj": label_obj,
            }

        return {"action": "cat", "category": cat, "secondary": secondary, "label_obj": label_obj}

    return {
        "error": (
            "Unknown command. Valid: cat <category>, hard-delete, soft-delete, "
            "move <label>, or leave empty to skip."
        )
    }


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class GmailManageApp(App):
    CSS = """
    Screen {
        layout: vertical;
    }

    #main-area {
        layout: horizontal;
        height: 1fr;
    }

    #email-pane {
        width: 2fr;
        border: solid $primary;
        padding: 1 2;
        overflow-y: auto;
    }

    #sidebar {
        width: 1fr;
        border: solid $accent;
        padding: 1 2;
        overflow-y: auto;
    }

    #help-bar {
        height: 1;
        padding: 0 1;
        background: $boost;
        color: $text-muted;
    }

    #status-bar {
        height: 1;
        padding: 0 1;
        background: $surface;
    }

    #cmd-input {
        border: none;
        padding: 0 1;
    }
    """

    TITLE = "dsed · Gmail Manage"

    def __init__(self, force_label_case: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.force_label_case = force_label_case

        self.labels: list[dict] = []
        self.categories: list[dict] = []
        self.email_queue: list[dict] = []
        self.page_token: Optional[str] = None
        self.processed: int = 0
        self.total_inbox: int = 0
        self.current_email: Optional[dict] = None

        # Typo-guard state: set while waiting for y/n/c response
        self._typo_guard: Optional[dict] = None
        self._fatal: bool = False

    # ── Composition ──────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-area"):
            yield Static("Loading…", id="email-pane")
            yield Static("Loading…", id="sidebar")
        yield Static(_HELP, id="help-bar")
        yield Static("", id="status-bar")
        yield Input(placeholder="> ", id="cmd-input")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#cmd-input", Input).focus()
        self._load_initial()

    # ── Workers ──────────────────────────────────────────────────────────────

    @work(thread=True)
    def _load_initial(self) -> None:
        try:
            labels = actions.fetch_labels()
        except Exception as e:
            self.call_from_thread(self._fatal_error, f"Failed to load labels:\n\n{e}")
            return

        conflicts = _find_conflicts(labels)
        if conflicts and not self.force_label_case:
            lines = ["[bold red]ERROR: Gmail label case conflicts detected:[/bold red]\n"]
            for a, b in conflicts:
                lines.append(f'  [yellow]"{a}"[/yellow]  vs  [yellow]"{b}"[/yellow]')
            lines += [
                "",
                "Case-insensitive label matching is ambiguous. Options:",
                "  1. Fix label names on [link=https://gmail.com]gmail.com[/link] › Settings › Labels",
                "  2. Re-run with [cyan]--force-label-case[/cyan] to require exact casing",
            ]
            self.call_from_thread(self._fatal_error, "\n".join(lines))
            return

        self.call_from_thread(self._set_labels, labels)

        if self.force_label_case and conflicts:
            self.call_from_thread(
                self._set_status,
                "[yellow]⚠  --force-label-case: type label names with exact casing[/yellow]",
            )

        try:
            categories = actions.fetch_categories()
            self.call_from_thread(self._set_categories, categories)
        except Exception as e:
            self.call_from_thread(
                self._set_status, f"[yellow]Warning: could not load categories: {e}[/yellow]"
            )

        self._load_next_page()

    @work(thread=True)
    def _load_next_page(self) -> None:
        try:
            data = actions.fetch_inbox(self.page_token)
        except Exception as e:
            self.call_from_thread(self._set_status, f"[red]Failed to load inbox: {e}[/red]")
            return
        self.call_from_thread(self._receive_inbox, data)

    @work(thread=True)
    def _create_and_execute(self, guard: dict) -> None:
        try:
            cat = actions.create_category(guard["original"])
        except Exception as e:
            self.call_from_thread(self._set_status, f"[red]Failed to create category: {e}[/red]")
            return
        try:
            cats = actions.fetch_categories()
            self.call_from_thread(self._set_categories, cats)
        except Exception:
            pass
        self.call_from_thread(
            self._run_parsed,
            {"action": "cat", "category": cat, "secondary": guard.get("secondary"), "label_obj": guard.get("label_obj")},
        )

    @work(thread=True)
    def _run_parsed(self, parsed: dict) -> None:
        email = self.current_email
        if email is None:
            return
        msg_id = email["id"]
        action = parsed["action"]
        secondary = parsed.get("secondary")
        label_obj = parsed.get("label_obj")
        cat = parsed.get("category")

        try:
            if action == "cat" and cat:
                actions.assign_category(
                    msg_id,
                    cat["id"],
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
            self.call_from_thread(self._set_status, f"[red]Action failed: {e}[/red]")
            return

        self.call_from_thread(self._on_action_done)

    # ── State setters (always called on main thread) ─────────────────────────

    def _set_labels(self, labels: list[dict]) -> None:
        self.labels = labels
        self._refresh_sidebar()

    def _set_categories(self, categories: list[dict]) -> None:
        self.categories = categories
        self._refresh_sidebar()

    def _receive_inbox(self, data: dict) -> None:
        self.email_queue.extend(data.get("emails", []))
        self.page_token = data.get("nextPageToken")
        self.total_inbox = data.get("total", self.total_inbox)
        if self.current_email is None:
            if self.email_queue:
                self._advance()
            else:
                self._show_done()

    def _on_action_done(self) -> None:
        self.processed += 1
        self._advance()

    def _fatal_error(self, msg: str) -> None:
        self._fatal = True
        self.query_one("#email-pane", Static).update(msg)
        self.query_one("#cmd-input", Input).disabled = True

    def _set_status(self, msg: str) -> None:
        self.query_one("#status-bar", Static).update(msg)

    # ── Display helpers ───────────────────────────────────────────────────────

    def _advance(self) -> None:
        if not self.email_queue:
            if self.page_token:
                self._set_status("[dim]Loading more emails…[/dim]")
                self._load_next_page()
            else:
                self._show_done()
            return
        self.current_email = self.email_queue.pop(0)
        if len(self.email_queue) < 3 and self.page_token:
            self._load_next_page()
        self._refresh_email_pane()
        self._set_status("")

    def _refresh_email_pane(self) -> None:
        e = self.current_email
        if e is None:
            return
        lines = [
            f"[bold cyan]FROM:[/bold cyan]    {e.get('from', '(unknown)')}",
            f"[bold cyan]DATE:[/bold cyan]    {e.get('date', '')}",
            f"[bold cyan]SUBJECT:[/bold cyan] [bold]{e.get('subject', '(no subject)')}[/bold]",
            "",
            "[dim]" + "─" * 44 + "[/dim]",
            "",
            e.get("snippet", ""),
            "",
            "[dim]" + "─" * 44 + "[/dim]",
            f"[dim]{self.processed} processed · ~{self.total_inbox} in inbox[/dim]",
        ]
        self.query_one("#email-pane", Static).update("\n".join(lines))

    def _refresh_sidebar(self) -> None:
        lines: list[str] = []

        lines.append("[bold cyan]GMAIL LABELS[/bold cyan]")
        lines.append("[dim]" + "─" * 22 + "[/dim]")
        for lbl in self.labels:
            name = lbl.get("name", "")
            unread = lbl.get("unread", 0)
            if unread > 0:
                lines.append(f"[yellow]{name}[/yellow] [dim]({unread})[/dim]")
            else:
                lines.append(f"  {name}")

        lines.append("")
        lines.append("[bold cyan]CATEGORIES[/bold cyan]")
        lines.append("[dim]" + "─" * 22 + "[/dim]")
        if self.categories:
            for cat in self.categories:
                lines.append(f"  {cat['name']}")
        else:
            lines.append("[dim]  (none yet)[/dim]")

        self.query_one("#sidebar", Static).update("\n".join(lines))

    def _show_done(self) -> None:
        self.query_one("#email-pane", Static).update(
            f"[bold green]✓ All done![/bold green]\n\n"
            f"[dim]{self.processed} emails processed.[/dim]\n\n"
            f"No more inbox emails to triage."
        )

    # ── Input handling ────────────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.clear()

        if self._fatal or self.current_email is None:
            return

        if self._typo_guard is not None:
            self._handle_typo_response(text)
            return

        parsed = _parse(text, self.labels, self.categories, self.force_label_case)
        self._dispatch(parsed)

    def _dispatch(self, parsed: dict) -> None:
        if "error" in parsed:
            self._set_status(f"[red]{parsed['error']}[/red]")
            return

        if parsed["action"] == "skip":
            self.processed += 1
            self._advance()
            return

        if parsed["action"] == "typo_guard":
            self._typo_guard = parsed
            original = parsed["original"]
            suggestion = parsed.get("suggestion")
            if suggestion:
                self._set_status(
                    f"[yellow]'{original}' not found — did you mean '[bold]{suggestion}[/bold]'?  "
                    f"[cyan]y[/cyan] use it   [cyan]n[/cyan] cancel   [cyan]c[/cyan] create '{original}'[/yellow]"
                )
            else:
                self._set_status(
                    f"[yellow]Category '{original}' not found (no close match).  "
                    f"[cyan]n[/cyan] cancel   [cyan]c[/cyan] create '{original}'[/yellow]"
                )
            return

        self._run_parsed(parsed)

    def _handle_typo_response(self, text: str) -> None:
        guard = self._typo_guard
        self._typo_guard = None
        response = text.strip().lower()

        if response == "y" and guard.get("suggestion"):
            cat = _resolve_category(guard["suggestion"], self.categories)
            if cat is None:
                self._set_status(f"[red]Suggestion '{guard['suggestion']}' disappeared — re-enter command.[/red]")
                return
            self._run_parsed(
                {"action": "cat", "category": cat, "secondary": guard.get("secondary"), "label_obj": guard.get("label_obj")}
            )
        elif response == "c":
            self._create_and_execute(guard)
        elif response == "n":
            self._set_status("[dim]Cancelled — re-enter your command.[/dim]")
        else:
            # Re-arm guard state and show reminder
            self._typo_guard = guard
            self._set_status("[red]Enter y, n, or c.[/red]")
