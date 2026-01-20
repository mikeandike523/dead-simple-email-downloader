import click
from termcolor import colored
import shutil
import textwrap

from pysrc.call_route import call_route


def _stringify_preview(text):
    if not text:
        return ""
    return " ".join(text.splitlines()).strip()


def _sender_display(msg):
    sender = msg.get("from") or {}
    email = sender.get("emailAddress") or {}
    address = email.get("address") or ""
    name = email.get("name") or ""
    if name and address:
        return f"{name} <{address}>"
    return address or name or "unknown"

def _wrap_width():
    cols = shutil.get_terminal_size((120, 20)).columns
    return max(40, int(cols * 0.85))


def _wrap_with_prefix(prefix, text, width):
    if not text:
        return ""
    subsequent = " " * len(prefix)
    return textwrap.fill(
        text,
        width=width,
        initial_indent=prefix,
        subsequent_indent=subsequent,
    )


def impl_outlook_safe_delete(
    exact_sender,
    exact_subject,
    subject_is_regex=False,
    prompt=False,
    case_sensitive=False,
    preview_count=25,
    show_all=False,
    report=False,
    assume_yes=False,
    soft=False,
):
    if prompt:
        if not exact_sender:
            exact_sender = click.prompt("Exact sender email")
        if not exact_subject:
            label = "Subject regex" if subject_is_regex else "Exact subject"
            exact_subject = click.prompt(label)
    if not exact_sender or not exact_subject:
        print(
            colored(
                "exact-sender and exact-subject are required (or use --prompt).",
                "red",
            )
        )
        return -1

    if preview_count < 1:
        print(colored("preview-count must be at least 1.", "red"))
        return -1

    resp = call_route(
        "/outlook/safe-delete/find",
        "Finding matching messages...",
        json_body={
            "exactSender": exact_sender,
            "exactSubject": exact_subject,
            "caseSensitive": case_sensitive,
            "subjectIsRegex": subject_is_regex,
        },
    )
    if resp is None:
        return -1

    data = resp.data
    if not isinstance(data, dict):
        print(colored("Unexpected response from backend.", "red"))
        return -1

    matches = data.get("matches", [])
    if not isinstance(matches, list):
        print(colored("Unexpected response from backend.", "red"))
        return -1

    total = len(matches)
    if total == 0:
        print(colored("No matching messages found.", "yellow"))
        return 0

    if show_all:
        preview_count = total
    else:
        preview_count = min(preview_count, total)
    print(colored(f"Found {total} matching messages.", "green"))
    print(colored(f"Showing first {preview_count} preview(s):", "cyan"))

    width = _wrap_width()
    for i, msg in enumerate(matches[:preview_count]):
        sender_display = _sender_display(msg)
        subject = msg.get("subject") or ""
        preview = _stringify_preview(msg.get("bodyPreview") or "")
        sender_line = _wrap_with_prefix(f"{i+1}. Sender: ", sender_display, width)
        subject_line = _wrap_with_prefix("   Subject: ", subject, width)
        preview_line = _wrap_with_prefix("   Preview: ", preview, width)
        if sender_line:
            print(colored(sender_line, "cyan"))
        if subject_line:
            print(colored(subject_line, "yellow"))
        if preview_line:
            print(preview_line)
        print()

    remaining = total - preview_count
    if remaining > 0:
        print(colored(f"... and {remaining} more", "yellow"))

    if report:
        return 0

    action_label = "Move" if soft else "Delete"
    if not assume_yes:
        confirm = click.confirm(
            f"{action_label} {total} message(s) with safe-delete now?",
            default=False,
        )
        if not confirm:
            print(colored("Aborted.", "yellow"))
            return 0

    delete_resp = call_route(
        "/outlook/safe-delete/delete",
        "Deleting messages..." if not soft else "Moving messages to trash...",
        json_body={
            "messageIds": [m.get("id") for m in matches if m.get("id")],
            "soft": soft,
        },
    )
    if delete_resp is None:
        return -1

    delete_data = delete_resp.data or {}
    deleted_ids = delete_data.get("deletedIds", [])
    failed = delete_data.get("failed", [])

    print(
        colored(
            f"Deleted {len(deleted_ids)} of {total} messages.",
            "green" if len(deleted_ids) == total else "yellow",
        )
    )
    if failed:
        print(colored(f"Failed to delete {len(failed)} messages:", "red"))
        for item in failed[:10]:
            failed_id = item.get("id", "unknown")
            status = item.get("status")
            detail = item.get("error", "")
            line = f"- {failed_id}"
            if status:
                line += f" (status {status})"
            if detail:
                line += f": {detail}"
            print(line)

    return 0
